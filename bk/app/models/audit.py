"""
FLC Bank - Model de Auditoria
"""

from sqlalchemy import Column, BigInteger, Integer, String, DateTime, JSON, func
from app.database import Base
import uuid as uuid_lib


class ActionType:
    """Tipos de ações para auditoria"""
    # Autenticação
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    REGISTER = "REGISTER"
    
    # Operações financeiras
    PIX_SENT = "PIX_SENT"
    PIX_RECEIVED = "PIX_RECEIVED"
    DEPOSIT = "DEPOSIT"
    ALLOCATION = "ALLOCATION"
    
    # Grafeno
    GRAFENO_WEBHOOK = "GRAFENO_WEBHOOK"
    GRAFENO_ONBOARDING = "GRAFENO_ONBOARDING"
    GRAFENO_TRANSFER = "GRAFENO_TRANSFER"
    
    # Boletos e cobranças
    BOLETO_CREATED = "BOLETO_CREATED"
    BOLETO_REGISTERED = "BOLETO_REGISTERED"
    BOLETO_PAID = "BOLETO_PAID"
    CHARGE_CREATED = "CHARGE_CREATED"
    CHARGE_PAID = "CHARGE_PAID"
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED"
    
    # Admin
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    SETTINGS_CHANGED = "SETTINGS_CHANGED"


class AuditLog(Base):
    """Modelo de log de auditoria"""
    
    __tablename__ = "audit_log"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    uuid = Column(String(36), nullable=False, default=lambda: str(uuid_lib.uuid4()))
    
    # Quem
    user_id = Column(Integer, nullable=True)
    user_email = Column(String(255), nullable=True)
    user_role = Column(String(20), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # O quê
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(String(100), nullable=True)
    
    # Detalhes
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    extra_data = Column("metadata", JSON, nullable=True)
    
    # Quando
    created_at = Column(DateTime, server_default=func.now(), index=True)
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', user_id={self.user_id})>"
