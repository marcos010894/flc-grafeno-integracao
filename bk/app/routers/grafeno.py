"""
FLC Bank - Router para Webhooks Grafeno
Recebe notificações de PIX recebidos, boletos, cobranças e pagamentos
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from decimal import Decimal
import logging
import json

from app.database import get_db
from app.models.user import User
from app.models.pix import PixIncoming, PixStatus
from app.models.ledger import LedgerEntry, EntryType, EntryDirection
from app.models.audit import AuditLog, ActionType
from app.services.grafeno import grafeno_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/grafeno", tags=["Grafeno Webhooks"])


# =====================================================
# WEBHOOK EVENTS - Eventos que a Grafeno envia
# =====================================================
# Boletos:
#   - boleto-criado: boleto criado com sucesso
#   - boleto-registrado: boleto registrado no banco
#
# Cobranças:
#   - cobranca-criada: cobrança PIX criada
#   - paid: cobrança paga
#   - paid_externally: baixa de cobrança
#   - boleto-falha-registro: falha no registro do boleto
#
# Pagamentos:
#   - pagamento-recebido: pagamento recebido na conta
#
# Transferências:
#   - confirmation: confirmação de criação
#   - status-alterado: mudança de status
#
# PIX:
#   - pix_entry / pix-recebido: PIX recebido
# =====================================================


@router.post("/webhook")
async def grafeno_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook para receber notificações da Grafeno.
    
    Tipos de notificação:
    - confirmation: Confirmação de criação de transferência
    - status-alterado: Mudança de status de transferência
    - pix_entry: PIX recebido na conta
    - boleto-criado: Boleto criado com sucesso
    - boleto-registrado: Boleto registrado no banco
    - cobranca-criada: Cobrança PIX criada
    - paid: Cobrança paga
    - paid_externally: Baixa de cobrança
    - boleto-falha-registro: Falha no registro do boleto
    - pagamento-recebido: Pagamento recebido na conta
    """
    try:
        body = await request.json()
        logger.info(f"Grafeno webhook received: {json.dumps(body, default=str)[:500]}")
        
        # Pode vir como "kind" ou "change" dependendo do tipo de webhook
        kind = body.get("kind") or body.get("change", "")
        data = body.get("data", {})
        signature = body.get("signature", "")
        digest = body.get("digest", "")
        
        # Registrar no audit log
        audit = AuditLog(
            action=ActionType.GRAFENO_WEBHOOK,
            entity_type="webhook",
            entity_id=data.get("uuid") or data.get("api_partner_transaction_uuid") or "unknown",
            new_values={"kind": kind, "status": data.get("status")},
            ip_address=request.client.host if request.client else None,
        )
        db.add(audit)
        db.commit()
        
        # Verificar assinatura (em produção)
        transaction_uuid = data.get("api_partner_transaction_uuid", "")
        status = data.get("status", "")
        
        if not grafeno_service.verify_webhook_signature(
            signature=signature,
            digest=digest,
            transaction_uuid=transaction_uuid,
            status=status,
            kind=kind
        ):
            logger.warning("Invalid webhook signature")
            # Mesmo com assinatura inválida, retornamos 200 para não ficar em retry
            return {"status": "signature_invalid"}
        
        # Processar diferentes tipos de webhook
        # === TRANSFERÊNCIAS ===
        if kind == "confirmation":
            return await handle_transfer_confirmation(data, db)
        
        elif kind == "status-alterado":
            return await handle_transfer_status_change(data, db)
        
        # === PIX RECEBIDO ===
        elif kind in ["pix_entry", "pix-recebido"]:
            return await handle_pix_received(data, db)
        
        # === BOLETOS ===
        elif kind == "boleto-criado":
            return await handle_boleto_created(data, db)
        
        elif kind == "boleto-registrado":
            return await handle_boleto_registered(data, db)
        
        elif kind == "boleto-falha-registro":
            return await handle_boleto_registration_failed(data, db)
        
        # === COBRANÇAS ===
        elif kind == "cobranca-criada":
            return await handle_charge_created(data, db)
        
        elif kind == "paid":
            return await handle_charge_paid(data, db)
        
        elif kind == "paid_externally":
            return await handle_charge_paid_externally(data, db)
        
        # === PAGAMENTOS ===
        elif kind == "pagamento-recebido":
            return await handle_payment_received(data, db)
        
        else:
            logger.info(f"Unknown webhook kind: {kind}")
            return {"status": "unknown_kind", "kind": kind}
        
    except Exception as e:
        logger.error(f"Error processing Grafeno webhook: {str(e)}")
        # Retornamos 200 para não ficar em retry loop
        return {"status": "error", "message": str(e)}


