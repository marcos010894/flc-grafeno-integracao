"""
FLC Bank - Model de Usuário
"""

from sqlalchemy import Column, Integer, String, Enum, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base
import enum
import uuid as uuid_lib


class UserRole(str, enum.Enum):
    """Roles de usuário no sistema"""
    MASTER = "MASTER"
    ADMIN = "ADMIN"
    USER = "USER"


class UserStatus(str, enum.Enum):
    """Status do usuário"""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    BLOCKED = "BLOCKED"


class PixKeyType(str, enum.Enum):
    """Tipos de chave PIX"""
    CPF = "CPF"
    CNPJ = "CNPJ"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    RANDOM = "RANDOM"


class User(Base):
    """Modelo de usuário do sistema"""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid_lib.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    cpf_cnpj = Column(String(18), unique=True, nullable=True)
    phone = Column(String(20), nullable=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.USER)
    status = Column(Enum(UserStatus), nullable=False, default=UserStatus.ACTIVE)
    pix_key = Column(String(255), nullable=True)
    pix_key_type = Column(Enum(PixKeyType), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime, nullable=True)
    
    # Relacionamentos
    allocations_received = relationship(
        "Allocation",
        foreign_keys="Allocation.user_id",
        back_populates="user"
    )
    allocations_made = relationship(
        "Allocation",
        foreign_keys="Allocation.allocated_by",
        back_populates="master"
    )
    ledger_entries = relationship(
        "LedgerEntry",
        foreign_keys="LedgerEntry.account_id",
        back_populates="account"
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"
    
    @property
    def is_master(self) -> bool:
        """Verifica se o usuário é master"""
        return self.role == UserRole.MASTER
    
    @property
    def is_admin(self) -> bool:
        """Verifica se o usuário é admin ou master"""
        return self.role in [UserRole.MASTER, UserRole.ADMIN]
    
    @property
    def is_active(self) -> bool:
        """Verifica se o usuário está ativo"""
        return self.status == UserStatus.ACTIVE
