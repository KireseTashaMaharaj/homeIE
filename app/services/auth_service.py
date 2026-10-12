from typing import Optional

from app.repositories.user import UserRepository
from app.schemas.user import LandlordUserCreate, RegularUserCreate
from app.utilities.security import (
    create_access_token,
    encrypt_password,
    verify_password,
)


class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def authenticate_user(self, username: str, password: str) -> Optional[str]:
        user = self.user_repo.get_by_username(username)
        if not user or not verify_password(
            plaintext_password=password,
            encrypted_password=user.passwordHash,
        ):
            return None
        return create_access_token(data={"sub": f"{user.id}", "role": user.role})

    def register_user(
        self,
        username: str,
        email: str,
        password: str,
        role: str = "student",
    ):
        if role not in {"student", "landlord"}:
            raise ValueError("Choose Student or Landlord.")
        user_type = LandlordUserCreate if role == "landlord" else RegularUserCreate
        user = user_type(
            username=username,
            email=email,
            passwordHash=encrypt_password(password),
            fullName=username,
            role=role,
        )
        return self.user_repo.create(user)