async def handle_transfer_confirmation(data: dict, db: Session):
    """
    Processa confirmação de criação de transferência.
    A transferência foi criada e está pendente de aprovação.
    
    APROVAÇÃO AUTOMÁTICA: TEMPORARIAMENTE DESABILITADA PARA TESTES
    """
    transaction_uuid = data.get("api_partner_transaction_uuid")
    value = data.get("value", 0)
    beneficiary = data.get("beneficiary", {})
    
    logger.info(f"Transfer confirmation: {transaction_uuid}, value: R$ {value}")
    
    # AUTO-APROVAÇÃO DESABILITADA TEMPORARIAMENTE
    # Para reabilitar, descomente o código abaixo
    
    # # Regra de negócio: Aprovar automaticamente transferências até R$ 10.000
    # MAX_AUTO_APPROVE_VALUE = Decimal("10000.00")
    # transfer_value = Decimal(str(value))
    # 
    # if transfer_value <= MAX_AUTO_APPROVE_VALUE:
    #     logger.info(f"Auto-approving transfer {transaction_uuid} (R$ {value})")
    #     
    #     try:
    #         # Aprovar a transferência
    #         result = await grafeno_service.approve_transfer(transaction_uuid)
    #         
    #         if result.get("success"):
    #             logger.info(f"✅ Transfer {transaction_uuid} auto-approved successfully")
    #             
    #             # Registrar no audit log
    #             audit = AuditLog(
    #                 action=ActionType.GRAFENO_WEBHOOK,
    #                 entity_type="transfer_auto_approved",
    #                 entity_id=transaction_uuid,
    #                 new_values={
    #                     "value": float(value),
    #                     "beneficiary": beneficiary.get("name"),
    #                     "auto_approved": True
    #                 },
    #             )
    #             db.add(audit)
    #             db.commit()
    #             
    #             return {
    #                 "status": "auto_approved",
    #                 "transaction_uuid": transaction_uuid,
    #                 "value": value,
    #             }
    #         else:
    #             logger.error(f"❌ Failed to auto-approve transfer {transaction_uuid}: {result}")
    #             return {
    #                 "status": "approval_failed",
    #                 "transaction_uuid": transaction_uuid,
    #                 "error": result.get("data"),
    #             }
    #     except Exception as e:
    #         logger.error(f"❌ Exception auto-approving transfer {transaction_uuid}: {str(e)}")
    #         return {
    #             "status": "approval_error",
    #             "transaction_uuid": transaction_uuid,
    #             "error": str(e),
    #         }
    # else:
    #     logger.warning(f"⚠️ Transfer {transaction_uuid} exceeds auto-approval limit (R$ {value} > R$ {MAX_AUTO_APPROVE_VALUE})")
    #     
    #     # Registrar que precisa de aprovação manual
    #     audit = AuditLog(
    #         action=ActionType.GRAFENO_WEBHOOK,
    #         entity_type="transfer_pending_manual_approval",
    #         entity_id=transaction_uuid,
    #         new_values={
    #             "value": float(value),
    #             "beneficiary": beneficiary.get("name"),
    #             "reason": "Exceeds auto-approval limit"
    #         },
    #     )
    #     db.add(audit)
    #     db.commit()
    #     
    #     return {
    #         "status": "pending_manual_approval",
    #         "transaction_uuid": transaction_uuid,
    #         "value": value,
    #         "reason": f"Value R$ {value} exceeds limit R$ {MAX_AUTO_APPROVE_VALUE}",
    #     }
    
    # Apenas registrar e retornar sem aprovar
    logger.info(f"Transfer {transaction_uuid} registered, waiting for manual approval")
    
    return {
        "status": "confirmed",
        "transaction_uuid": transaction_uuid,
        "value": value,
    }


