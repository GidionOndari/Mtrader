from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import Role


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_fingerprint: str = Field(min_length=8, max_length=256)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'


class RefreshRequest(BaseModel):
    refresh_token: str
    device_fingerprint: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: Role


class VaultKeyUpsertRequest(BaseModel):
    provider: str
    api_key: str = Field(min_length=8)


class VaultKeyView(BaseModel):
    id: int
    provider: str
    key_last4: str
    updated_at: datetime


class VaultTestRequest(BaseModel):
    provider: str


class VaultTestResponse(BaseModel):
    provider: str
    ok: bool
    detail: str
