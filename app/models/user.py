from sqlmodel import Field, SQLModel
from typing import Optional
from pydantic import EmailStr

class UserBase(SQLModel,):
    username: str = Field(index=True, unique=True)
    email: EmailStr = Field(index=True, unique=True)
    passwordHash: str
    fullName: str = ""
    role: str = "student"

class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)