async def handle_transfer_status_change(data: dict, db: Session):
    """
    Processa mudança de status de transferência.
    
    Status possíveis:
    - autorizado-pelo-aprovador
    - rejeitado-pelo-aprovador
    - transferencia-enviada-com-sucesso
    - erro-ao-enviar-transferencia
    """
    from app.services.email import email_service
    from app.models.user import User
    
    transaction_uuid = data.get("api_partner_transaction_uuid")
    status = data.get("status")
    resource = data.get("resource")
    receipt_number = data.get("receipt_number")
    message = data.get("message")
    reject_reason = data.get("reject_reason")
    beneficiary = data.get("beneficiary", {})
    value = data.get("value")
    
    logger.info(f"Transfer status change: {transaction_uuid} -> {status}")
    
    # Buscar o ledger entry pelo reference_id (que é o transaction_uuid)
    ledger_entry = db.query(LedgerEntry).filter(
        LedgerEntry.reference_id == transaction_uuid
    ).first()
    
    user_email = None
    user_name = None
    
    if ledger_entry:
        # Buscar usuário relacionado
        if ledger_entry.created_by:
            user = db.query(User).filter(User.uuid == ledger_entry.created_by).first()
            if user:
                user_email = user.email
                user_name = user.full_name
        
        # Atualizar descrição com status
        if status == "transferencia-enviada-com-sucesso":
            ledger_entry.description = f"{ledger_entry.description} - Confirmado (Comprovante: {receipt_number})"
            logger.info(f"PIX sent successfully: {transaction_uuid}")
            
            # Notificar usuário
            if user_email:
                try:
                    email_service.notify_user_pix_sent(
                        user_email=user_email,
                        user_name=user_name or "Cliente",
                        amount=float(value) if value else float(ledger_entry.amount),
                        recipient_name=beneficiary.get("name", "Destinatário"),
                        recipient_pix_key=beneficiary.get("pix_key", ""),
                        status="enviado",
                    )
                    # Também enviar notificação do portal Grafeno
                    email_service.notify_grafeno_pix_sent(
                        user_email=user_email,
                        user_name=user_name or "Cliente",
                        amount=float(value) if value else float(ledger_entry.amount),
                        recipient_name=beneficiary.get("name", "Destinatário"),
                        recipient_pix_key=beneficiary.get("pix_key", ""),
                        status="concluido",
                        transaction_id=transaction_uuid,
                    )
                except Exception as e:
                    logger.error(f"Failed to send email notification: {e}")
        
        elif status == "erro-ao-enviar-transferencia":
            # Em caso de erro, precisamos reverter o débito
            logger.error(f"PIX send failed: {transaction_uuid}, reason: {message}")
            
            # Criar lançamento de estorno
            last_entry = db.query(LedgerEntry).filter(
                LedgerEntry.account_id == ledger_entry.account_id
            ).order_by(LedgerEntry.id.desc()).first()
            
            current_balance = Decimal(str(last_entry.balance_after)) if last_entry else Decimal("0")
            new_balance = current_balance + ledger_entry.amount
            
            reversal = LedgerEntry(
                account_id=ledger_entry.account_id,
                entry_type=EntryType.ADJUSTMENT_CREDIT,
                amount=ledger_entry.amount,
                direction=EntryDirection.CREDIT,
                balance_after=new_balance,
                description=f"Estorno PIX - Falha no envio: {message or reject_reason or 'Erro desconhecido'}",
                reference_type="PIX_REVERSAL",
                reference_id=transaction_uuid,
                created_by=ledger_entry.created_by,
            )
            db.add(reversal)
            db.commit()
            
            logger.info(f"Created reversal entry for failed PIX: {transaction_uuid}")
            
            # Notificar usuário sobre erro
            if user_email:
                try:
                    email_service.notify_user_pix_sent(
                        user_email=user_email,
                        user_name=user_name or "Cliente",
                        amount=float(value) if value else float(ledger_entry.amount),
                        recipient_name=beneficiary.get("name", "Destinatário"),
                        recipient_pix_key=beneficiary.get("pix_key", ""),
                        status="erro",
                    )
                    # Também notificar pelo portal Grafeno
                    email_service.notify_grafeno_pix_sent(
                        user_email=user_email,
                        user_name=user_name or "Cliente",
                        amount=float(value) if value else float(ledger_entry.amount),
                        recipient_name=beneficiary.get("name", "Destinatário"),
                        recipient_pix_key=beneficiary.get("pix_key", ""),
                        status="falhou",
                        transaction_id=transaction_uuid,
                    )
                except Exception as e:
                    logger.error(f"Failed to send email notification: {e}")
        
        elif status == "rejeitado-pelo-aprovador":
            logger.warning(f"PIX rejected by approver: {transaction_uuid}, reason: {reject_reason}")
            # Também reverter
            last_entry = db.query(LedgerEntry).filter(
                LedgerEntry.account_id == ledger_entry.account_id
            ).order_by(LedgerEntry.id.desc()).first()
            
            current_balance = Decimal(str(last_entry.balance_after)) if last_entry else Decimal("0")
            new_balance = current_balance + ledger_entry.amount
            
            reversal = LedgerEntry(
                account_id=ledger_entry.account_id,
                entry_type=EntryType.ADJUSTMENT_CREDIT,
                amount=ledger_entry.amount,
                direction=EntryDirection.CREDIT,
                balance_after=new_balance,
                description=f"Estorno PIX - Rejeitado: {reject_reason or 'Sem motivo'}",
                reference_type="PIX_REVERSAL",
                reference_id=transaction_uuid,
                created_by=ledger_entry.created_by,
            )
            db.add(reversal)
            db.commit()
            
            # Notificar usuário sobre rejeição
            if user_email:
                try:
                    email_service.notify_user_pix_sent(
                        user_email=user_email,
                        user_name=user_name or "Cliente",
                        amount=float(value) if value else float(ledger_entry.amount),
                        recipient_name=beneficiary.get("name", "Destinatário"),
                        recipient_pix_key=beneficiary.get("pix_key", ""),
                        status="rejeitado",
                    )
                    # Também notificar pelo portal Grafeno
                    email_service.notify_grafeno_pix_sent(
                        user_email=user_email,
                        user_name=user_name or "Cliente",
                        amount=float(value) if value else float(ledger_entry.amount),
                        recipient_name=beneficiary.get("name", "Destinatário"),
                        recipient_pix_key=beneficiary.get("pix_key", ""),
                        status="rejeitado",
                        transaction_id=transaction_uuid,
                    )
                except Exception as e:
                    logger.error(f"Failed to send email notification: {e}")
        
        db.commit()
    
    return {
        "status": "processed",
        "transaction_uuid": transaction_uuid,
        "new_status": status,
    }


