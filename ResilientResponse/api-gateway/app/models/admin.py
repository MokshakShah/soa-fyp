from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class AdminRole(str, Enum):
    ADMIN = "ADMIN"


class AdminInDB(BaseModel):
    id: Optional[str] = None
    email: str
    password_hash: str
    role: AdminRole = AdminRole.ADMIN
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AdminResponse(BaseModel):
    id: str
    email: str
    role: AdminRole
    name: str
    created_at: datetime
    updated_at: datetime


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: AdminResponse
