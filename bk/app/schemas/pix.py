"""
FLC Bank - Schemas de PIX
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum


class PixStatus(str, Enum):
    PENDING = "PENDING"
    ALLOCATED = "ALLOCATED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class PixCreate(BaseModel):
    """Schema para registro de PIX recebido"""
    external_id: Optional[str] = Field(None, max_length=100)
    end_to_end_id: Optional[str] = Field(None, max_length=100)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    payer_name: Optional[str] = Field(None, max_length=255)
    payer_cpf_cnpj: Optional[str] = Field(None, max_length=18)
    payer_bank_code: Optional[str] = Field(None, max_length=10)
    payer_bank_name: Optional[str] = Field(None, max_length=100)
    payer_agency: Optional[str] = Field(None, max_length=10)
    payer_account: Optional[str] = Field(None, max_length=20)
    payer_pix_key: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    transaction_date: datetime
    raw_payload: Optional[Any] = None


class PixResponse(BaseModel):
    """Schema de resposta de PIX"""
    uuid: str
    external_id: Optional[str] = None
    end_to_end_id: Optional[str] = None
    amount: Decimal
    payer_name: Optional[str] = None
    payer_cpf_cnpj: Optional[str] = None
    payer_bank_code: Optional[str] = None
    payer_bank_name: Optional[str] = None
    payer_pix_key: Optional[str] = None
    description: Optional[str] = None
    transaction_date: datetime
    status: PixStatus
    created_at: datetime
    
    # Campos de alocação (preenchidos se allocated)
    allocated_to_name: Optional[str] = None
    allocated_to_uuid: Optional[str] = None
    allocation_uuid: Optional[str] = None
    
    class Config:
        from_attributes = True


class PixListResponse(BaseModel):
    """Schema para lista de PIX"""
    pix_list: List[PixResponse]
    total: int
    total_amount: Decimal
    page: int
    per_page: int


class PixStats(BaseModel):
    """Schema de estatísticas de PIX"""
    total_pending: int
    total_pending_amount: Decimal
    total_allocated: int
    total_allocated_amount: Decimal
    total_today: int
    total_today_amount: Decimal


class PixWebhook(BaseModel):
    """Schema para recebimento de webhook de PIX"""
    external_id: str
    end_to_end_id: str
    amount: Decimal
    payer_name: Optional[str] = None
    payer_cpf_cnpj: Optional[str] = None
    payer_pix_key: Optional[str] = None
    description: Optional[str] = None
    transaction_date: datetime
    raw_payload: Optional[Any] = None


# =============================================
# Schemas para Solicitação de PIX de Saída
# =============================================

class PixOutgoingStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class PixOutgoingCreate(BaseModel):
    """Schema para criar solicitação de envio de PIX"""
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="Valor do PIX")
    recipient_pix_key: str = Field(..., min_length=1, max_length=255, description="Chave PIX do destinatário")
    recipient_pix_key_type: str = Field(..., description="Tipo da chave PIX")
    recipient_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=500)


class PixOutgoingResponse(BaseModel):
    """Schema de resposta de solicitação de PIX"""
    uuid: str
    amount: Decimal
    recipient_pix_key: str
    recipient_pix_key_type: str
    recipient_name: Optional[str] = None
    recipient_bank: Optional[str] = None
    recipient_document: Optional[str] = None
    description: Optional[str] = None
    status: PixOutgoingStatus
    created_at: datetime
    processed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    receipt_url: Optional[str] = None
    receipt_filename: Optional[str] = None
    e2e_id: Optional[str] = None
    
    # Dados do solicitante (para Master)
    user_name: Optional[str] = None
    user_uuid: Optional[str] = None
    
    class Config:
        from_attributes = True


class PixOutgoingListResponse(BaseModel):
    """Schema para lista de solicitações de PIX"""
    requests: List[PixOutgoingResponse]
    total: int
    total_amount: Decimal
    page: int
    per_page: int


class PixOutgoingProcess(BaseModel):
    """Schema para Master processar solicitação"""
    action: str = Field(..., description="'approve' ou 'reject'")
    e2e_id: Optional[str] = Field(None, description="E2E ID do PIX enviado")
    receipt_data: Optional[str] = Field(None, description="Comprovante em base64")
    receipt_filename: Optional[str] = Field(None, description="Nome do arquivo do comprovante")
    rejection_reason: Optional[str] = Field(None, description="Motivo da rejeição")