async def handle_pix_received(data: dict, db: Session):
    """
    Processa PIX recebido na conta Grafeno.
    Cria um PIX_INCOMING pendente para alocação pelo Master.
    """
    from app.services.email import email_service
    
    # Extrair dados do PIX recebido
    value = data.get("value") or data.get("amount")
    payer_name = data.get("payer_name") or data.get("bankAccount", {}).get("name", "Desconhecido")
    payer_document = data.get("payer_document") or data.get("bankAccount", {}).get("documentNumber", "")
    entry_id = data.get("id") or data.get("entry_id")
    entry_at = data.get("entry_at") or data.get("entryAt")
    description = data.get("description") or data.get("info") or ""
    
    logger.info(f"PIX received: {value} from {payer_name}")
    
    # Verificar se já existe (idempotência)
    existing = db.query(PixIncoming).filter(
        PixIncoming.external_id == str(entry_id)
    ).first() if entry_id else None
    
    if existing:
        logger.info(f"PIX already registered: {entry_id}")
        return {"status": "already_exists", "pix_id": existing.uuid}
    
    # Criar PIX incoming pendente
    pix = PixIncoming(
        amount=Decimal(str(value)) if value else Decimal("0"),
        payer_name=payer_name,
        payer_cpf_cnpj=payer_document,
        description=f"PIX recebido via Grafeno",
        external_id=str(entry_id) if entry_id else None,
        status=PixStatus.PENDING,
        transaction_date=datetime.fromisoformat(entry_at.replace("Z", "+00:00")) if entry_at else datetime.utcnow(),
    )
    db.add(pix)
    db.commit()
    db.refresh(pix)
    
    logger.info(f"Created pending PIX: {pix.uuid}")
    
    # Enviar notificação por email para admins
    try:
        email_service.notify_pix_received(
            payer_name=payer_name,
            amount=float(value) if value else 0.0,
            payer_cpf_cnpj=payer_document,
            description=description,
        )
        
        # Notificar também o master do portal Grafeno
        email_service.notify_grafeno_pix_received(
            user_email="master@flcbank.com.br",  # Email do master
            user_name="FLC Bank",
            amount=float(value) if value else 0.0,
            payer_name=payer_name,
            payer_document=payer_document,
            description=description,
            end_to_end_id=str(entry_id) if entry_id else None,
        )
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")
    
    return {
        "status": "created",
        "pix_uuid": pix.uuid,
    }


