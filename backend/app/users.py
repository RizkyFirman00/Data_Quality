import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import AuthContext, INITIAL_ACCOUNT_PASSWORD, create_local_user, require_user
from .database import get_session
from .models import LocalUser


class CreateAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    role: Literal["Admin", "Pemeriksa"] = "Pemeriksa"


class AccountResponse(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    role: Literal["Admin", "Pemeriksa"]
    is_active: bool


def require_admin(context: AuthContext = Depends(require_user)) -> AuthContext:
    if not context.user.is_admin:
        raise HTTPException(status_code=403, detail={"message": "Hanya Admin yang dapat mengelola akun."})
    return context


def account_response(user: LocalUser) -> AccountResponse:
    return AccountResponse(
        id=user.id, username=user.username, display_name=user.display_name,
        role="Admin" if user.is_admin else "Pemeriksa", is_active=user.is_active,
    )


router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[AccountResponse])
def list_accounts(response: Response, session: Session = Depends(get_session)):
    response.headers["cache-control"] = "no-store"
    users = session.scalars(select(LocalUser).order_by(LocalUser.created_at.desc(), LocalUser.username)).all()
    return [account_response(user) for user in users]


@router.post("", response_model=AccountResponse, status_code=201)
def create_account(payload: CreateAccountRequest, response: Response, session: Session = Depends(get_session)):
    try:
        user = create_local_user(
            session, username=payload.username, display_name=payload.display_name,
            password=INITIAL_ACCOUNT_PASSWORD, is_admin=payload.role == "Admin",
            initial_password=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409 if str(exc) == "Username sudah digunakan." else 422, detail={"message": str(exc)}) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail={"message": "Username sudah digunakan."}) from exc
    response.headers["cache-control"] = "no-store"
    return account_response(user)
