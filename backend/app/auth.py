import hashlib
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .config import Settings, get_settings
from .database import get_session
from .models import LocalSession, LocalUser


USERNAME_PATTERN = re.compile(r"^[a-z0-9._-]{3,64}$")
PASSWORD_HASH = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = PASSWORD_HASH.hash("dummy-password-never-used-for-login")
INITIAL_ACCOUNT_PASSWORD = "Password123"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=12, max_length=128)
    confirm_password: SecretStr = Field(min_length=12, max_length=128)


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    is_admin: bool


class AuthResponse(BaseModel):
    user: UserResponse
    csrf_token: str


@dataclass(frozen=True)
class AuthContext:
    user: LocalUser
    session: LocalSession


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def normalize_username(username: str) -> str:
    normalized = username.strip().lower()
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError("Username harus 3-64 karakter: huruf kecil, angka, titik, garis bawah, atau tanda hubung.")
    return normalized


def validate_password(password: str) -> None:
    if not 12 <= len(password) <= 128:
        raise ValueError("Password harus terdiri dari 12-128 karakter.")


def create_local_user(
    session: Session,
    *,
    username: str,
    display_name: str,
    password: str,
    is_admin: bool = False,
    initial_password: bool = False,
) -> LocalUser:
    normalized = normalize_username(username)
    name = display_name.strip()
    if not 1 <= len(name) <= 128:
        raise ValueError("Nama tampilan harus terdiri dari 1-128 karakter.")
    if not (initial_password and password == INITIAL_ACCOUNT_PASSWORD):
        validate_password(password)
    if session.scalar(select(LocalUser).where(LocalUser.username == normalized)):
        raise ValueError("Username sudah digunakan.")
    user = LocalUser(
        username=normalized,
        display_name=name,
        password_hash=PASSWORD_HASH.hash(password),
        is_admin=is_admin,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def set_local_password(session: Session, user: LocalUser, password: str) -> None:
    validate_password(password)
    user.password_hash = PASSWORD_HASH.hash(password)
    user.failed_login_count = 0
    user.locked_until = None
    for active_session in list(user.sessions):
        session.delete(active_session)
    session.commit()


def authenticate_local_user(
    session: Session, username: str, password: str, config: Settings
) -> LocalUser | None:
    normalized = username.strip().lower()
    user = session.scalar(select(LocalUser).where(LocalUser.username == normalized))
    if not user:
        PASSWORD_HASH.verify(password, DUMMY_PASSWORD_HASH)
        return None
    now = _now()
    if not user.is_active or user.locked_until and _aware(user.locked_until) > now:
        PASSWORD_HASH.verify(password, DUMMY_PASSWORD_HASH)
        return None
    valid, replacement_hash = PASSWORD_HASH.verify_and_update(password, user.password_hash)
    if not valid:
        user.failed_login_count += 1
        if user.failed_login_count >= config.auth_max_failed_attempts:
            user.locked_until = now + timedelta(minutes=config.auth_lock_minutes)
        session.commit()
        return None
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    if replacement_hash:
        user.password_hash = replacement_hash
    session.commit()
    return user


def create_local_session(
    session: Session, user: LocalUser, config: Settings
) -> tuple[LocalSession, str]:
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    auth_session = LocalSession(
        token_hash=_token_hash(token),
        csrf_token=csrf_token,
        user=user,
        expires_at=_now() + timedelta(hours=config.auth_session_hours),
    )
    session.add(auth_session)
    session.commit()
    session.refresh(auth_session)
    return auth_session, token


def require_user(
    request: Request,
    session: Session = Depends(get_session),
    config: Settings = Depends(get_settings),
) -> AuthContext:
    token = request.cookies.get(config.auth_cookie_name)
    auth_session = None
    if token:
        auth_session = session.scalar(
            select(LocalSession)
            .options(joinedload(LocalSession.user))
            .where(LocalSession.token_hash == _token_hash(token))
        )
    if not auth_session or not auth_session.user.is_active:
        raise HTTPException(status_code=401, detail={"message": "Sesi login diperlukan."})
    if _aware(auth_session.expires_at) <= _now():
        session.delete(auth_session)
        session.commit()
        raise HTTPException(status_code=401, detail={"message": "Sesi login telah berakhir."})
    if request.method not in SAFE_METHODS:
        supplied = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(supplied, auth_session.csrf_token):
            raise HTTPException(status_code=403, detail={"message": "Token keamanan permintaan tidak valid."})
    return AuthContext(auth_session.user, auth_session)


def _response(context: AuthContext) -> AuthResponse:
    return AuthResponse(
        user=UserResponse(
            id=context.user.id,
            username=context.user.username,
            display_name=context.user.display_name,
            is_admin=context.user.is_admin,
        ),
        csrf_token=context.session.csrf_token,
    )


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=AuthResponse)
def login(
    credentials: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
    config: Settings = Depends(get_settings),
) -> AuthResponse:
    user = authenticate_local_user(session, credentials.username, credentials.password, config)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "Username atau password tidak valid."})
    auth_session, token = create_local_session(session, user, config)
    response.set_cookie(
        key=config.auth_cookie_name,
        value=token,
        max_age=config.auth_session_hours * 3600,
        httponly=True,
        secure=config.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.headers["cache-control"] = "no-store"
    return _response(AuthContext(user, auth_session))


@router.get("/me", response_model=AuthResponse)
def me(context: AuthContext = Depends(require_user)) -> AuthResponse:
    return _response(context)


@router.post("/password")
def change_own_password(
    payload: PasswordChangeRequest,
    response: Response,
    context: AuthContext = Depends(require_user),
    session: Session = Depends(get_session),
    config: Settings = Depends(get_settings),
) -> dict[str, str]:
    current_password = payload.current_password.get_secret_value()
    new_password = payload.new_password.get_secret_value()
    if new_password != payload.confirm_password.get_secret_value():
        raise HTTPException(status_code=422, detail={"message": "Konfirmasi password baru tidak cocok."})
    if new_password == current_password:
        raise HTTPException(status_code=422, detail={"message": "Password baru harus berbeda dari password saat ini."})
    user = session.scalar(
        select(LocalUser).where(LocalUser.id == context.user.id)
        .with_for_update().execution_options(populate_existing=True)
    )
    now = _now()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail={"message": "Sesi login diperlukan."})
    if user.locked_until and _aware(user.locked_until) > now:
        raise HTTPException(status_code=400, detail={"message": "Verifikasi password sementara terkunci. Coba lagi nanti."})
    if not PASSWORD_HASH.verify(current_password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= config.auth_max_failed_attempts:
            user.locked_until = now + timedelta(minutes=config.auth_lock_minutes)
        session.commit()
        raise HTTPException(status_code=400, detail={"message": "Password saat ini tidak benar."})
    set_local_password(session, user, new_password)
    response.delete_cookie(
        config.auth_cookie_name, path="/", secure=config.auth_cookie_secure,
        httponly=True, samesite="lax",
    )
    response.headers["cache-control"] = "no-store"
    return {"message": "Password berhasil diubah. Silakan masuk kembali dengan password baru."}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    context: AuthContext = Depends(require_user),
    session: Session = Depends(get_session),
    config: Settings = Depends(get_settings),
) -> None:
    session.delete(context.session)
    session.commit()
    response.delete_cookie(
        config.auth_cookie_name,
        path="/",
        secure=config.auth_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.headers["cache-control"] = "no-store"