# =====================================================
# HANDLERS - BOLETOS
# =====================================================

async def handle_boleto_created(data: dict, db: Session):
    """
    Processa notificação de boleto criado.
    Evento: boleto-criado
    """
    uuid = data.get("uuid")
    value = data.get("value")
    due_date = data.get("dueDate")
    status = data.get("status")
    boleto_data = data.get("boleto", {})
    payer = data.get("payer", {})
    
    logger.info(f"Boleto created: {uuid}, value: {value}, due_date: {due_date}")
    
    # Aqui você pode salvar em uma tabela de boletos se necessário
    # Por enquanto apenas registramos no audit log
    
    return {
        "status": "processed",
        "event": "boleto-criado",
        "uuid": uuid,
        "boleto": {
            "bar_code": boleto_data.get("barCode"),
            "line_code": boleto_data.get("lineCode"),
            "our_number": boleto_data.get("ourNumber"),
            "pdf_url": boleto_data.get("pdf"),
            "registration_status": boleto_data.get("registrationStatus"),
        },
        "payer_name": payer.get("name"),
        "value": value,
    }


async def handle_boleto_registered(data: dict, db: Session):
    """
    Processa notificação de boleto registrado.
    Evento: boleto-registrado
    """
    uuid = data.get("uuid")
    boleto_data = data.get("boleto", {})
    
    logger.info(f"Boleto registered: {uuid}")
    
    return {
        "status": "processed",
        "event": "boleto-registrado",
        "uuid": uuid,
        "registration_status": boleto_data.get("registrationStatus"),
    }


async def handle_boleto_registration_failed(data: dict, db: Session):
    """
    Processa notificação de falha no registro do boleto.
    Evento: boleto-falha-registro
    """
    uuid = data.get("uuid")
    boleto_data = data.get("boleto", {})
    registration_details = boleto_data.get("registrationDetails", "")
    
    logger.error(f"Boleto registration failed: {uuid}, reason: {registration_details}")
    
    return {
        "status": "processed",
        "event": "boleto-falha-registro",
        "uuid": uuid,
        "registration_status": boleto_data.get("registrationStatus"),
        "registration_details": registration_details,
    }


# =====================================================
# HANDLERS - COBRANÇAS
# =====================================================

async def handle_charge_created(data: dict, db: Session):
    """
    Processa notificação de cobrança PIX criada.
    Evento: cobranca-criada
    """
    uuid = data.get("uuid")
    value = data.get("value")
    due_date = data.get("dueDate")
    status = data.get("status")
    payment_method = data.get("paymentMethod")
    pix_data = data.get("pixData", {}).get("data", {}).get("attributes", {})
    
    logger.info(f"Charge created: {uuid}, method: {payment_method}, value: {value}")
    
    return {
        "status": "processed",
        "event": "cobranca-criada",
        "uuid": uuid,
        "payment_method": payment_method,
        "value": value,
        "pix_emv": pix_data.get("emv") if pix_data else None,
    }


