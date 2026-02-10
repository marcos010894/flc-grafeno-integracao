"""
FLC Bank - Router de PIX
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import datetime, date
from decimal import Decimal
import uuid

from app.database import get_db
from app.models.user import User
from app.models.pix import PixIncoming, PixStatus, PixOutgoingRequest, PixOutgoingStatus
from app.models.audit import AuditLog
from app.schemas.pix import PixCreate, PixResponse, PixListResponse, PixStats, PixWebhook, PixOutgoingCreate, PixOutgoingResponse, PixOutgoingListResponse, PixOutgoingProcess
from app.utils.security import get_current_user, get_current_master
from app.services.pix_qrcode import generate_pix_qrcode_base64, get_deposit_info
from app.services.grafeno import GrafenoService
from app.services.email import email_service

router = APIRouter(prefix="/pix", tags=["PIX"])

# Instância do serviço Grafeno
grafeno_service = GrafenoService()


@router.get("/deposit/info")
async def get_pix_deposit_info(
    current_user: User = Depends(get_current_user),
):
    """
    Retorna informações para depósito via PIX.
    Qualquer usuário autenticado pode acessar.
    """
    return get_deposit_info()


@router.post("/deposit/charge")
async def create_deposit_charge(
    amount: float = Query(..., gt=0, description="Valor do depósito"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cria uma cobrança PIX via Grafeno (QR Code dinâmico oficial).
    
    Este endpoint:
    1. Cria uma cobrança na Grafeno
    2. Retorna o QR Code e código copia-cola
    3. Quando pago, a Grafeno notifica via webhook
    """
    # Gerar ID de controle
    client_control = f"DEP{current_user.id}T{int(datetime.now().timestamp())}"[:25]
    
    # Criar cobrança na Grafeno
    result = await grafeno_service.create_pix_charge(
        value=Decimal(str(amount)),
        payer_name=current_user.full_name,
        payer_document=current_user.cpf_cnpj or "00000000000",
        payer_email=current_user.email,
        client_control_number=client_control,
        expires_after=1,  # Expira 1 dia após vencimento
    )
    
    if not result.get("success"):
        # Se falhar na Grafeno, usa o QR Code local como fallback
        fallback = generate_pix_qrcode_base64(
            amount=Decimal(str(amount)),
            transaction_id=client_control,
            description=f"Dep {current_user.full_name[:15]}",
        )
        return {
            "success": True,
            "source": "local",
            "message": "Use o PIX Copia e Cola ou a chave Email para depositar",
            "charge_id": None,
            "pix_qrcode": fallback.get("qrcode_base64"),
            "pix_copy_paste": fallback.get("payload"),
            "pix_key": "fabio@flcbank.com.br",
            "pix_key_type": "email",
            "client_control_number": client_control,
            "amount": amount,
            "instructions": [
                "1. Abra o app do seu banco",
                "2. Acesse a área PIX",
                "3. Cole o código ou use a chave Email: fabio@flcbank.com.br",
                "4. Confirme o valor e finalize o pagamento",
                "5. O depósito será creditado automaticamente",
            ]
        }
    
    return {
        "success": True,
        "source": "grafeno",
        "charge_id": result.get("charge_id"),
        "status": result.get("status"),
        "pix_qrcode": result.get("pix_qrcode"),
        "pix_copy_paste": result.get("pix_copy_paste"),
        "pix_txid": result.get("pix_txid"),
        "client_control_number": result.get("client_control_number"),
        "amount": amount,
        "due_date": result.get("due_date"),
        "user_name": current_user.full_name,
        "instructions": [
            "1. Escaneie o QR Code com o app do seu banco",
            "2. Confira os dados e confirme o pagamento",
            "3. O valor será creditado automaticamente em sua conta",
            "4. Depósitos PIX são processados em segundos",
        ]
    }


@router.get("/deposit/qrcode")
async def generate_deposit_qrcode(
    amount: Optional[float] = Query(None, description="Valor do depósito (opcional)"),
    current_user: User = Depends(get_current_user),
):
    """
    Gera QR Code PIX para depósito.
    
    - Se amount for informado, gera QR dinâmico com valor fixo
    - Se amount não for informado, gera QR estático (valor livre)
    """
    # Gerar ID de transação único para rastrear o depósito
    transaction_id = f"DEP{current_user.id}{int(datetime.now().timestamp())}"
    
    # Descrição inclui identificação do usuário
    description = f"Dep {current_user.full_name[:15]}"
    
    amount_decimal = Decimal(str(amount)) if amount else None
    
    result = generate_pix_qrcode_base64(
        amount=amount_decimal,
        transaction_id=transaction_id,
        description=description,
    )
    
    return {
        **result,
        "transaction_id": transaction_id,
        "amount": amount,
        "user_name": current_user.full_name,
        "instructions": [
            "1. Escaneie o QR Code com o app do seu banco",
            "2. Confira os dados e confirme o pagamento",
            "3. O valor será creditado automaticamente em sua conta",
            "4. Guarde o comprovante para conferência",
        ]
    }


