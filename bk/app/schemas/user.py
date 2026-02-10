"""
FLC Bank - Schemas de Usuário
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    MASTER = "MASTER"
    ADMIN = "ADMIN"
    USER = "USER"


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    BLOCKED = "BLOCKED"


class PixKeyType(str, Enum):
    CPF = "CPF"
    CNPJ = "CNPJ"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    RANDOM = "RANDOM"


class UserBase(BaseModel):
    """Schema base de usuário"""
    email: EmailStr
    full_name: str = Field(..., min_length=3, max_length=255)
    cpf_cnpj: Optional[str] = Field(None, max_length=18)
    phone: Optional[str] = Field(None, max_length=20)
    pix_key: Optional[str] = Field(None, max_length=255)
    pix_key_type: Optional[PixKeyType] = None


class UserCreate(UserBase):
    """Schema para criação de usuário"""
    password: str = Field(..., min_length=6, max_length=100)
    role: UserRole = UserRole.USER


class UserUpdate(BaseModel):
    """Schema para atualização de usuário"""
    full_name: Optional[str] = Field(None, min_length=3, max_length=255)
    cpf_cnpj: Optional[str] = Field(None, max_length=18)
    phone: Optional[str] = Field(None, max_length=20)
    pix_key: Optional[str] = Field(None, max_length=255)
    pix_key_type: Optional[PixKeyType] = None
    status: Optional[UserStatus] = None


class UserResponse(BaseModel):
    """Schema de resposta de usuário"""
    uuid: str
    email: str
    full_name: str
    cpf_cnpj: Optional[str] = None
    phone: Optional[str] = None
    role: UserRole
    status: UserStatus
    pix_key: Optional[str] = None
    pix_key_type: Optional[PixKeyType] = None
    created_at: datetime
    last_login_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Schema para lista de usuários"""
    users: List[UserResponse]
    total: int
    page: int
    per_page: int


class UserLogin(BaseModel):
    """Schema para login"""
    email: EmailStr
    password: str


class Token(BaseModel):
    """Schema de token JWT"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Schema de dados do token"""
    user_uuid: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    exp: Optional[int] = None


class PasswordChange(BaseModel):
    """Schema para troca de senha"""
    current_password: str
    new_password: str = Field(..., min_length=6, max_length=100)