async def handle_charge_paid(data: dict, db: Session):
    """
    Processa notificação de cobrança paga.
    Evento: paid
    
    Este é um dos eventos mais importantes - indica que recebemos um pagamento!
    """
    uuid = data.get("uuid")
    value = data.get("value")
    status = data.get("status")
    payment_method = data.get("paymentMethod")
    payments = data.get("payments", [])
    payer = data.get("payer", {})
    client_control_number = data.get("clientControlNumber")
    
    logger.info(f"Charge PAID: {uuid}, value: {value}, method: {payment_method}")
    
    # Extrair informações do pagamento
    payment_info = None
    if payments:
        payment_info = {
            "value": payments[0].get("value"),
            "received_at": payments[0].get("receivedAt"),
            "processed_at": payments[0].get("processedAt"),
            "bank_code": payments[0].get("paymentBankCode"),
            "agency": payments[0].get("paymentAgency"),
        }
    
    # Se for boleto ou PIX Cobrança pago, criar entrada no sistema
    payer_name = payer.get("name", "Desconhecido")
    payer_document = payer.get("documentNumber", "")
    
    # Verificar se já existe (idempotência)
    existing = db.query(PixIncoming).filter(
        PixIncoming.external_id == str(uuid)
    ).first()
    
    if existing:
        # Atualizar status se necessário
        if existing.status == PixStatus.PENDING:
            logger.info(f"Payment already registered: {uuid}")
        return {"status": "already_exists", "uuid": uuid}
    
    # Criar entrada pendente para alocação
    pix = PixIncoming(
        amount=Decimal(str(value)) if value else Decimal("0"),
        payer_name=payer_name,
        payer_cpf_cnpj=payer_document,
        description=f"Pagamento {payment_method.upper()} recebido - Ref: {client_control_number or uuid}",
        external_id=str(uuid),
        status=PixStatus.PENDING,
        transaction_date=datetime.utcnow(),
    )
    db.add(pix)
    db.commit()
    db.refresh(pix)
    
    logger.info(f"Created pending payment entry: {pix.uuid}")
    
    return {
        "status": "processed",
        "event": "paid",
        "uuid": uuid,
        "pix_uuid": pix.uuid,
        "value": value,
        "payment_method": payment_method,
        "payment_info": payment_info,
    }


async def handle_charge_paid_externally(data: dict, db: Session):
    """
    Processa notificação de baixa de cobrança.
    Evento: paid_externally
    
    Isso acontece quando a cobrança é baixada manualmente.
    """
    uuid = data.get("uuid")
    value = data.get("value")
    status = data.get("status")
    
    logger.info(f"Charge paid externally (write-off): {uuid}, value: {value}")
    
    return {
        "status": "processed",
        "event": "paid_externally",
        "uuid": uuid,
        "value": value,
    }


# =====================================================
# HANDLERS - PAGAMENTOS
# =====================================================

async def handle_payment_received(data: dict, db: Session):
    """
    Processa notificação de pagamento recebido.
    Evento: pagamento-recebido
    
    Similar ao 'paid', mas é o evento específico de recebimento de valores.
    """
    uuid = data.get("uuid")
    value = data.get("value")
    status = data.get("status")
    payment_method = data.get("paymentMethod")
    payments = data.get("payments", [])
    payer = data.get("payer", {})
    client_control_number = data.get("clientControlNumber")
    boleto_data = data.get("boleto", {})
    
    logger.info(f"Payment received: {uuid}, value: {value}, method: {payment_method}")
    
    # Verificar se já existe
    existing = db.query(PixIncoming).filter(
        PixIncoming.external_id == str(uuid)
    ).first()
    
    if existing:
        logger.info(f"Payment already registered: {uuid}")
        return {"status": "already_exists", "uuid": uuid}
    
    # Criar entrada pendente
    payer_name = payer.get("name", "Desconhecido")
    payer_document = payer.get("documentNumber", "")
    
    pix = PixIncoming(
        amount=Decimal(str(value)) if value else Decimal("0"),
        payer_name=payer_name,
        payer_cpf_cnpj=payer_document,
        description=f"Pagamento recebido ({payment_method}) - {client_control_number or uuid}",
        external_id=str(uuid),
        status=PixStatus.PENDING,
        transaction_date=datetime.utcnow(),
    )
    db.add(pix)
    db.commit()
    db.refresh(pix)
    
    logger.info(f"Created pending payment: {pix.uuid}")
    
    return {
        "status": "processed",
        "event": "pagamento-recebido",
        "uuid": uuid,
        "pix_uuid": pix.uuid,
        "value": value,
        "payment_method": payment_method,
    }