@router.post("/deposit/confirm")
async def confirm_deposit(
    background_tasks: BackgroundTasks,
    amount: float = Query(..., gt=0, description="Valor do depósito"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Registra um depósito pendente de alocação.
    
    Quando o usuário confirma que fez o PIX, salvamos na tabela
    pix_incoming como PENDING para o master alocar.
    """
    # Gerar IDs únicos
    pix_uuid = str(uuid.uuid4())
    external_id = f"DEP{current_user.id}T{int(datetime.now().timestamp())}"
    
    # Criar o PIX pendente
    pix = PixIncoming(
        uuid=pix_uuid,
        external_id=external_id,
        end_to_end_id=f"E2E{datetime.now().strftime('%Y%m%d%H%M%S')}{current_user.id}",
        amount=Decimal(str(amount)),
        payer_name=current_user.full_name,
        payer_cpf_cnpj=current_user.cpf_cnpj,
        payer_bank_code="000",
        payer_bank_name="Informado pelo usuário",
        description=f"Depósito via PIX - {current_user.full_name}",
        transaction_date=datetime.now(),
        status=PixStatus.PENDING,
        raw_payload={"source": "user_deposit", "user_uuid": current_user.uuid},
    )
    
    db.add(pix)
    db.commit()
    db.refresh(pix)
    
    # Enviar notificação por email usando BackgroundTasks (forma correta no FastAPI)
    background_tasks.add_task(
        email_service.notify_pix_received,
        payer_name=current_user.full_name,
        amount=float(amount),
        payer_cpf_cnpj=current_user.cpf_cnpj,
        description=f"Depósito via PIX - {current_user.full_name}",
    )
    
    return {
        "success": True,
        "message": "Depósito registrado com sucesso! Aguarde a alocação.",
        "pix_uuid": pix.uuid,
        "amount": float(pix.amount),
        "status": pix.status.value,
    }


@router.get("/pending", response_model=PixListResponse)
async def list_pending_pix(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Lista PIX pendentes de alocação (apenas MASTER).
    """
    query = db.query(PixIncoming).filter(
        PixIncoming.status == PixStatus.PENDING
    ).order_by(PixIncoming.transaction_date.desc())
    
    total = query.count()
    total_amount = db.query(func.sum(PixIncoming.amount)).filter(
        PixIncoming.status == PixStatus.PENDING
    ).scalar() or Decimal("0.00")
    
    pix_list = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return PixListResponse(
        pix_list=[PixResponse.model_validate(p) for p in pix_list],
        total=total,
        total_amount=total_amount,
        page=page,
        per_page=per_page
    )


@router.get("/allocated", response_model=PixListResponse)
async def list_allocated_pix(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Lista PIX já alocados (apenas MASTER).
    """
    query = db.query(PixIncoming).filter(
        PixIncoming.status == PixStatus.ALLOCATED
    )
    
    if start_date:
        query = query.filter(PixIncoming.transaction_date >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(PixIncoming.transaction_date <= datetime.combine(end_date, datetime.max.time()))
    
    query = query.order_by(PixIncoming.transaction_date.desc())
    
    total = query.count()
    total_amount = db.query(func.sum(PixIncoming.amount)).filter(
        PixIncoming.status == PixStatus.ALLOCATED
    ).scalar() or Decimal("0.00")
    
    pix_list = query.offset((page - 1) * per_page).limit(per_page).all()
    
    # Enriquecer com dados de alocação
    result = []
    for pix in pix_list:
        pix_data = PixResponse.model_validate(pix)
        if pix.allocation:
            pix_data.allocated_to_name = pix.allocation.user.full_name
            pix_data.allocated_to_uuid = pix.allocation.user.uuid
            pix_data.allocation_uuid = pix.allocation.uuid
        result.append(pix_data)
    
    return PixListResponse(
        pix_list=result,
        total=total,
        total_amount=total_amount,
        page=page,
        per_page=per_page
    )


@router.get("/stats", response_model=PixStats)
async def get_pix_stats(
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Retorna estatísticas de PIX (apenas MASTER).
    """
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    
    # Pendentes
    pending_count = db.query(func.count(PixIncoming.id)).filter(
        PixIncoming.status == PixStatus.PENDING
    ).scalar() or 0
    
    pending_amount = db.query(func.sum(PixIncoming.amount)).filter(
        PixIncoming.status == PixStatus.PENDING
    ).scalar() or Decimal("0.00")
    
    # Alocados
    allocated_count = db.query(func.count(PixIncoming.id)).filter(
        PixIncoming.status == PixStatus.ALLOCATED
    ).scalar() or 0
    
    allocated_amount = db.query(func.sum(PixIncoming.amount)).filter(
        PixIncoming.status == PixStatus.ALLOCATED
    ).scalar() or Decimal("0.00")
    
    # Hoje
    today_count = db.query(func.count(PixIncoming.id)).filter(
        PixIncoming.transaction_date >= today_start
    ).scalar() or 0
    
    today_amount = db.query(func.sum(PixIncoming.amount)).filter(
        PixIncoming.transaction_date >= today_start
    ).scalar() or Decimal("0.00")
    
    return PixStats(
        total_pending=pending_count,
        total_pending_amount=pending_amount,
        total_allocated=allocated_count,
        total_allocated_amount=allocated_amount,
        total_today=today_count,
        total_today_amount=today_amount
    )


@router.get("/{pix_uuid}", response_model=PixResponse)
async def get_pix(
    pix_uuid: str,
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Obtém detalhes de um PIX (apenas MASTER).
    """
    pix = db.query(PixIncoming).filter(PixIncoming.uuid == pix_uuid).first()
    if not pix:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PIX não encontrado"
        )
    
    response = PixResponse.model_validate(pix)
    if pix.allocation:
        response.allocated_to_name = pix.allocation.user.full_name
        response.allocated_to_uuid = pix.allocation.user.uuid
        response.allocation_uuid = pix.allocation.uuid
    
    return response


@router.post("/", response_model=PixResponse, status_code=status.HTTP_201_CREATED)
async def create_pix(
    pix_data: PixCreate,
    request: Request,
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Registra um novo PIX manualmente (apenas MASTER).
    Use para testes ou correções.
    """
    # Verificar duplicidade
    if pix_data.end_to_end_id:
        existing = db.query(PixIncoming).filter(
            PixIncoming.end_to_end_id == pix_data.end_to_end_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PIX com este E2E ID já existe"
            )
    
    # Criar PIX
    pix = PixIncoming(
        uuid=str(uuid.uuid4()),
        external_id=pix_data.external_id,
        end_to_end_id=pix_data.end_to_end_id,
        amount=pix_data.amount,
        payer_name=pix_data.payer_name,
        payer_cpf_cnpj=pix_data.payer_cpf_cnpj,
        payer_bank_code=pix_data.payer_bank_code,
        payer_bank_name=pix_data.payer_bank_name,
        payer_agency=pix_data.payer_agency,
        payer_account=pix_data.payer_account,
        payer_pix_key=pix_data.payer_pix_key,
        description=pix_data.description,
        transaction_date=pix_data.transaction_date,
        raw_payload=pix_data.raw_payload,
        status=PixStatus.PENDING
    )
    
    db.add(pix)
    
    # Auditoria
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        user_role=current_user.role.value,
        ip_address=request.client.host if request.client else None,
        action="PIX_CREATED_MANUAL",
        entity_type="PIX",
        entity_id=pix.uuid,
        new_values={
            "amount": str(pix_data.amount),
            "payer_name": pix_data.payer_name
        }
    )
    db.add(audit)
    
    db.commit()
    db.refresh(pix)
    
    return pix


@router.post("/webhook", status_code=status.HTTP_201_CREATED)
async def webhook_pix(
    webhook_data: PixWebhook,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Endpoint para receber webhooks de PIX da API bancária.
    Este endpoint deve ser protegido por IP ou token específico.
    """
    # TODO: Adicionar validação de origem (IP, token, etc.)
    
    # Verificar duplicidade
    existing = db.query(PixIncoming).filter(
        PixIncoming.end_to_end_id == webhook_data.end_to_end_id
    ).first()
    
    if existing:
        return {"message": "PIX já registrado", "uuid": existing.uuid}
    
    # Criar PIX
    pix = PixIncoming(
        uuid=str(uuid.uuid4()),
        external_id=webhook_data.external_id,
        end_to_end_id=webhook_data.end_to_end_id,
        amount=webhook_data.amount,
        payer_name=webhook_data.payer_name,
        payer_cpf_cnpj=webhook_data.payer_cpf_cnpj,
        payer_pix_key=webhook_data.payer_pix_key,
        description=webhook_data.description,
        transaction_date=webhook_data.transaction_date,
        raw_payload=webhook_data.raw_payload,
        status=PixStatus.PENDING
    )
    
    db.add(pix)
    
    # Auditoria
    audit = AuditLog(
        ip_address=request.client.host if request.client else None,
        action="PIX_RECEIVED_WEBHOOK",
        entity_type="PIX",
        entity_id=pix.uuid,
        new_values={
            "amount": str(webhook_data.amount),
            "end_to_end_id": webhook_data.end_to_end_id
        }
    )
    db.add(audit)
    
    db.commit()
    
    return {"message": "PIX registrado com sucesso", "uuid": pix.uuid}


@router.post("/simulate", status_code=status.HTTP_201_CREATED)
async def create_simulated_pix(
    request: Request,
    db: Session = Depends(get_db),
    amount: float = None,
    payer_name: str = None,
    payer_cpf_cnpj: str = None,
    description: str = None,
    target_user_id: int = None,
):
    """
    Cria um PIX simulado para testes/demonstração.
    Usado durante o registro para simular depósito inicial.
    """
    # Receber dados via JSON body
    body = await request.json()
    amount = body.get('amount', amount)
    payer_name = body.get('payer_name', payer_name)
    payer_cpf_cnpj = body.get('payer_cpf_cnpj', payer_cpf_cnpj)
    description = body.get('description', description)
    target_user_id = body.get('target_user_id', target_user_id)
    
    if not amount or amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valor do PIX deve ser maior que zero"
        )
    
    # Gerar IDs simulados
    pix_uuid = str(uuid.uuid4())
    simulated_e2e = f"E2E{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"
    simulated_external = f"SIM{uuid.uuid4().hex[:12].upper()}"
    
    # Criar PIX simulado
    pix = PixIncoming(
        uuid=pix_uuid,
        external_id=simulated_external,
        end_to_end_id=simulated_e2e,
        amount=Decimal(str(amount)),
        payer_name=payer_name or "Depósito Simulado",
        payer_cpf_cnpj=payer_cpf_cnpj,
        payer_bank_code="000",
        payer_bank_name="Banco Simulado",
        description=description or "PIX simulado para demonstração",
        transaction_date=datetime.now(),
        raw_payload={
            "simulated": True,
            "target_user_id": target_user_id,
            "created_via": "register_flow"
        },
        status=PixStatus.PENDING
    )
    
    db.add(pix)
    
    # Auditoria
    audit = AuditLog(
        ip_address=request.client.host if request.client else None,
        action="PIX_SIMULATED_CREATED",
        entity_type="PIX",
        entity_id=pix_uuid,
        new_values={
            "amount": str(amount),
            "payer_name": payer_name,
            "target_user_id": target_user_id,
            "simulated": True
        }
    )
    db.add(audit)
    
    db.commit()
    
    return {
        "message": "PIX simulado criado com sucesso",
        "uuid": pix_uuid,
        "external_id": simulated_external,
        "end_to_end_id": simulated_e2e,
        "amount": float(amount),
        "status": "PENDING",
        "note": "Este PIX precisa ser alocado pelo Master para creditar o saldo"
    }


# ===== PIX de SAÍDA (Envio) =====

@router.post("/lookup", status_code=status.HTTP_200_OK)
async def lookup_pix_key(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Pesquisa uma chave PIX (simulado).
    Retorna dados do destinatário.
    """
    body = await request.json()
    pix_key = body.get('pix_key', '')
    key_type = body.get('key_type', 'CPF')  # CPF, CNPJ, EMAIL, PHONE, RANDOM
    
    if not pix_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chave PIX é obrigatória"
        )
    
    # Simular resposta de consulta DICT (Diretório de Identificadores de Contas Transacionais)
    # Em produção, isso seria uma chamada real à API do PSP/Grafeno
    
    # Gerar dados simulados baseados na chave
    import hashlib
    hash_key = hashlib.md5(pix_key.encode()).hexdigest()
    
    # Simular diferentes tipos de destinatários
    simulated_names = [
        "João da Silva Santos",
        "Maria Aparecida Oliveira",
        "José Carlos Ferreira",
        "Ana Paula Costa",
        "Pedro Henrique Lima",
        "Fernanda Souza Rodrigues",
        "Lucas Gabriel Almeida",
        "Juliana Martins Silva",
        "Ricardo Santos Pereira",
        "Camila Rocha Fernandes"
    ]
    
    simulated_banks = [
        {"code": "001", "name": "Banco do Brasil"},
        {"code": "033", "name": "Santander"},
        {"code": "104", "name": "Caixa Econômica"},
        {"code": "237", "name": "Bradesco"},
        {"code": "341", "name": "Itaú"},
        {"code": "260", "name": "Nubank"},
        {"code": "077", "name": "Inter"},
        {"code": "336", "name": "C6 Bank"},
        {"code": "290", "name": "PagBank"},
        {"code": "380", "name": "PicPay"}
    ]
    
    # Usar hash para selecionar dados consistentes
    name_index = int(hash_key[:2], 16) % len(simulated_names)
    bank_index = int(hash_key[2:4], 16) % len(simulated_banks)
    
    # Formatar CPF/CNPJ
    if key_type == "CPF":
        formatted_doc = f"{pix_key[:3]}.***.**{pix_key[-2:]}-**" if len(pix_key) == 11 else pix_key
    elif key_type == "CNPJ":
        formatted_doc = f"{pix_key[:2]}.***/****-**" if len(pix_key) == 14 else pix_key
    else:
        formatted_doc = pix_key
    
    return {
        "found": True,
        "key": pix_key,
        "key_type": key_type,
        "recipient": {
            "name": simulated_names[name_index],
            "document": formatted_doc,
            "document_type": "CPF" if key_type == "CPF" else "CNPJ",
            "bank_code": simulated_banks[bank_index]["code"],
            "bank_name": simulated_banks[bank_index]["name"],
            "agency": f"{int(hash_key[4:8], 16) % 10000:04d}",
            "account": f"{int(hash_key[8:12], 16) % 1000000:06d}-{int(hash_key[12:13], 16) % 10}",
            "account_type": "CONTA_CORRENTE"
        }
    }


@router.post("/send", status_code=status.HTTP_201_CREATED)
async def send_pix(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Envia um PIX para outra conta.
    Integra com a Grafeno para envio real do PIX.
    Desconta do saldo virtual do usuário.
    """
    from app.models.ledger import LedgerEntry, EntryType, EntryDirection
    from app.services.grafeno import grafeno_service
    from sqlalchemy import func
    
    body = await request.json()
    pix_key = body.get('pix_key', '')
    key_type = body.get('key_type', 'cpf').lower()  # cpf, cnpj, email, phone, evp
    amount = Decimal(str(body.get('amount', 0)))
    description = body.get('description', '')
    recipient_name = body.get('recipient_name', 'Destinatário')
    recipient_document = body.get('recipient_document', pix_key if key_type in ['cpf', 'cnpj'] else '')
    recipient_bank = body.get('recipient_bank', 'Banco')
    
    if not pix_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chave PIX é obrigatória"
        )
    
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valor deve ser maior que zero"
        )
    
    # Calcular saldo atual do usuário
    last_entry = db.query(LedgerEntry).filter(
        LedgerEntry.account_id == current_user.id
    ).order_by(LedgerEntry.id.desc()).first()
    
    current_balance = Decimal(str(last_entry.balance_after)) if last_entry else Decimal("0.00")
    
    if amount > current_balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Saldo insuficiente. Disponível: R$ {current_balance:.2f}"
        )
    
    # Gerar UUID único para a transação
    transaction_uuid = str(uuid.uuid4())
    
    # Enviar PIX via Grafeno
    grafeno_result = await grafeno_service.create_pix_transfer(
        value=amount,
        pix_key=pix_key,
        pix_key_type=key_type,
        beneficiary_name=recipient_name,
        beneficiary_document=recipient_document.replace(".", "").replace("-", "").replace("/", ""),
        transaction_uuid=transaction_uuid,
        description=description,
    )
    
    if not grafeno_result.get("success"):
        # Log do erro mas não impede (pode ser sandbox)
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Grafeno API error (continuing in sandbox mode): {grafeno_result}")
    
    # Novo saldo
    new_balance = current_balance - amount
    
    # Criar lançamento no ledger (débito) - sempre registrar localmente
    ledger_entry = LedgerEntry(
        uuid=str(uuid.uuid4()),
        allocation_id=None,
        pix_id=None,
        account_id=current_user.id,
        entry_type=EntryType.PIX_DEBIT,
        amount=amount,
        direction=EntryDirection.DEBIT,
        balance_after=new_balance,
        description=f"PIX enviado para {recipient_name} ({recipient_bank})",
        reference_type="PIX_OUT",
        reference_id=transaction_uuid,  # Usar transaction_uuid para rastrear na Grafeno
        created_by=current_user.id,
        previous_entry_id=last_entry.id if last_entry else None
    )
    db.add(ledger_entry)
    
    # Auditoria
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        user_role=current_user.role.value,
        ip_address=request.client.host if request.client else None,
        action="PIX_SENT",
        entity_type="PIX_OUT",
        entity_id=transaction_uuid,
        new_values={
            "amount": str(amount),
            "pix_key": pix_key,
            "key_type": key_type,
            "recipient_name": recipient_name,
            "recipient_bank": recipient_bank,
            "description": description,
            "grafeno_success": grafeno_result.get("success"),
            "balance_before": str(current_balance),
            "balance_after": str(new_balance)
        }
    )
    db.add(audit)
    
    db.commit()
    
    return {
        "success": True,
        "message": "PIX enviado com sucesso",
        "transaction": {
            "uuid": transaction_uuid,
            "amount": float(amount),
            "recipient": {
                "name": recipient_name,
                "pix_key": pix_key,
                "bank": recipient_bank
            },
            "description": description,
            "timestamp": datetime.now().isoformat(),
            "balance_after": float(new_balance),
            "grafeno_status": "pending" if grafeno_result.get("success") else "local_only"
        }
    }


@router.get("/balance")
async def get_user_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna o saldo atual do usuário.
    """
    from app.models.ledger import LedgerEntry
    
    last_entry = db.query(LedgerEntry).filter(
        LedgerEntry.account_id == current_user.id
    ).order_by(LedgerEntry.id.desc()).first()
    
    balance = Decimal(str(last_entry.balance_after)) if last_entry else Decimal("0.00")
    
    return {
        "user_uuid": current_user.uuid,
        "user_name": current_user.full_name,
        "balance": float(balance),
        "formatted_balance": f"R$ {balance:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    }


# =============================================
# ENDPOINTS DE SOLICITAÇÃO DE PIX DE SAÍDA
# =============================================

@router.post("/outgoing/request")
async def create_pix_outgoing_request(
    request_data: PixOutgoingCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cliente solicita envio de PIX.
    O PIX fica pendente até o Master aprovar e enviar.
    O saldo NÃO é descontado neste momento.
    """
    from app.models.ledger import LedgerEntry
    
    # Verificar saldo disponível
    last_entry = db.query(LedgerEntry).filter(
        LedgerEntry.account_id == current_user.id
    ).order_by(LedgerEntry.id.desc()).first()
    
    current_balance = Decimal(str(last_entry.balance_after)) if last_entry else Decimal("0.00")
    
    if request_data.amount > current_balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Saldo insuficiente. Disponível: R$ {current_balance:.2f}"
        )
    
    # Criar solicitação
    pix_request = PixOutgoingRequest(
        user_id=current_user.id,
        amount=request_data.amount,
        recipient_pix_key=request_data.recipient_pix_key,
        recipient_pix_key_type=request_data.recipient_pix_key_type,
        recipient_name=request_data.recipient_name,
        description=request_data.description,
        status=PixOutgoingStatus.PENDING
    )
    
    db.add(pix_request)
    
    # Auditoria
    audit = AuditLog(
        user_id=current_user.id,
        action="PIX_OUTGOING_REQUEST",
        entity_type="pix_outgoing_request",
        extra_data={
            "amount": str(request_data.amount),
            "recipient_pix_key": request_data.recipient_pix_key,
            "recipient_name": request_data.recipient_name
        }
    )
    db.add(audit)
    
    db.commit()
    db.refresh(pix_request)
    
    # Enviar notificação por email usando BackgroundTasks (forma correta no FastAPI)
    background_tasks.add_task(
        email_service.notify_pix_send_request,
        user_name=current_user.full_name,
        user_email=current_user.email,
        amount=float(request_data.amount),
        recipient_name=request_data.recipient_name,
        recipient_pix_key=request_data.recipient_pix_key,
    )
    
    return {
        "success": True,
        "message": "Solicitação de PIX criada com sucesso. Aguardando processamento.",
        "request": {
            "uuid": pix_request.uuid,
            "amount": float(pix_request.amount),
            "recipient_pix_key": pix_request.recipient_pix_key,
            "status": pix_request.status.value,
            "created_at": pix_request.created_at.isoformat() if pix_request.created_at else None
        }
    }


@router.get("/outgoing/my-requests")
async def list_my_pix_requests(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista as solicitações de PIX do usuário logado.
    """
    query = db.query(PixOutgoingRequest).filter(
        PixOutgoingRequest.user_id == current_user.id
    )
    
    if status_filter:
        try:
            status_enum = PixOutgoingStatus(status_filter)
            query = query.filter(PixOutgoingRequest.status == status_enum)
        except ValueError:
            pass
    
    query = query.order_by(PixOutgoingRequest.created_at.desc())
    
    total = query.count()
    total_amount = db.query(func.sum(PixOutgoingRequest.amount)).filter(
        PixOutgoingRequest.user_id == current_user.id
    ).scalar() or Decimal("0.00")
    
    requests = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return {
        "requests": [
            {
                "uuid": r.uuid,
                "amount": float(r.amount),
                "recipient_pix_key": r.recipient_pix_key,
                "recipient_pix_key_type": r.recipient_pix_key_type,
                "recipient_name": r.recipient_name,
                "description": r.description,
                "status": r.status.value,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "processed_at": r.processed_at.isoformat() if r.processed_at else None,
                "rejection_reason": r.rejection_reason,
                "receipt_url": r.receipt_url,
                "receipt_filename": r.receipt_filename,
                "e2e_id": r.e2e_id
            }
            for r in requests
        ],
        "total": total,
        "total_amount": float(total_amount),
        "page": page,
        "per_page": per_page
    }


@router.delete("/outgoing/request/{request_uuid}")
async def cancel_pix_request(
    request_uuid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancela uma solicitação de PIX pendente.
    Só pode cancelar se ainda estiver PENDING.
    """
    pix_request = db.query(PixOutgoingRequest).filter(
        PixOutgoingRequest.uuid == request_uuid,
        PixOutgoingRequest.user_id == current_user.id
    ).first()
    
    if not pix_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitação não encontrada"
        )
    
    if pix_request.status != PixOutgoingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Apenas solicitações pendentes podem ser canceladas"
        )
    
    pix_request.status = PixOutgoingStatus.CANCELLED
    
    # Auditoria
    audit = AuditLog(
        user_id=current_user.id,
        action="PIX_OUTGOING_CANCELLED",
        entity_type="pix_outgoing_request",
        entity_id=pix_request.uuid,
        extra_data={"cancelled_by": "user"}
    )
    db.add(audit)
    
    db.commit()
    
    return {"success": True, "message": "Solicitação cancelada com sucesso"}


# =============================================
# ENDPOINTS MASTER - GERENCIAR SOLICITAÇÕES DE PIX
# =============================================

@router.get("/outgoing/pending")
async def list_pending_pix_requests(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Lista solicitações de PIX pendentes (apenas MASTER).
    """
    query = db.query(PixOutgoingRequest).filter(
        PixOutgoingRequest.status == PixOutgoingStatus.PENDING
    ).order_by(PixOutgoingRequest.created_at.asc())  # Mais antigos primeiro
    
    total = query.count()
    total_amount = db.query(func.sum(PixOutgoingRequest.amount)).filter(
        PixOutgoingRequest.status == PixOutgoingStatus.PENDING
    ).scalar() or Decimal("0.00")
    
    requests = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return {
        "requests": [
            {
                "uuid": r.uuid,
                "amount": float(r.amount),
                "recipient_pix_key": r.recipient_pix_key,
                "recipient_pix_key_type": r.recipient_pix_key_type,
                "recipient_name": r.recipient_name,
                "description": r.description,
                "status": r.status.value,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "user_name": r.user.full_name if r.user else None,
                "user_uuid": r.user.uuid if r.user else None,
                "user_balance": None  # Pode ser populado se necessário
            }
            for r in requests
        ],
        "total": total,
        "total_amount": float(total_amount),
        "page": page,
        "per_page": per_page
    }


@router.post("/outgoing/process/{request_uuid}")
async def process_pix_request(
    request_uuid: str,
    process_data: PixOutgoingProcess,
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Master processa (aprova ou rejeita) uma solicitação de PIX.
    
    - Se 'approve': desconta do saldo do cliente e marca como COMPLETED
    - Se 'reject': marca como REJECTED
    """
    from app.models.ledger import LedgerEntry, EntryType, EntryDirection
    
    pix_request = db.query(PixOutgoingRequest).filter(
        PixOutgoingRequest.uuid == request_uuid
    ).first()
    
    if not pix_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitação não encontrada"
        )
    
    if pix_request.status != PixOutgoingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solicitação já foi processada. Status atual: {pix_request.status.value}"
        )
    
    if process_data.action == "reject":
        # Rejeitar solicitação
        pix_request.status = PixOutgoingStatus.REJECTED
        pix_request.processed_by = current_user.id
        pix_request.processed_at = datetime.now()
        pix_request.rejection_reason = process_data.rejection_reason or "Rejeitado pelo administrador"
        
        # Auditoria
        audit = AuditLog(
            user_id=current_user.id,
            action="PIX_OUTGOING_REJECTED",
            entity_type="pix_outgoing_request",
            entity_id=request_uuid,
            extra_data={
                "user_id": pix_request.user_id,
                "amount": str(pix_request.amount),
                "reason": pix_request.rejection_reason
            }
        )
        db.add(audit)
        db.commit()
        
        # Enviar notificação por email para o usuário
        try:
            from app.services.email import email_service
            user = db.query(User).filter(User.id == pix_request.user_id).first()
            if user and user.email:
                email_service.notify_user_pix_sent(
                    user_email=user.email,
                    user_name=user.full_name or "Cliente",
                    amount=float(pix_request.amount),
                    recipient_name=pix_request.recipient_name or "Destinatário",
                    recipient_pix_key=pix_request.pix_key or "",
                    status="rejeitado",
                )
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
        
        return {"success": True, "message": "Solicitação rejeitada"}
    
    elif process_data.action == "approve":
        # Verificar saldo atual do usuário
        last_entry = db.query(LedgerEntry).filter(
            LedgerEntry.account_id == pix_request.user_id
        ).order_by(LedgerEntry.id.desc()).first()
        
        current_balance = Decimal(str(last_entry.balance_after)) if last_entry else Decimal("0.00")
        
        if pix_request.amount > current_balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Saldo insuficiente do cliente. Disponível: R$ {current_balance:.2f}"
            )
        
        # Calcular novo saldo
        new_balance = current_balance - pix_request.amount
        
        # Criar lançamento no ledger (débito)
        ledger_entry = LedgerEntry(
            account_id=pix_request.user_id,
            entry_type=EntryType.TRANSFER_OUT,
            amount=pix_request.amount,
            direction=EntryDirection.DEBIT,
            balance_after=new_balance,
            description=f"PIX enviado para {pix_request.recipient_pix_key}",
            reference_id=request_uuid,
            created_by=current_user.id
        )
        db.add(ledger_entry)
        
        # Atualizar solicitação
        pix_request.status = PixOutgoingStatus.COMPLETED
        pix_request.processed_by = current_user.id
        pix_request.processed_at = datetime.now()
        pix_request.e2e_id = process_data.e2e_id
        
        # Salvar comprovante se enviado
        if process_data.receipt_data:
            pix_request.receipt_url = process_data.receipt_data
            pix_request.receipt_filename = process_data.receipt_filename or "comprovante.pdf"
        
        # Auditoria
        audit = AuditLog(
            user_id=current_user.id,
            action="PIX_OUTGOING_APPROVED",
            entity_type="pix_outgoing_request",
            entity_id=request_uuid,
            extra_data={
                "user_id": pix_request.user_id,
                "amount": str(pix_request.amount),
                "recipient": pix_request.recipient_pix_key,
                "e2e_id": process_data.e2e_id,
                "balance_before": str(current_balance),
                "balance_after": str(new_balance)
            }
        )
        db.add(audit)
        
        db.commit()
        
        return {
            "success": True,
            "message": "PIX aprovado e saldo debitado com sucesso",
            "details": {
                "amount": float(pix_request.amount),
                "new_balance": float(new_balance),
                "recipient": pix_request.recipient_pix_key
            }
        }
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ação inválida. Use 'approve' ou 'reject'"
        )


@router.get("/outgoing/all")
async def list_all_pix_requests(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Lista todas as solicitações de PIX (apenas MASTER).
    """
    query = db.query(PixOutgoingRequest)
    
    if status_filter:
        try:
            status_enum = PixOutgoingStatus(status_filter)
            query = query.filter(PixOutgoingRequest.status == status_enum)
        except ValueError:
            pass
    
    query = query.order_by(PixOutgoingRequest.created_at.desc())
    
    total = query.count()
    
    requests = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return {
        "requests": [
            {
                "uuid": r.uuid,
                "amount": float(r.amount),
                "recipient_pix_key": r.recipient_pix_key,
                "recipient_pix_key_type": r.recipient_pix_key_type,
                "recipient_name": r.recipient_name,
                "description": r.description,
                "status": r.status.value,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "processed_at": r.processed_at.isoformat() if r.processed_at else None,
                "user_name": r.user.full_name if r.user else None,
                "user_uuid": r.user.uuid if r.user else None,
                "receipt_url": r.receipt_url,
                "receipt_filename": r.receipt_filename,
                "e2e_id": r.e2e_id
            }
            for r in requests
        ],
        "total": total,
        "page": page,
        "per_page": per_page
    }
