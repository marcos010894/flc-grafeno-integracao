"""
FLC Bank - Schemas de Conta Grafeno
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class LegalNatureEnum(str, Enum):
    LTDA = "LTDA"
    SA = "SA"
    EIRELI = "EIRELI"
    MEI = "MEI"
    EI = "EI"
    SLU = "SLU"
    SS = "SS"


class TaxRegimeEnum(str, Enum):
    SIMPLES_NACIONAL = "SIMPLES_NACIONAL"
    LUCRO_PRESUMIDO = "LUCRO_PRESUMIDO"
    LUCRO_REAL = "LUCRO_REAL"
    MEI = "MEI"


class AddressCreate(BaseModel):
    street: str = Field(..., min_length=1, max_length=255)
    number: str = Field(..., min_length=1, max_length=20)
    complement: Optional[str] = Field(None, max_length=100)
    neighborhood: str = Field(..., min_length=1, max_length=100)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=2, max_length=2)
    country: str = Field(default="BR", max_length=2)
    zipCode: str = Field(..., min_length=8, max_length=10)


class FileUpload(BaseModel):
    filename: str
    content: str  # Base64


class AdministratorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., min_length=10, max_length=20)
    documentNumber: str = Field(..., min_length=11, max_length=14)
    identityDocument: Optional[FileUpload] = None  # RG/CNH (frente e verso)


class RevenueCreate(BaseModel):
    informed: bool = Field(default=False)
    value: Optional[str] = None
    periodStartAt: Optional[str] = None
    periodEndAt: Optional[str] = None


class GrafenoAccountCreate(BaseModel):
    """Schema para criar conta mãe Grafeno"""
    # Dados da empresa
    name: str = Field(..., min_length=1, max_length=255, description="Nome fantasia")
    companyName: str = Field(..., min_length=1, max_length=255, description="Razão social")
    documentNumber: str = Field(..., min_length=14, max_length=18, description="CNPJ")
    legalNature: LegalNatureEnum = Field(..., description="Natureza jurídica")
    taxRegime: Optional[TaxRegimeEnum] = None
    nire: Optional[str] = None
    
    # Contato
    commercialPhone: str = Field(..., min_length=10, max_length=20)
    email: str = Field(..., min_length=1, max_length=255)
    
    # Endereço
    address: AddressCreate
    
    # Administrador
    administrator: AdministratorCreate
    
    # Faturamento
    revenue: Optional[RevenueCreate] = None
    
    # Assinaturas
    requiredSigners: int = Field(default=1, ge=1)
    
    # Capital Social
    socialCapital: Optional[float] = Field(default=None, description="Capital social da empresa")
    
    # Contrato social (obrigatório)
    articleOfAssociation: FileUpload
    
    # Senha local (para salvar no banco)
    password: Optional[str] = None


class GrafenoAccountResponse(BaseModel):
    uuid: str
    name: str
    company_name: str
    document_number: str
    legal_nature: str
    email: str
    commercial_phone: str
    status: str
    grafeno_id: Optional[str] = None
    account_number: Optional[str] = None
    agency: Optional[str] = None
    pix_key: Optional[str] = None
    created_at: datetime
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class GrafenoAccountListResponse(BaseModel):
    accounts: list[GrafenoAccountResponse]
    total: int
