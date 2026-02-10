"""
FLC Bank - Model de Conta Mãe Grafeno
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Enum, func
from sqlalchemy.dialects.mysql import DECIMAL
from app.database import Base
import uuid as uuid_lib
import enum


class OnboardingStatus(str, enum.Enum):
    """Status do onboarding"""
    PENDING = "PENDING"           # Aguardando envio
    SUBMITTED = "SUBMITTED"       # Enviado para Grafeno
    UNDER_REVIEW = "UNDER_REVIEW" # Em análise
    APPROVED = "APPROVED"         # Aprovado
    REJECTED = "REJECTED"         # Rejeitado
    ACTIVE = "ACTIVE"             # Conta ativa


class GrafenoAccount(Base):
    """Modelo de conta mãe Grafeno"""
    
    __tablename__ = "grafeno_accounts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid_lib.uuid4()))
    
    # Dados da empresa
    name = Column(String(255), nullable=False)  # Nome fantasia
    company_name = Column(String(255), nullable=False)  # Razão social
    document_number = Column(String(18), nullable=False, unique=True)  # CNPJ
    legal_nature = Column(String(50), nullable=False)  # LTDA, SA, etc
    tax_regime = Column(String(50), nullable=True)  # Simples Nacional, Lucro Presumido, etc
    
    # Contato
    commercial_phone = Column(String(20), nullable=False)
    email = Column(String(255), nullable=False)
    nire = Column(String(50), nullable=True)
    
    # Endereço
    address_street = Column(String(255), nullable=False)
    address_number = Column(String(20), nullable=False)
    address_complement = Column(String(100), nullable=True)
    address_neighborhood = Column(String(100), nullable=False)
    address_city = Column(String(100), nullable=False)
    address_state = Column(String(2), nullable=False)
    address_country = Column(String(2), nullable=False, default="BR")
    address_zipcode = Column(String(10), nullable=False)
    
    # Administrador
    admin_name = Column(String(255), nullable=False)
    admin_email = Column(String(255), nullable=False)
    admin_phone = Column(String(20), nullable=False)
    admin_document = Column(String(14), nullable=False)  # CPF
    
    # Faturamento
    revenue_informed = Column(String(5), default="false")
    revenue_value = Column(String(50), nullable=True)
    revenue_period_start = Column(String(10), nullable=True)
    revenue_period_end = Column(String(10), nullable=True)
    
    # Assinaturas necessárias
    required_signers = Column(Integer, nullable=False, default=1)
    
    # Capital Social
    social_capital = Column(DECIMAL(15, 2), nullable=True)
    
    # Credenciais (salvar localmente como solicitado)
    password = Column(String(255), nullable=True)
    api_key = Column(String(255), nullable=True)
    api_secret = Column(String(255), nullable=True)
    
    # Status e resposta do Grafeno
    status = Column(Enum(OnboardingStatus), nullable=False, default=OnboardingStatus.PENDING)
    grafeno_id = Column(String(100), nullable=True)  # ID retornado pelo Grafeno
    grafeno_response = Column(JSON, nullable=True)  # Resposta completa do Grafeno
    
    # Dados da conta (após aprovação)
    account_number = Column(String(50), nullable=True)
    agency = Column(String(10), nullable=True)
    bank_code = Column(String(10), nullable=True, default="274")
    pix_key = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    submitted_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    # Arquivos (armazenar referência e conteúdo)
    article_of_association_filename = Column(String(255), nullable=True)
    article_of_association_content = Column(Text, nullable=True)  # Base64
    
    # Documento de identidade do administrador (RG/CNH)
    admin_identity_filename = Column(String(255), nullable=True)
    admin_identity_content = Column(Text, nullable=True)  # Base64
    
    def __repr__(self):
        return f"<GrafenoAccount(id={self.id}, company='{self.company_name}', status='{self.status}')>"
