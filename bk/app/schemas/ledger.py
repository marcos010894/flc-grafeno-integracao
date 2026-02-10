"""
FLC Bank - Schemas de Ledger e Alocação
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from enum import Enum


class DiscountType(str, Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED = "FIXED"


class EntryType(str, Enum):
    PIX_CREDIT = "PIX_CREDIT"
    PIX_DEBIT = "PIX_DEBIT"
    COMPANY_FEE = "COMPANY_FEE"
    WITHDRAWAL = "WITHDRAWAL"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    ADJUSTMENT_CREDIT = "ADJUSTMENT_CREDIT"
    ADJUSTMENT_DEBIT = "ADJUSTMENT_DEBIT"


class EntryDirection(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class AllocationCreate(BaseModel):
    """Schema para criar alocação de PIX"""
    pix_uuid: str = Field(..., description="UUID do PIX a ser alocado")
    user_uuid: str = Field(..., description="UUID do usuário destino")
    discount_type: DiscountType = Field(..., description="Tipo de desconto")
    discount_value: Decimal = Field(..., ge=0, description="Valor ou percentual do desconto")
    notes: Optional[str] = Field(None, description="Observações")


class AllocationSimulation(BaseModel):
    """Schema para simulação de alocação"""
    pix_uuid: str
    discount_type: DiscountType
    discount_value: Decimal = Field(..., ge=0)


class AllocationSimulationResponse(BaseModel):
    """Resposta da simulação de alocação"""
    gross_amount: Decimal
    discount_type: DiscountType
    discount_value: Decimal
    discount_amount: Decimal
    net_amount: Decimal
    company_margin: Decimal
    discount_percentage: float


class AllocationResponse(BaseModel):
    """Schema de resposta de alocação"""
    uuid: str
    pix_uuid: str
    user_uuid: str
    user_name: str
    allocated_by_uuid: str
    allocated_by_name: str
    
    gross_amount: Decimal
    discount_type: DiscountType
    discount_value: Decimal
    discount_amount: Decimal
    net_amount: Decimal
    company_margin: Decimal
    
    notes: Optional[str] = None
    allocated_at: datetime
    
    # Dados do PIX
    payer_name: Optional[str] = None
    payer_cpf_cnpj: Optional[str] = None
    transaction_date: datetime
    
    class Config:
        from_attributes = True


class AllocationListResponse(BaseModel):
    """Lista de alocações"""
    allocations: List[AllocationResponse]
    total: int
    total_gross: Decimal
    total_net: Decimal
    total_margin: Decimal
    page: int
    per_page: int


class LedgerEntryResponse(BaseModel):
    """Schema de resposta de lançamento do ledger"""
    uuid: str
    entry_type: EntryType
    amount: Decimal
    direction: EntryDirection
    balance_after: Decimal
    description: Optional[str] = None
    created_at: datetime
    
    # Referências
    pix_uuid: Optional[str] = None
    allocation_uuid: Optional[str] = None
    payer_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class LedgerListResponse(BaseModel):
    """Lista de lançamentos"""
    entries: List[LedgerEntryResponse]
    total: int
    page: int
    per_page: int


class BalanceResponse(BaseModel):
    """Schema de resposta de saldo"""
    user_uuid: str
    user_name: str
    available_balance: Decimal
    total_received: Decimal
    total_withdrawn: Decimal
    pending_withdrawals: Decimal = Decimal("0.00")
    last_update: datetime


class CompanyBalanceResponse(BaseModel):
    """Schema de resposta de saldo da empresa"""
    total_pix_received: Decimal
    total_allocated: Decimal
    total_margin: Decimal
    pending_allocation: Decimal
    pix_count: int
    allocation_count: int
    last_update: datetime


class ExtractItem(BaseModel):
    """Item do extrato"""
    date: datetime
    description: str
    type: EntryType
    direction: EntryDirection
    gross_amount: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None
    net_amount: Decimal
    balance: Decimal
    payer_name: Optional[str] = None


class ExtractResponse(BaseModel):
    """Extrato completo"""
    user_uuid: str
    user_name: str
    period_start: datetime
    period_end: datetime
    opening_balance: Decimal
    closing_balance: Decimal
    total_credits: Decimal
    total_debits: Decimal
    entries: List[ExtractItem]
