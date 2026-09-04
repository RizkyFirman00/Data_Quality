import argparse
import getpass
import sys
from pathlib import Path

# Mendukung eksekusi langsung: `python scripts/manage_user.py ...`.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.auth import create_local_user, set_local_password
from app.database import SessionLocal
from app.models import LocalUser


def _password() -> str:
    first = getpass.getpass("Password: ")
    second = getpass.getpass("Ulangi password: ")
    if first != second:
        raise ValueError("Konfirmasi password tidak sama.")
    return first


def main() -> None:
    parser = argparse.ArgumentParser(description="Kelola akun lokal Data Quality.")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--username", required=True)
    create.add_argument("--display-name", required=True)
    create.add_argument("--admin", action="store_true")
    password = commands.add_parser("password")
    password.add_argument("--username", required=True)
    for command in ("enable", "disable"):
        target = commands.add_parser(command)
        target.add_argument("--username", required=True)
    args = parser.parse_args()

    with SessionLocal() as session:
        try:
            if args.command == "create":
                user = create_local_user(
                    session,
                    username=args.username,
                    display_name=args.display_name,
                    password=_password(),
                    is_admin=args.admin,
                )
                print(f"Akun {user.username} berhasil dibuat.")
                return
            username = args.username.strip().lower()
            user = session.scalar(select(LocalUser).where(LocalUser.username == username))
            if not user:
                raise ValueError("Akun tidak ditemukan.")
            if args.command == "password":
                set_local_password(session, user, _password())
                print(f"Password {user.username} berhasil diubah dan seluruh sesi dicabut.")
                return
            user.is_active = args.command == "enable"
            if not user.is_active:
                for active_session in list(user.sessions):
                    session.delete(active_session)
            session.commit()
            action = "diaktifkan" if user.is_active else "dinonaktifkan"
            print(f"Akun {user.username} berhasil {action}.")
        except ValueError as exc:
            parser.error(str(exc))


if __name__ == "__main__":
    main()
