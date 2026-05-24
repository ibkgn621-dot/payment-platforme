from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime
from .models import UserRole

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: UUID
    email: str
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class VerifyTokenRequest(BaseModel):
    token: str

class VerifyTokenResponse(BaseModel):
    valid: bool
    user_id: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