@router.get("/balance")
async def get_grafeno_balance():
    """Consulta o saldo atual da conta Grafeno."""
    result = await grafeno_service.get_balance()
    return result


@router.get("/statement")
async def get_grafeno_statement(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
):
    """Consulta o extrato da conta Grafeno."""
    result = await grafeno_service.get_statement(
        start_date=start_date,
        end_date=end_date,
        page=page,
        per_page=per_page,
    )
    return result


@router.get("/accounts")
async def get_grafeno_accounts():
    """Lista contas bancárias vinculadas à Grafeno."""
    result = await grafeno_service.get_bank_accounts()
    return result


@router.get("/transfers")
async def get_grafeno_transfers(
    page: int = 1,
    per_page: int = 50,
    status: Optional[str] = None,
):
    """Lista transferências na Grafeno."""
    result = await grafeno_service.list_transfers(
        page=page,
        per_page=per_page,
        status=status,
    )
    return result


@router.get("/transfers/pending")
async def get_grafeno_pending_transfers():
    """Lista transferências pendentes de aprovação."""
    result = await grafeno_service.list_pending_transfers()
    return result


# =====================================================
# WEBHOOK REGISTRATION - Registrar URLs de webhook na Grafeno
# =====================================================

@router.post("/webhooks/register")
async def register_webhook(
    kind: str,
    url: str,
    extra_headers: Optional[str] = None,
):
    """
    Registra uma URL de webhook na Grafeno.
    
    Tipos disponíveis:
    - boleto: Notificações de boletos
    - charge: Notificações de cobranças
    - payment: Notificações de pagamentos
    - concession: Notificações de concessões
    - protest: Notificações de protesto
    
    Args:
        kind: Tipo do webhook (boleto, charge, payment, concession, protest)
        url: URL para receber as notificações
        extra_headers: Headers extras para enviar com a notificação (opcional)
    """
    valid_kinds = ["boleto", "charge", "payment", "concession", "protest"]
    if kind not in valid_kinds:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo inválido. Use um dos: {', '.join(valid_kinds)}"
        )
    
    result = await grafeno_service.register_webhook(
        kind=kind,
        url=url,
        extra_headers=extra_headers
    )
    return result


@router.get("/webhooks")
async def list_webhooks():
    """Lista todos os webhooks registrados na Grafeno."""
    result = await grafeno_service.list_webhooks()
    return result


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str):
    """Remove um webhook registrado na Grafeno."""
    result = await grafeno_service.delete_webhook(webhook_id)
    return result


@router.post("/webhooks/setup-all")
async def setup_all_webhooks(base_url: str):
    """
    Configura todos os webhooks necessários de uma vez.
    
    Este endpoint registra webhooks para:
    - Boletos
    - Cobranças
    - Pagamentos
    
    Args:
        base_url: URL base do sistema (ex: https://flc-bank-api.fly.dev)
    """
    webhook_url = f"{base_url.rstrip('/')}/grafeno/webhook"
    
    results = {}
    for kind in ["boleto", "charge", "payment"]:
        try:
            result = await grafeno_service.register_webhook(
                kind=kind,
                url=webhook_url,
                extra_headers=None  # Sem headers extras por enquanto
            )
            results[kind] = {"status": "registered", "result": result}
        except Exception as e:
            results[kind] = {"status": "error", "message": str(e)}
    
    return {
        "webhook_url": webhook_url,
        "results": results
    }
