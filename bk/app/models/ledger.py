"""
FLC Bank - Models de Ledger e Alocação
"""

from sqlalchemy import Column, Integer, BigInteger, String, Enum, DateTime, DECIMAL, Text, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base
import enum
import uuid as uuid_lib


class DiscountType(str, enum.Enum):
    """Tipos de desconto"""
    PERCENTAGE = "PERCENTAGE"
    FIXED = "FIXED"


class EntryType(str, enum.Enum):
    """Tipos de lançamento no ledger"""
    PIX_CREDIT = "PIX_CREDIT"
    PIX_DEBIT = "PIX_DEBIT"
    COMPANY_FEE = "COMPANY_FEE"
    WITHDRAWAL = "WITHDRAWAL"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    ADJUSTMENT_CREDIT = "ADJUSTMENT_CREDIT"
    ADJUSTMENT_DEBIT = "ADJUSTMENT_DEBIT"


class EntryDirection(str, enum.Enum):
    """Direção do lançamento"""
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class Allocation(Base):
    """Modelo de alocação de PIX a usuário"""
    
    __tablename__ = "allocations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid_lib.uuid4()))
    
    # Referências
    pix_id = Column(Integer, ForeignKey("pix_incoming.id"), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    allocated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Valores
    gross_amount = Column(DECIMAL(15, 2), nullable=False)
    discount_type = Column(Enum(DiscountType), nullable=False)
    discount_value = Column(DECIMAL(15, 2), nullable=False)
    discount_amount = Column(DECIMAL(15, 2), nullable=False)
    net_amount = Column(DECIMAL(15, 2), nullable=False)
    company_margin = Column(DECIMAL(15, 2), nullable=False)
    
    # Metadados
    notes = Column(Text, nullable=True)
    allocated_at = Column(DateTime, server_default=func.now())
    
    # Relacionamentos
    pix = relationship("PixIncoming", back_populates="allocation", foreign_keys=[pix_id])
    user = relationship("User", foreign_keys=[user_id], back_populates="allocations_received")
    master = relationship("User", foreign_keys=[allocated_by], back_populates="allocations_made")
    ledger_entries = relationship("LedgerEntry", back_populates="allocation")
    
    def __repr__(self):
        return f"<Allocation(id={self.id}, gross={self.gross_amount}, net={self.net_amount})>"
    
    @property
    def discount_percentage(self) -> float:
        """Retorna o percentual de desconto aplicado"""
        if self.gross_amount and float(self.gross_amount) > 0:
            return (float(self.discount_amount) / float(self.gross_amount)) * 100
        return 0.0


class LedgerEntry(Base):
    """
    Modelo de lançamento no ledger (IMUTÁVEL)
    Esta tabela NUNCA deve ter UPDATE ou DELETE
    """
    
    __tablename__ = "ledger_entries"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid_lib.uuid4()))
    
    # Referências
    allocation_id = Column(Integer, ForeignKey("allocations.id"), nullable=True)
    pix_id = Column(Integer, ForeignKey("pix_incoming.id"), nullable=True)
    account_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Tipo e valores
    entry_type = Column(Enum(EntryType), nullable=False)
    amount = Column(DECIMAL(15, 2), nullable=False)
    direction = Column(Enum(EntryDirection), nullable=False)
    balance_after = Column(DECIMAL(15, 2), nullable=False)
    
    # Descrição
    description = Column(String(500), nullable=True)
    reference_type = Column(String(50), nullable=True)
    reference_id = Column(String(100), nullable=True)
    
    # Imutabilidade e rastreabilidade
    created_at = Column(DateTime, server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Integridade (opcional - para blockchain-like)
    entry_hash = Column(String(64), nullable=True)
    previous_entry_id = Column(BigInteger, nullable=True)
    
    # Relacionamentos
    allocation = relationship("Allocation", back_populates="ledger_entries")
    pix = relationship("PixIncoming", back_populates="ledger_entries")
    account = relationship("User", foreign_keys=[account_id], back_populates="ledger_entries")
    creator = relationship("User", foreign_keys=[created_by])
    
    def __repr__(self):
        return f"<LedgerEntry(id={self.id}, type='{self.entry_type}', amount={self.amount}, direction='{self.direction}')>"
    
    @property
    def is_credit(self) -> bool:
        """Verifica se é um lançamento a crédito"""
        return self.direction == EntryDirection.CREDIT
    
    @property
    def is_debit(self) -> bool:
        """Verifica se é um lançamento a débito"""
        return self.direction == EntryDirection.DEBIT
    
    @property
    def signed_amount(self) -> float:
        """Retorna o valor com sinal (+ para crédito, - para débito)"""
        amount = float(self.amount) if self.amount else 0.0
        return amount if self.is_credit else -amount
