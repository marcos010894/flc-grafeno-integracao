"""
FLC Bank - Router do Painel Master
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import datetime, date
from decimal import Decimal

from app.database import get_db
from app.models.user import User
from app.models.pix import PixIncoming, PixStatus
from app.models.ledger import Allocation, LedgerEntry, DiscountType, EntryType, EntryDirection
from app.models.audit import AuditLog
from app.schemas.ledger import (
    AllocationCreate, AllocationResponse, AllocationSimulation,
    AllocationSimulationResponse, AllocationListResponse,
    CompanyBalanceResponse
)
from app.services.allocation import AllocationService
from app.services.grafeno import GrafenoService
from app.utils.security import get_current_master

router = APIRouter(prefix="/master", tags=["Painel Master"])

# Instância do serviço Grafeno
grafeno_service = GrafenoService()


@router.get("/dashboard")
async def get_dashboard(
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Retorna dados do dashboard do Master.
    """
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    
    # PIX pendentes
    pending = db.query(
        func.count(PixIncoming.id),
        func.coalesce(func.sum(PixIncoming.amount), 0)
    ).filter(PixIncoming.status == PixStatus.PENDING).first()
    
    # PIX alocados hoje
    allocated_today = db.query(
        func.count(Allocation.id),
        func.coalesce(func.sum(Allocation.net_amount), 0),
        func.coalesce(func.sum(Allocation.company_margin), 0)
    ).filter(Allocation.allocated_at >= today_start).first()
    
    # Total geral
    total_margin = db.query(
        func.coalesce(func.sum(Allocation.company_margin), 0)
    ).scalar()
    
    # Usuários ativos
    active_users = db.query(func.count(User.id)).filter(
        User.status == "ACTIVE",
        User.role == "USER"
    ).scalar()
    
    # PIX enviados (débitos - saídas)
    pix_sent = db.query(
        func.count(LedgerEntry.id),
        func.coalesce(func.sum(LedgerEntry.amount), 0)
    ).filter(LedgerEntry.entry_type == EntryType.PIX_DEBIT).first()
    
    # Saldo total de todos os usuários (soma dos saldos finais)
    # Buscar o último lançamento de cada usuário para pegar o balance_after
    from sqlalchemy import text
    total_balance_result = db.execute(text("""
        SELECT COALESCE(SUM(balance_after), 0) as total_balance
        FROM (
            SELECT l1.account_id, l1.balance_after
            FROM ledger_entries l1
            WHERE l1.id = (
                SELECT MAX(l2.id)
                FROM ledger_entries l2
                WHERE l2.account_id = l1.account_id
            )
        ) AS last_entries
    """)).fetchone()
    total_balance = float(total_balance_result[0]) if total_balance_result else 0.0
    
    # Buscar saldo da conta Grafeno
    grafeno_balance = None
    try:
        grafeno_result = await grafeno_service.get_balance()
        if grafeno_result.get("success"):
            grafeno_balance = {
                "current": float(grafeno_result.get("current_balance") or 0),
                "available": float(grafeno_result.get("available_balance") or 0),
                "account": grafeno_result.get("account", "08185935-7")
            }
    except Exception as e:
        pass  # Se falhar, grafeno_balance fica None
    
    return {
        "pending_pix": {
            "count": pending[0] or 0,
            "amount": float(pending[1] or 0)
        },
        "allocated_today": {
            "count": allocated_today[0] or 0,
            "net_amount": float(allocated_today[1] or 0),
            "margin": float(allocated_today[2] or 0)
        },
        "total_margin": float(total_margin or 0),
        "active_users": active_users or 0,
        "pix_sent": {
            "count": pix_sent[0] or 0,
            "amount": float(pix_sent[1] or 0)
        },
        "total_balance": total_balance,
        "grafeno_balance": grafeno_balance,
        "last_update": datetime.utcnow().isoformat()
    }


@router.post("/simulate", response_model=AllocationSimulationResponse)
async def simulate_allocation(
    simulation: AllocationSimulation,
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Simula uma alocação sem persistir.
    Útil para preview antes de confirmar.
    """
    service = AllocationService(db)
    
    try:
        result = service.simulate_allocation(
            pix_uuid=simulation.pix_uuid,
            discount_type=simulation.discount_type,
            discount_value=simulation.discount_value
        )
        return AllocationSimulationResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/allocate", response_model=AllocationResponse)
async def allocate_pix(
    allocation_data: AllocationCreate,
    request: Request,
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Aloca um PIX a um usuário.
    
    Esta é a operação principal do sistema:
    1. Valida o PIX (deve estar PENDING)
    2. Calcula valores com desconto
    3. Cria a alocação
    4. Registra no ledger imutável
    5. Atualiza status do PIX
    """
    service = AllocationService(db)
    
    try:
        allocation, ledger_entry = service.allocate_pix(
            pix_uuid=allocation_data.pix_uuid,
            user_uuid=allocation_data.user_uuid,
            discount_type=allocation_data.discount_type,
            discount_value=allocation_data.discount_value,
            master=current_user,
            notes=allocation_data.notes,
            ip_address=request.client.host if request.client else None
        )
        
        # Montar resposta
        return AllocationResponse(
            uuid=allocation.uuid,
            pix_uuid=allocation.pix.uuid,
            user_uuid=allocation.user.uuid,
            user_name=allocation.user.full_name,
            allocated_by_uuid=current_user.uuid,
            allocated_by_name=current_user.full_name,
            gross_amount=allocation.gross_amount,
            discount_type=allocation.discount_type,
            discount_value=allocation.discount_value,
            discount_amount=allocation.discount_amount,
            net_amount=allocation.net_amount,
            company_margin=allocation.company_margin,
            notes=allocation.notes,
            allocated_at=allocation.allocated_at,
            payer_name=allocation.pix.payer_name,
            payer_cpf_cnpj=allocation.pix.payer_cpf_cnpj,
            transaction_date=allocation.pix.transaction_date
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/allocations", response_model=AllocationListResponse)
async def list_allocations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user_uuid: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Lista todas as alocações realizadas.
    """
    query = db.query(Allocation)
    
    if user_uuid:
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if user:
            query = query.filter(Allocation.user_id == user.id)
    
    if start_date:
        query = query.filter(Allocation.allocated_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(Allocation.allocated_at <= datetime.combine(end_date, datetime.max.time()))
    
    query = query.order_by(Allocation.allocated_at.desc())
    
    total = query.count()
    
    # Totais
    totals = db.query(
        func.coalesce(func.sum(Allocation.gross_amount), 0),
        func.coalesce(func.sum(Allocation.net_amount), 0),
        func.coalesce(func.sum(Allocation.company_margin), 0)
    ).first()
    
    allocations = query.offset((page - 1) * per_page).limit(per_page).all()
    
    result = []
    for a in allocations:
        result.append(AllocationResponse(
            uuid=a.uuid,
            pix_uuid=a.pix.uuid,
            user_uuid=a.user.uuid,
            user_name=a.user.full_name,
            allocated_by_uuid=a.master.uuid,
            allocated_by_name=a.master.full_name,
            gross_amount=a.gross_amount,
            discount_type=a.discount_type,
            discount_value=a.discount_value,
            discount_amount=a.discount_amount,
            net_amount=a.net_amount,
            company_margin=a.company_margin,
            notes=a.notes,
            allocated_at=a.allocated_at,
            payer_name=a.pix.payer_name,
            payer_cpf_cnpj=a.pix.payer_cpf_cnpj,
            transaction_date=a.pix.transaction_date
        ))
    
    return AllocationListResponse(
        allocations=result,
        total=total,
        total_gross=Decimal(str(totals[0])),
        total_net=Decimal(str(totals[1])),
        total_margin=Decimal(str(totals[2])),
        page=page,
        per_page=per_page
    )


@router.get("/company-balance", response_model=CompanyBalanceResponse)
async def get_company_balance(
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Retorna o saldo e estatísticas da empresa.
    """
    # Total PIX recebidos
    pix_stats = db.query(
        func.count(PixIncoming.id),
        func.coalesce(func.sum(PixIncoming.amount), 0)
    ).first()
    
    # Total alocado
    allocation_stats = db.query(
        func.count(Allocation.id),
        func.coalesce(func.sum(Allocation.net_amount), 0),
        func.coalesce(func.sum(Allocation.company_margin), 0)
    ).first()
    
    # Pendente de alocação
    pending = db.query(
        func.coalesce(func.sum(PixIncoming.amount), 0)
    ).filter(PixIncoming.status == PixStatus.PENDING).scalar()
    
    return CompanyBalanceResponse(
        total_pix_received=Decimal(str(pix_stats[1])),
        total_allocated=Decimal(str(allocation_stats[1])),
        total_margin=Decimal(str(allocation_stats[2])),
        pending_allocation=Decimal(str(pending)),
        pix_count=pix_stats[0] or 0,
        allocation_count=allocation_stats[0] or 0,
        last_update=datetime.utcnow()
    )


@router.get("/movements")
async def get_all_movements(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user_uuid: Optional[str] = None,
    entry_type: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Lista todas as movimentações de todos os clientes.
    """
    query = db.query(LedgerEntry).join(User, LedgerEntry.account_id == User.id)
    
    if user_uuid:
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if user:
            query = query.filter(LedgerEntry.account_id == user.id)
    
    if entry_type:
        try:
            entry_type_enum = EntryType(entry_type)
            query = query.filter(LedgerEntry.entry_type == entry_type_enum)
        except ValueError:
            pass
    
    if start_date:
        query = query.filter(LedgerEntry.created_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(LedgerEntry.created_at <= datetime.combine(end_date, datetime.max.time()))
    
    query = query.order_by(LedgerEntry.created_at.desc())
    
    total = query.count()
    
    # Totais
    credit_total = db.query(func.coalesce(func.sum(LedgerEntry.amount), 0)).filter(
        LedgerEntry.direction == EntryDirection.CREDIT
    ).scalar()
    
    debit_total = db.query(func.coalesce(func.sum(LedgerEntry.amount), 0)).filter(
        LedgerEntry.direction == EntryDirection.DEBIT
    ).scalar()
    
    entries = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return {
        "movements": [
            {
                "uuid": entry.uuid,
                "user_uuid": entry.account.uuid,
                "user_name": entry.account.full_name,
                "user_email": entry.account.email,
                "entry_type": entry.entry_type.value if hasattr(entry.entry_type, 'value') else str(entry.entry_type),
                "direction": entry.direction.value if hasattr(entry.direction, 'value') else str(entry.direction),
                "amount": float(entry.amount),
                "balance_after": float(entry.balance_after),
                "description": entry.description,
                "reference_id": entry.reference_id,
                "created_at": entry.created_at.isoformat(),
            }
            for entry in entries
        ],
        "total": total,
        "total_credits": float(credit_total or 0),
        "total_debits": float(debit_total or 0),
        "page": page,
        "per_page": per_page
    }


@router.get("/audit-log")
async def get_audit_log(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    action: Optional[str] = None,
    user_email: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Retorna logs de auditoria.
    """
    query = db.query(AuditLog)
    
    if action:
        query = query.filter(AuditLog.action == action)
    if user_email:
        query = query.filter(AuditLog.user_email.ilike(f"%{user_email}%"))
    if start_date:
        query = query.filter(AuditLog.created_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(AuditLog.created_at <= datetime.combine(end_date, datetime.max.time()))
    
    query = query.order_by(AuditLog.created_at.desc())
    
    total = query.count()
    logs = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return {
        "logs": [
            {
                "uuid": log.uuid,
                "user_email": log.user_email,
                "user_role": log.user_role,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat(),
                "metadata": log.extra_data
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "per_page": per_page
    }


@router.post("/run-migrations")
async def run_migrations(
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Executa migrações SQL manuais para criar tabelas novas.
    APENAS MASTER pode executar.
    """
    from app.database import engine, Base
    from app.models import GrafenoAccount  # Importar o modelo
    from sqlalchemy import text
    
    try:
        # Criar todas as tabelas que não existem
        Base.metadata.create_all(bind=engine)
        
        # Adicionar colunas novas se não existirem
        alter_statements = [
            "ALTER TABLE grafeno_accounts ADD COLUMN IF NOT EXISTS article_of_association_content TEXT",
            "ALTER TABLE grafeno_accounts ADD COLUMN IF NOT EXISTS admin_identity_filename VARCHAR(255)",
            "ALTER TABLE grafeno_accounts ADD COLUMN IF NOT EXISTS admin_identity_content TEXT",
            "ALTER TABLE grafeno_accounts ADD COLUMN IF NOT EXISTS social_capital DECIMAL(15,2)",
        ]
        
        altered_columns = []
        for stmt in alter_statements:
            try:
                db.execute(text(stmt))
                altered_columns.append(stmt.split("ADD COLUMN IF NOT EXISTS ")[1].split(" ")[0])
            except Exception as e:
                # Ignorar erros de coluna já existente
                pass
        
        db.commit()
        
        return {
            "success": True,
            "message": "Migrações executadas com sucesso",
            "tables_checked": list(Base.metadata.tables.keys()),
            "columns_altered": altered_columns
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao executar migrações: {str(e)}"
        )
