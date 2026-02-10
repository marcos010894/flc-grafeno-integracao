"""
FLC Bank - Router de Ledger e Extrato
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import datetime, date
from decimal import Decimal

from app.database import get_db
from app.models.user import User
from app.models.ledger import LedgerEntry, Allocation, EntryDirection
from app.schemas.ledger import (
    LedgerEntryResponse, LedgerListResponse, BalanceResponse,
    ExtractItem, ExtractResponse
)
from app.services.allocation import AllocationService
from app.services.statement_pdf import statement_pdf_generator
from app.utils.security import get_current_user, get_current_master

router = APIRouter(prefix="/ledger", tags=["Ledger e Extrato"])


@router.get("/balance", response_model=BalanceResponse)
async def get_my_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna o saldo do usuário autenticado.
    Saldo calculado a partir do ledger (fonte da verdade).
    """
    service = AllocationService(db)
    balance = service.get_user_balance(current_user.id)
    
    # Totais
    totals = db.query(
        func.coalesce(func.sum(
            func.if_(
                LedgerEntry.direction == EntryDirection.CREDIT,
                LedgerEntry.amount,
                0
            )
        ), 0),
        func.coalesce(func.sum(
            func.if_(
                LedgerEntry.direction == EntryDirection.DEBIT,
                LedgerEntry.amount,
                0
            )
        ), 0)
    ).filter(LedgerEntry.account_id == current_user.id).first()
    
    return BalanceResponse(
        user_uuid=current_user.uuid,
        user_name=current_user.full_name,
        available_balance=balance,
        total_received=Decimal(str(totals[0])),
        total_withdrawn=Decimal(str(totals[1])),
        pending_withdrawals=Decimal("0.00"),
        last_update=datetime.utcnow()
    )


