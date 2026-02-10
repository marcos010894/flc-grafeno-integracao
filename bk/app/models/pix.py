"""
FLC Bank - Model de PIX
"""

from sqlalchemy import Column, Integer, String, Enum, DateTime, DECIMAL, Text, JSON, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base
import enum
import uuid as uuid_lib


class PixStatus(str, enum.Enum):
    """Status do PIX recebido"""
    PENDING = "PENDING"
    ALLOCATED = "ALLOCATED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class PixOutgoingStatus(str, enum.Enum):
    """Status da solicitação de PIX de saída"""
    PENDING = "PENDING"           # Aguardando envio pelo Master
    PROCESSING = "PROCESSING"     # Em processamento
    COMPLETED = "COMPLETED"       # Enviado com sucesso
    CANCELLED = "CANCELLED"       # Cancelado
    REJECTED = "REJECTED"         # Rejeitado pelo Master


class PixIncoming(Base):
    """Modelo de PIX recebido na conta principal"""
    
    __tablename__ = "pix_incoming"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid_lib.uuid4()))
    external_id = Column(String(100), unique=True, nullable=True)
    end_to_end_id = Column(String(100), unique=True, nullable=True)
    
    # Valores
    amount = Column(DECIMAL(15, 2), nullable=False)
    
    # Dados do pagador
    payer_name = Column(String(255), nullable=True)
    payer_cpf_cnpj = Column(String(18), nullable=True, index=True)
    payer_bank_code = Column(String(10), nullable=True)
    payer_bank_name = Column(String(100), nullable=True)
    payer_agency = Column(String(10), nullable=True)
    payer_account = Column(String(20), nullable=True)
    payer_pix_key = Column(String(255), nullable=True)
    
    # Informações adicionais
    description = Column(Text, nullable=True)
    transaction_date = Column(DateTime, nullable=False)
    
    # Status
    status = Column(Enum(PixStatus), nullable=False, default=PixStatus.PENDING, index=True)
    
    # Metadados
    raw_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relacionamentos
    allocation = relationship("Allocation", back_populates="pix", uselist=False)
    ledger_entries = relationship("LedgerEntry", back_populates="pix")
    
    def __repr__(self):
        return f"<PixIncoming(id={self.id}, amount={self.amount}, status='{self.status}')>"
    
    @property
    def is_pending(self) -> bool:
        """Verifica se o PIX está pendente de alocação"""
        return self.status == PixStatus.PENDING
    
    @property
    def is_allocated(self) -> bool:
        """Verifica se o PIX já foi alocado"""
        return self.status == PixStatus.ALLOCATED
    
    @property
    def amount_float(self) -> float:
        """Retorna o valor como float"""
        return float(self.amount) if self.amount else 0.0


class PixOutgoingRequest(Base):
    """Modelo de solicitação de envio de PIX"""
    
    __tablename__ = "pix_outgoing_requests"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid_lib.uuid4()))
    
    # Solicitante
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Valor
    amount = Column(DECIMAL(15, 2), nullable=False)
    
    # Dados do destinatário
    recipient_pix_key = Column(String(255), nullable=False)
    recipient_pix_key_type = Column(String(20), nullable=False)  # CPF, CNPJ, EMAIL, PHONE, RANDOM
    recipient_name = Column(String(255), nullable=True)
    recipient_bank = Column(String(100), nullable=True)
    recipient_document = Column(String(18), nullable=True)
    
    # Descrição
    description = Column(Text, nullable=True)
    
    # Status
    status = Column(Enum(PixOutgoingStatus), nullable=False, default=PixOutgoingStatus.PENDING, index=True)
    
    # Processamento pelo Master
    processed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    processed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Comprovante (URL ou base64)
    receipt_url = Column(Text, nullable=True)
    receipt_filename = Column(String(255), nullable=True)
    
    # E2E ID após envio
    e2e_id = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relacionamentos
    user = relationship("User", foreign_keys=[user_id], backref="pix_outgoing_requests")
    processor = relationship("User", foreign_keys=[processed_by])
    
    def __repr__(self):
        return f"<PixOutgoingRequest(id={self.id}, amount={self.amount}, status='{self.status}')>"
    
    @property
    def amount_float(self) -> float:
        """Retorna o valor como float"""
        return float(self.amount) if self.amount else 0.0
