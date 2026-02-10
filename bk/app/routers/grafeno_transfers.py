"""
Endpoint para aprovação automática de transferências PIX pendentes
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from decimal import Decimal
from typing import Optional

from app.database import get_db
from app.models import User
from app.utils.security import get_current_user
from app.services.grafeno import GrafenoService

router = APIRouter(prefix="/grafeno/transfers", tags=["Grafeno Transfers"])


@router.post("/auto-approve")
async def auto_approve_transfers(
    max_value: Optional[float] = Query(None, description="Valor máximo para aprovação automática"),
    approve_all: bool = Query(False, description="Aprovar todas independente do valor"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Aprova automaticamente transferências PIX pendentes.
    
    Regras de negócio:
    - Se approve_all=True: Aprova todas as transferências pendentes
    - Se max_value definido: Aprova apenas transferências até esse valor
    - Padrão: Aprova transferências até R$ 10.000
    """
    grafeno = GrafenoService()
    
    max_value_decimal = Decimal(str(max_value)) if max_value else None
    
    result = await grafeno.auto_approve_pending_transfers(
        max_value=max_value_decimal,
        auto_approve_all=approve_all
    )
    
    return result


@router.get("/pending")
async def list_pending_transfers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista todas as transferências pendentes de aprovação."""
    grafeno = GrafenoService()
    result = await grafeno.list_pending_transfers()
    return result


@router.patch("/{api_partner_transaction_uuid}/approve")
async def approve_transfer(
    api_partner_transaction_uuid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aprova uma transferência específica."""
    grafeno = GrafenoService()
    result = await grafeno.approve_transfer(api_partner_transaction_uuid)
    return result


@router.patch("/{api_partner_transaction_uuid}/reject")
async def reject_transfer(
    api_partner_transaction_uuid: str,
    reason: str = Query("", description="Motivo da rejeição"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rejeita uma transferência específica."""
    grafeno = GrafenoService()
    result = await grafeno.reject_transfer(api_partner_transaction_uuid, reason)
    return result
