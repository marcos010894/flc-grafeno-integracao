"""
FLC Bank - Serviço de Alocação
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid

from app.models.pix import PixIncoming, PixStatus
from app.models.ledger import Allocation, LedgerEntry, DiscountType, EntryType, EntryDirection
from app.models.user import User
from app.models.audit import AuditLog


class AllocationService:
    """Serviço para gerenciamento de alocações de PIX"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def simulate_allocation(
        self,
        pix_uuid: str,
        discount_type: DiscountType,
        discount_value: Decimal
    ) -> dict:
        """
        Simula uma alocação sem persistir
        Retorna os valores calculados
        """
        # Buscar PIX
        pix = self.db.query(PixIncoming).filter(PixIncoming.uuid == pix_uuid).first()
        if not pix:
            raise ValueError("PIX não encontrado")
        
        if not pix.is_pending:
            raise ValueError("PIX já foi alocado ou cancelado")
        
        gross_amount = Decimal(str(pix.amount))
        
        # Calcular desconto
        if discount_type == DiscountType.PERCENTAGE:
            discount_amount = (gross_amount * discount_value / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            discount_amount = discount_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # Validar
        if discount_amount > gross_amount:
            raise ValueError("Desconto não pode ser maior que o valor do PIX")
        
        net_amount = gross_amount - discount_amount
        company_margin = discount_amount
        
        # Calcular percentual efetivo
        discount_percentage = float(discount_amount / gross_amount * 100) if gross_amount > 0 else 0
        
        return {
            "gross_amount": gross_amount,
            "discount_type": discount_type,
            "discount_value": discount_value,
            "discount_amount": discount_amount,
            "net_amount": net_amount,
            "company_margin": company_margin,
            "discount_percentage": round(discount_percentage, 2)
        }
    
    def allocate_pix(
        self,
        pix_uuid: str,
        user_uuid: str,
        discount_type: DiscountType,
        discount_value: Decimal,
        master: User,
        notes: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Tuple[Allocation, LedgerEntry]:
        """
        Aloca um PIX a um usuário.
        
        Esta operação:
        1. Valida o PIX e usuário
        2. Calcula valores
        3. Cria a alocação
        4. Cria lançamento no ledger
        5. Atualiza status do PIX
        6. Registra auditoria
        
        Tudo em uma transação atômica.
        """
        # 1. Buscar e bloquear o PIX (FOR UPDATE)
        pix = self.db.query(PixIncoming).filter(
            PixIncoming.uuid == pix_uuid
        ).with_for_update().first()
        
        if not pix:
            raise ValueError("PIX não encontrado")
        
        if not pix.is_pending:
            raise ValueError("PIX já foi alocado ou está cancelado")
        
        # 2. Buscar usuário destino
        user = self.db.query(User).filter(
            User.uuid == user_uuid,
            User.status == "ACTIVE",
            User.role == "USER"
        ).first()
        
        if not user:
            raise ValueError("Usuário não encontrado ou inativo")
        
        # 3. Simular para obter valores
        simulation = self.simulate_allocation(pix_uuid, discount_type, discount_value)
        
        # 4. Criar alocação
        allocation = Allocation(
            uuid=str(uuid.uuid4()),
            pix_id=pix.id,
            user_id=user.id,
            allocated_by=master.id,
            gross_amount=simulation["gross_amount"],
            discount_type=discount_type,
            discount_value=discount_value,
            discount_amount=simulation["discount_amount"],
            net_amount=simulation["net_amount"],
            company_margin=simulation["company_margin"],
            notes=notes
        )
        self.db.add(allocation)
        self.db.flush()  # Para obter o ID
        
        # 5. Buscar último saldo do usuário
        last_entry = self.db.query(LedgerEntry).filter(
            LedgerEntry.account_id == user.id
        ).order_by(LedgerEntry.id.desc()).first()
        
        last_balance = Decimal(str(last_entry.balance_after)) if last_entry else Decimal("0.00")
        new_balance = last_balance + simulation["net_amount"]
        
        # 6. Criar lançamento no ledger
        ledger_entry = LedgerEntry(
            uuid=str(uuid.uuid4()),
            allocation_id=allocation.id,
            pix_id=pix.id,
            account_id=user.id,
            entry_type=EntryType.PIX_CREDIT,
            amount=simulation["net_amount"],
            direction=EntryDirection.CREDIT,
            balance_after=new_balance,
            description=f"PIX recebido de {pix.payer_name or 'N/I'} - Valor líquido",
            reference_type="PIX",
            reference_id=pix_uuid,
            created_by=master.id,
            previous_entry_id=last_entry.id if last_entry else None
        )
        self.db.add(ledger_entry)
        
        # 7. Atualizar status do PIX
        pix.status = PixStatus.ALLOCATED
        pix.allocation_id = allocation.id
        
        # 8. Registrar auditoria
        audit = AuditLog(
            user_id=master.id,
            user_email=master.email,
            user_role=master.role.value,
            ip_address=ip_address,
            action="PIX_ALLOCATED",
            entity_type="ALLOCATION",
            entity_id=allocation.uuid,
            new_values={
                "pix_uuid": pix_uuid,
                "user_uuid": user_uuid,
                "gross_amount": str(simulation["gross_amount"]),
                "discount_type": discount_type.value,
                "discount_value": str(discount_value),
                "discount_amount": str(simulation["discount_amount"]),
                "net_amount": str(simulation["net_amount"]),
                "company_margin": str(simulation["company_margin"])
            }
        )
        self.db.add(audit)
        
        # 9. Commit
        self.db.commit()
        self.db.refresh(allocation)
        self.db.refresh(ledger_entry)
        
        return allocation, ledger_entry
    
    def get_pending_pix(self, page: int = 1, per_page: int = 20) -> Tuple[list, int, Decimal]:
        """Lista PIX pendentes de alocação"""
        query = self.db.query(PixIncoming).filter(
            PixIncoming.status == PixStatus.PENDING
        ).order_by(PixIncoming.transaction_date.desc())
        
        total = query.count()
        total_amount = self.db.query(func.sum(PixIncoming.amount)).filter(
            PixIncoming.status == PixStatus.PENDING
        ).scalar() or Decimal("0.00")
        
        pix_list = query.offset((page - 1) * per_page).limit(per_page).all()
        
        return pix_list, total, total_amount
    
    def get_allocations(
        self,
        user_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[list, int]:
        """Lista alocações"""
        query = self.db.query(Allocation)
        
        if user_id:
            query = query.filter(Allocation.user_id == user_id)
        
        query = query.order_by(Allocation.allocated_at.desc())
        
        total = query.count()
        allocations = query.offset((page - 1) * per_page).limit(per_page).all()
        
        return allocations, total
    
    def get_user_balance(self, user_id: int) -> Decimal:
        """Calcula saldo atual do usuário baseado no último lançamento do ledger"""
        # Pegar o último lançamento do usuário (que tem o saldo atualizado)
        last_entry = self.db.query(LedgerEntry).filter(
            LedgerEntry.account_id == user_id
        ).order_by(LedgerEntry.id.desc()).first()
        
        return Decimal(str(last_entry.balance_after)) if last_entry else Decimal("0.00")
    
    def get_user_extract(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        per_page: int = 50
    ) -> Tuple[list, int]:
        """Obtém extrato do usuário"""
        query = self.db.query(LedgerEntry).filter(
            LedgerEntry.account_id == user_id
        )
        
        if start_date:
            query = query.filter(LedgerEntry.created_at >= start_date)
        if end_date:
            query = query.filter(LedgerEntry.created_at <= end_date)
        
        query = query.order_by(LedgerEntry.created_at.desc())
        
        total = query.count()
        entries = query.offset((page - 1) * per_page).limit(per_page).all()
        
        return entries, total