@router.get("/balance/{user_uuid}", response_model=BalanceResponse)
async def get_user_balance(
    user_uuid: str,
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Retorna o saldo de um usuário específico (apenas MASTER).
    """
    user = db.query(User).filter(User.uuid == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    service = AllocationService(db)
    balance = service.get_user_balance(user.id)
    
    # Totais
    totals = db.query(
        func.coalesce(func.sum(
            func.if_(
                LedgerEntry.direction == EntryDirection.CREDIT,
                LedgerEntry.amount,
                0
            )
        ), 0),
        func.coalesce(func.sum(
            func.if_(
                LedgerEntry.direction == EntryDirection.DEBIT,
                LedgerEntry.amount,
                0
            )
        ), 0)
    ).filter(LedgerEntry.account_id == user.id).first()
    
    return BalanceResponse(
        user_uuid=user.uuid,
        user_name=user.full_name,
        available_balance=balance,
        total_received=Decimal(str(totals[0])),
        total_withdrawn=Decimal(str(totals[1])),
        pending_withdrawals=Decimal("0.00"),
        last_update=datetime.utcnow()
    )


@router.get("/entries", response_model=LedgerListResponse)
async def get_my_entries(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna os lançamentos do usuário autenticado.
    """
    query = db.query(LedgerEntry).filter(
        LedgerEntry.account_id == current_user.id
    )
    
    if start_date:
        query = query.filter(LedgerEntry.created_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(LedgerEntry.created_at <= datetime.combine(end_date, datetime.max.time()))
    
    query = query.order_by(LedgerEntry.created_at.desc())
    
    total = query.count()
    entries = query.offset((page - 1) * per_page).limit(per_page).all()
    
    result = []
    for entry in entries:
        result.append(LedgerEntryResponse(
            uuid=entry.uuid,
            entry_type=entry.entry_type,
            amount=entry.amount,
            direction=entry.direction,
            balance_after=entry.balance_after,
            description=entry.description,
            created_at=entry.created_at,
            pix_uuid=entry.pix.uuid if entry.pix else None,
            allocation_uuid=entry.allocation.uuid if entry.allocation else None,
            payer_name=entry.pix.payer_name if entry.pix else None
        ))
    
    return LedgerListResponse(
        entries=result,
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/extract", response_model=ExtractResponse)
async def get_my_extract(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna extrato completo do usuário autenticado.
    """
    # Definir período padrão (últimos 30 dias)
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = date(end_date.year, end_date.month, 1)
    
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Buscar saldo inicial (antes do período)
    opening_entry = db.query(LedgerEntry).filter(
        LedgerEntry.account_id == current_user.id,
        LedgerEntry.created_at < start_datetime
    ).order_by(LedgerEntry.id.desc()).first()
    
    opening_balance = Decimal(str(opening_entry.balance_after)) if opening_entry else Decimal("0.00")
    
    # Buscar lançamentos do período
    entries = db.query(LedgerEntry).filter(
        LedgerEntry.account_id == current_user.id,
        LedgerEntry.created_at >= start_datetime,
        LedgerEntry.created_at <= end_datetime
    ).order_by(LedgerEntry.created_at.asc()).all()
    
    # Processar lançamentos
    extract_items = []
    total_credits = Decimal("0.00")
    total_debits = Decimal("0.00")
    closing_balance = opening_balance
    
    for entry in entries:
        if entry.direction == EntryDirection.CREDIT:
            total_credits += entry.amount
        else:
            total_debits += entry.amount
        
        closing_balance = entry.balance_after
        
        # Buscar dados adicionais da alocação
        gross_amount = None
        discount_amount = None
        if entry.allocation:
            gross_amount = entry.allocation.gross_amount
            discount_amount = entry.allocation.discount_amount
        
        extract_items.append(ExtractItem(
            date=entry.created_at,
            description=entry.description or entry.entry_type.value,
            type=entry.entry_type,
            direction=entry.direction,
            gross_amount=gross_amount,
            discount_amount=discount_amount,
            net_amount=entry.amount,
            balance=entry.balance_after,
            payer_name=entry.pix.payer_name if entry.pix else None
        ))
    
    return ExtractResponse(
        user_uuid=current_user.uuid,
        user_name=current_user.full_name,
        period_start=start_datetime,
        period_end=end_datetime,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        total_credits=total_credits,
        total_debits=total_debits,
        entries=extract_items
    )


@router.get("/allocations")
async def get_my_allocations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna as alocações recebidas pelo usuário autenticado.
    Mostra bruto, desconto e líquido.
    """
    query = db.query(Allocation).filter(
        Allocation.user_id == current_user.id
    ).order_by(Allocation.allocated_at.desc())
    
    total = query.count()
    allocations = query.offset((page - 1) * per_page).limit(per_page).all()
    
    result = []
    for a in allocations:
        result.append({
            "uuid": a.uuid,
            "pix_uuid": a.pix.uuid,
            "gross_amount": float(a.gross_amount),
            "discount_amount": float(a.discount_amount),
            "discount_percentage": a.discount_percentage,
            "net_amount": float(a.net_amount),
            "payer_name": a.pix.payer_name,
            "payer_cpf_cnpj": a.pix.payer_cpf_cnpj,
            "transaction_date": a.pix.transaction_date.isoformat(),
            "allocated_at": a.allocated_at.isoformat(),
            "notes": a.notes
        })
    
    # Totais
    totals = db.query(
        func.coalesce(func.sum(Allocation.gross_amount), 0),
        func.coalesce(func.sum(Allocation.discount_amount), 0),
        func.coalesce(func.sum(Allocation.net_amount), 0)
    ).filter(Allocation.user_id == current_user.id).first()
    
    return {
        "allocations": result,
        "total": total,
        "total_gross": float(totals[0]),
        "total_discount": float(totals[1]),
        "total_net": float(totals[2]),
        "page": page,
        "per_page": per_page
    }


@router.get("/extract/pdf")
async def get_extract_pdf(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Gera extrato em PDF do usuário autenticado.
    """
    # Definir período padrão (últimos 30 dias)
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = date(end_date.year, end_date.month, 1)
    
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Buscar lançamentos do período
    entries = db.query(LedgerEntry).filter(
        LedgerEntry.account_id == current_user.id,
        LedgerEntry.created_at >= start_datetime,
        LedgerEntry.created_at <= end_datetime
    ).order_by(LedgerEntry.created_at.desc()).all()
    
    # Calcular saldo atual
    service = AllocationService(db)
    balance = service.get_user_balance(current_user.id)
    
    # Converter para lista de dicts
    entries_list = []
    for entry in entries:
        # Melhorar descrição para saídas
        description = entry.description or entry.entry_type.value
        if entry.direction == EntryDirection.DEBIT:
            if entry.pix:
                description = f"PIX para {entry.pix.payer_name or 'Destinatário'}"
            elif 'PIX' in str(entry.entry_type):
                description = f"Saída PIX - {description}"
        elif entry.direction == EntryDirection.CREDIT:
            if entry.pix:
                description = f"PIX de {entry.pix.payer_name or 'Pagador'}"
        
        entries_list.append({
            'created_at': entry.created_at,
            'description': description,
            'entry_type': entry.entry_type.value,
            'amount': entry.amount,
            'direction': entry.direction.value,
            'balance_after': entry.balance_after,
        })
    
    # Gerar PDF
    pdf_bytes = statement_pdf_generator.generate(
        user_name=current_user.full_name,
        user_email=current_user.email,
        user_cpf_cnpj=current_user.cpf_cnpj,
        entries=entries_list,
        balance=balance,
        start_date=start_date,
        end_date=end_date,
    )
    
    # Retornar PDF
    filename = f"extrato_flcbank_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )
