"""
FLC Bank - Router para Clientes Grafeno
API para clientes acessarem suas contas Grafeno diretamente
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal
from typing import Optional
import httpx
import os
import logging

from app.database import get_db
from app.models.grafeno_account import GrafenoAccount, OnboardingStatus
from app.models.user import User
from app.models.audit import AuditLog
from app.utils.security import create_access_token, decode_token, verify_password
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/grafeno-client", tags=["Grafeno Client"])

# URLs da API Grafeno
GRAFENO_PAYMENTS_URL = "https://pagamentos.grafeno.be/api/v2"
GRAFENO_STATEMENTS_URL = "https://extratos.grafeno.digital/api/v1"

# Token base do Grafeno (será substituído pelo token da conta específica)
GRAFENO_TOKEN = os.getenv("GRAFENO_API_TOKEN", "38387c01-b705-4425-9006-59a8c134d8b0.9V9v4B_L0XVcx-tmrEEUMNAKvSk")


# =====================================================
# SCHEMAS
# =====================================================

class ClientLoginRequest(BaseModel):
    """Request para login do cliente"""
    document_number: Optional[str] = None  # CNPJ (opcional)
    email: Optional[str] = None  # Email do master (opcional)
    password: str


class ClientLoginResponse(BaseModel):
    """Response do login do cliente"""
    access_token: str
    token_type: str = "bearer"
    account: dict


class PixTransferRequest(BaseModel):
    """Request para enviar PIX"""
    value: float
    pix_key: str
    pix_key_type: str  # cpf, cnpj, email, phone, evp
    beneficiary_name: str
    beneficiary_document: str
    description: Optional[str] = None
    beneficiary_id: Optional[str] = None


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def get_grafeno_headers(account: GrafenoAccount) -> dict:
    """Retorna headers para requisições à API Grafeno usando a conta do cliente."""
    # Se a conta tiver api_key própria, usar ela, senão usar a principal
    token = account.api_key if account.api_key else GRAFENO_TOKEN
    account_number = account.account_number if account.account_number else "08185935-7"
    
    return {
        "Authorization": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Account-Number": account_number,
    }


def get_grafeno_headers_master() -> dict:
    """Retorna headers para a conta principal/master Grafeno."""
    return {
        "Authorization": GRAFENO_TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Account-Number": "08185935-7",
    }


async def get_current_grafeno_client(
    request: Request,
    db: Session = Depends(get_db)
) -> GrafenoAccount | User:
    """Obtém a conta Grafeno do cliente autenticado ou usuário master."""
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token não fornecido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header.split(" ")[1]
    
    token = auth_header.split(" ")[1]
    
    # Decodificar o token
    try:
        payload = decode_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {str(e)}",
        )

    uuid = payload.get("sub")
    token_type = payload.get("type")
    
    logger.info(f"Grafeno Auth: UUID={uuid}, Type={token_type}")
    
    if not uuid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido (sem UUID)",
        )
    
    # 1. Se for explicitamente token de master
    if token_type == "grafeno_master":
        user = db.query(User).filter(User.uuid == uuid).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário master não encontrado",
            )
        user.is_grafeno_master = True
        return user
        
    # 2. Se for token de cliente Grafeno
    if token_type == "grafeno_client":
        account = db.query(GrafenoAccount).filter(GrafenoAccount.uuid == uuid).first()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conta Grafeno não encontrada",
            )
        return account

    # 3. Fallback: Se for token de acesso comum ('access'), verifica se é Master
    # Isso permite que o login antigo funcione se o usuário for Master
    if token_type == "access" or token_type is None:
        # Tenta achar usuário
        user = db.query(User).filter(User.uuid == uuid).first()
        if user and user.role == "MASTER":
            logger.info(f"Fallback Auth: Usuário {user.email} autenticado via token padrão como Master")
            user.is_grafeno_master = True
            return user
        
        # Se achou ussuário mas não é master
        if user:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Este usuário não tem permissão de Master para acessar Grafeno",
            )

        # Se não achou usuário, tenta achar conta (caso improvável de token de acesso para conta)
        # Mas mantemos a lógica original de falhar se não achar conta
    
    # Se chegou aqui, tenta buscar como Conta Grafeno padrão
    account = db.query(GrafenoAccount).filter(GrafenoAccount.uuid == uuid).first()
    
    if not account:
        logger.error(f"Auth Failed: UUID {uuid} not found in Users (Master) or GrafenoAccounts")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conta/Usuário não encontrado para UUID: {uuid}",
        )
    
    return account


# =====================================================
# AUTHENTICATION
# =====================================================

@router.post("/login", response_model=ClientLoginResponse)
async def client_login(
    credentials: ClientLoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Login do cliente Grafeno.
    
    Aceita dois modos de autenticação:
    1. Email + senha (para usuários master do FLC Bank)
    2. CNPJ + senha (para contas Grafeno cadastradas)
    """
    account = None
    login_type = None
    
    # Modo 1: Login via email (master FLC Bank)
    if credentials.email:
        user = db.query(User).filter(User.email == credentials.email).first()
        
        if user and verify_password(credentials.password, user.password_hash):
            if user.role != "MASTER":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Apenas usuários master podem acessar o Portal FLC Bank",
                )
            
            # Criar uma conta virtual para o master (usa a conta principal Grafeno)
            login_type = "master"
            
            # Criar token JWT
            token_data = {
                "sub": user.uuid,
                "email": user.email,
                "type": "grafeno_master"
            }
            access_token = create_access_token(token_data)
            
            # Registrar login
            audit = AuditLog(
                action="GRAFENO_MASTER_LOGIN_SUCCESS",
                entity_type="user",
                entity_id=user.uuid,
                ip_address=request.client.host if request.client else None,
            )
            db.add(audit)
            db.commit()
            
            return ClientLoginResponse(
                access_token=access_token,
                account={
                    "uuid": user.uuid,
                    "name": user.full_name,
                    "company_name": "FLC Bank - Conta Principal Grafeno",
                    "document_number": "00.000.000/0000-00",
                    "email": user.email,
                    "account_number": "08185935-7",
                    "agency": "0001",
                    "bank_code": "274",
                    "pix_key": "43aa6af5-c6e1-42f1-9cf9-d5606d1b8a75",
                    "status": "ACTIVE",
                    "is_master": True,
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou senha incorretos",
            )
    
    # Modo 2: Login via CNPJ (conta Grafeno cadastrada)
    if credentials.document_number:
        doc_number = credentials.document_number.replace(".", "").replace("/", "").replace("-", "")
        
        account = db.query(GrafenoAccount).filter(
            GrafenoAccount.document_number == doc_number
        ).first()
        
        if not account:
            audit = AuditLog(
                action="GRAFENO_CLIENT_LOGIN_FAILED",
                entity_type="grafeno_account",
                entity_id=doc_number,
                extra_data={"reason": "account_not_found"},
                ip_address=request.client.host if request.client else None,
            )
            db.add(audit)
            db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="CNPJ ou senha incorretos",
            )
        
        if account.password != credentials.password:
            audit = AuditLog(
                action="GRAFENO_CLIENT_LOGIN_FAILED",
                entity_type="grafeno_account",
                entity_id=account.uuid,
                extra_data={"reason": "invalid_password"},
                ip_address=request.client.host if request.client else None,
            )
            db.add(audit)
            db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="CNPJ ou senha incorretos",
            )
        
        if account.status not in [OnboardingStatus.APPROVED, OnboardingStatus.ACTIVE]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Conta ainda não está ativa. Status: {account.status.value}",
            )
        
        token_data = {
            "sub": account.uuid,
            "document": account.document_number,
            "type": "grafeno_client"
        }
        access_token = create_access_token(token_data)
        
        audit = AuditLog(
            action="GRAFENO_CLIENT_LOGIN_SUCCESS",
            entity_type="grafeno_account",
            entity_id=account.uuid,
            ip_address=request.client.host if request.client else None,
        )
        db.add(audit)
        db.commit()
        
        return ClientLoginResponse(
            access_token=access_token,
            account={
                "uuid": account.uuid,
                "name": account.name,
                "company_name": account.company_name,
                "document_number": account.document_number,
                "email": account.email,
                "account_number": account.account_number,
                "agency": account.agency,
                "bank_code": account.bank_code,
                "pix_key": account.pix_key,
                "status": account.status.value,
            }
        )
    
    # Nenhum método de login fornecido
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Informe email ou CNPJ para login",
    )


# =====================================================
# ACCOUNT INFO
# =====================================================

@router.get("/me")
async def get_client_info(
    account = Depends(get_current_grafeno_client)
):
    """Retorna informações da conta do cliente logado."""
    # Se for master, retorna dados da conta principal Grafeno
    if hasattr(account, 'is_grafeno_master') and account.is_grafeno_master:
        return {
            "uuid": account.uuid,
            "name": account.full_name,
            "company_name": "FLC Bank - Conta Principal Grafeno",
            "document_number": "00.000.000/0000-00",
            "email": account.email,
            "commercial_phone": "",
            "account_number": "08185935-7",
            "agency": "0001",
            "bank_code": "274",
            "pix_key": "43aa6af5-c6e1-42f1-9cf9-d5606d1b8a75",
            "status": "ACTIVE",
            "is_master": True,
            "address": None,
        }
    
    # Retorno normal para conta Grafeno cadastrada
    return {
        "uuid": account.uuid,
        "name": account.name,
        "company_name": account.company_name,
        "document_number": account.document_number,
        "email": account.email,
        "commercial_phone": account.commercial_phone,
        "account_number": account.account_number,
        "agency": account.agency,
        "bank_code": account.bank_code or "274",
        "pix_key": account.pix_key,
        "status": account.status.value,
        "address": {
            "street": account.address_street,
            "number": account.address_number,
            "complement": account.address_complement,
            "neighborhood": account.address_neighborhood,
            "city": account.address_city,
            "state": account.address_state,
            "zipCode": account.address_zipcode,
        }
    }


# =====================================================
# BALANCE
# =====================================================

@router.get("/balance")
async def get_client_balance(
    account = Depends(get_current_grafeno_client)
):
    """Consulta o saldo da conta do cliente."""
    # Se for master, usa headers da conta principal
    if hasattr(account, 'is_grafeno_master') and account.is_grafeno_master:
        headers = get_grafeno_headers_master()
        account_number = "08185935-7"
        agency = "0001"
    else:
        headers = get_grafeno_headers(account)
        account_number = account.account_number
        agency = account.agency
    
    url = f"{GRAFENO_PAYMENTS_URL}/balance/"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Processar resposta - pode ser lista ou objeto
                if isinstance(data, dict) and "data" in data:
                    accounts_data = data.get("data", {})
                    
                    # Se for lista, pegar o primeiro
                    if isinstance(accounts_data, list) and len(accounts_data) > 0:
                        account_info = accounts_data[0]
                        attrs = account_info.get("attributes", {})
                    # Se for objeto direto
                    elif isinstance(accounts_data, dict):
                        attrs = accounts_data.get("attributes", {})
                    else:
                        attrs = {}
                    
                    # Converter string para float se necessário
                    current = attrs.get("currentBalance") or attrs.get("balance", 0)
                    available = attrs.get("availableBalance") or attrs.get("balance", 0)
                    
                    if isinstance(current, str):
                        current = float(current)
                    if isinstance(available, str):
                        available = float(available)
                    
                    return {
                        "success": True,
                        "current_balance": current,
                        "available_balance": available,
                        "account_number": account_number,
                        "agency": agency,
                    }
                
                return {
                    "success": True,
                    "current_balance": 0,
                    "available_balance": 0,
                    "account_number": account_number,
                    "data": data,
                }
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text,
                }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Erro ao conectar com a API Grafeno",
        }


# =====================================================
# STATEMENT
# =====================================================

@router.get("/statement")
async def get_client_statement(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
    account = Depends(get_current_grafeno_client)
):
    """Consulta o extrato da conta do cliente."""
    # Se for master, usa headers da conta principal
    if hasattr(account, 'is_grafeno_master') and account.is_grafeno_master:
        headers = get_grafeno_headers_master()
    else:
        headers = get_grafeno_headers(account)
    
    # Parâmetros conforme documentação Grafeno
    params = {
        "p[page]": page,
        "p[per_page]": per_page,
    }
    
    # Filtros de data (formato YYYY-MM-DD)
    if start_date:
        params["q[entryAtGteq]"] = start_date
    if end_date:
        params["q[entryAtLteq]"] = end_date
    
    # URL correta conforme documentação
    url = f"{GRAFENO_PAYMENTS_URL}/statement_entries/"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=headers,
                params=params,
                timeout=30.0
            )
            
            return {
                "success": response.status_code == 200,
                "data": response.json() if response.status_code == 200 else None,
                "status_code": response.status_code,
                "error": response.text if response.status_code != 200 else None,
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Erro ao conectar com a API Grafeno",
        }


# =====================================================
# PIX TRANSFER
# =====================================================

@router.post("/pix/send")
async def send_pix_transfer(
    transfer: PixTransferRequest,
    request: Request,
    account = Depends(get_current_grafeno_client),
    db: Session = Depends(get_db)
):
    """
    Envia uma transferência PIX.
    
    IMPORTANTE: Este endpoint agora cadastra o beneficiário automaticamente
    antes de criar a transferência, conforme exigido pela Grafeno.
    """
    import uuid as uuid_lib
    
    # Se for master, usa headers da conta principal
    if hasattr(account, 'is_grafeno_master') and account.is_grafeno_master:
        headers = get_grafeno_headers_master()
        account_uuid = account.uuid
    else:
        headers = get_grafeno_headers(account)
        account_uuid = account.uuid
    
    transaction_uuid = str(uuid_lib.uuid4())
    
    # Callback URL para receber atualizações
    webhook_url = os.getenv("GRAFENO_WEBHOOK_URL", "https://flc-bank-api.fly.dev/grafeno/webhook")
    
    # ======================================================
    # PASSO 1: Verificar/Cadastrar beneficiário (Se não fornecido ID)
    # ======================================================
    beneficiary_id = transfer.beneficiary_id
    
    if not beneficiary_id:
        # Limpar documento do beneficiário
        clean_document = transfer.beneficiary_document.replace(".", "").replace("-", "").replace("/", "") if transfer.beneficiary_document else ""
        
        beneficiary_payload_for_creation = {
            "name": transfer.beneficiary_name,
            "documentNumber": clean_document,
            "pixDetails": {
                "key": transfer.pix_key,
                "keyType": transfer.pix_key_type,
            },
            # Workaround: Grafeno exige dados bancários para criar beneficiário
            "bankCode": "274",
            "agency": "0001",
            "account": "000000000"
        }
        
        beneficiary_url = f"{GRAFENO_PAYMENTS_URL}/beneficiaries"
        
        try:
            async with httpx.AsyncClient() as client:
                # Primeiro, verificar se beneficiário já existe
                check_response = await client.get(
                    beneficiary_url,
                    params={"filter[documentNumber]": clean_document},
                    headers=headers,
                    timeout=30.0
                )
                
                existing_beneficiaries = []
                if check_response.status_code == 200:
                    try:
                        check_data = check_response.json()
                        if isinstance(check_data, dict) and "data" in check_data:
                            existing_beneficiaries = check_data.get("data", [])
                    except:
                        pass
                
                if existing_beneficiaries and len(existing_beneficiaries) > 0:
                    # Beneficiário já existe
                    beneficiary_id = existing_beneficiaries[0].get("id")
                    logger.info(f"Beneficiário já cadastrado: {beneficiary_id}")
                else:
                    # Cadastrar novo beneficiário
                    logger.info(f"Cadastrando novo beneficiário: {transfer.beneficiary_name}")
                    add_response = await client.post(
                        beneficiary_url,
                        json=beneficiary_payload_for_creation,
                        headers=headers,
                        timeout=30.0
                    )
                    
                    if add_response.status_code in [200, 201]:
                        try:
                            add_data = add_response.json()
                            if isinstance(add_data, dict) and "data" in add_data:
                                beneficiary_id = add_data["data"].get("id")
                            logger.info(f"Beneficiário cadastrado com sucesso: {beneficiary_id}")
                        except:
                            pass
                    else:
                        try:
                            error_data = add_response.json()
                        except:
                            error_data = {"raw": add_response.text}
                        
                        logger.warning(f"Erro ao cadastrar beneficiário: {error_data}")
        except Exception as e:
            logger.warning(f"Erro ao verificar/cadastrar beneficiário: {str(e)}")
    
    # ======================================================
    # PASSO 2: Criar transferência PIX
    # ======================================================
    
    # Preparar objeto beneficiary para o payload da transferência
    # Enviar objeto COMPLETO mesmo se tiver ID, para garantir que a Grafeno 
    # consiga validar todos os campos.
    
    clean_document = transfer.beneficiary_document.replace(".", "").replace("-", "").replace("/", "") if transfer.beneficiary_document else ""
    
    beneficiary_payload = {
        "name": transfer.beneficiary_name,
        "documentNumber": clean_document,
        "keyType": transfer.pix_key_type,
        "key": transfer.pix_key,
        # Workaround: Grafeno exige dados bancários para criar/validar beneficiário
        "bankCode": "274",
        "agency": "0001",
        "account": "000000000"
    }
    
    if beneficiary_id:
        beneficiary_payload["id"] = beneficiary_id

    payload = {
        "transfer_request": {
            "transferMethod": "pix",
            "value": float(transfer.value),
            "api_partner_transaction_uuid": transaction_uuid,
            "callback_url": webhook_url,
        },
        "beneficiary": beneficiary_payload
    }
    
    url = f"{GRAFENO_PAYMENTS_URL}/transfer_requests"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            try:
                response_data = response.json()
            except:
                response_data = {"raw": response.text}
            
            success = response.status_code in [200, 201, 202]

            if success:
                # Registrar auditoria
                audit = AuditLog(
                    action="GRAFENO_PIX_TRANSFER",
                    entity_type="grafeno_account" if not hasattr(account, 'is_grafeno_master') else "user",
                    entity_id=account_uuid,
                    extra_data={
                        "transaction_uuid": transaction_uuid,
                        "value": transfer.value,
                        "beneficiary_name": transfer.beneficiary_name,
                        "beneficiary_id": beneficiary_id,
                        "pix_key": transfer.pix_key,
                        "success": True,
                        "status_code": response.status_code,
                    },
                    ip_address=request.client.host if request.client else None,
                )
                db.add(audit)
                db.commit()
                
                # Enviar notificação por email
                try:
                    from app.services.email import email_service
                    # Determinar email e nome do usuário
                    if hasattr(account, 'is_grafeno_master') and account.is_grafeno_master:
                        user_email = account.email
                        user_name = account.full_name or "Master"
                    else:
                        user_email = account.email
                        user_name = account.name or account.company_name or "Cliente"
                    
                    email_service.notify_grafeno_pix_sent(
                        user_email=user_email,
                        user_name=user_name,
                        amount=float(transfer.value),
                        recipient_name=transfer.beneficiary_name,
                        recipient_pix_key=transfer.pix_key,
                        status="enviado",
                        transaction_id=transaction_uuid,
                    )
                except Exception as email_error:
                    logger.warning(f"Erro ao enviar email de notificação: {email_error}")
                
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "transaction_uuid": transaction_uuid,
                    "data": response_data,
                    "message": "PIX enviado com sucesso!",
                }
            else:
                 # Registrar auditoria de falha
                audit = AuditLog(
                    action="GRAFENO_PIX_TRANSFER",
                    entity_type="grafeno_account" if not hasattr(account, 'is_grafeno_master') else "user",
                    entity_id=account_uuid,
                    extra_data={
                        "transaction_uuid": transaction_uuid,
                        "value": transfer.value,
                        "beneficiary_name": transfer.beneficiary_name,
                        "beneficiary_id": beneficiary_id,
                        "pix_key": transfer.pix_key,
                        "success": False,
                        "status_code": response.status_code,
                    },
                    ip_address=request.client.host if request.client else None,
                )
                db.add(audit)
                db.commit()

                # Tenta extrair mensagem de erro detalhada
                try:
                    err_json = response.json()
                    if "errors" in err_json:
                        details = []
                        for err in err_json["errors"]:
                            field = err.get("field", "Geral")
                            msg = err.get("message", "Erro")
                            details.append(f"{field}: {msg}")
                        error_msg = "; ".join(details)
                    else:
                        error_msg = err_json.get("message") or err_json.get("error") or response.text
                except:
                    error_msg = response.text or "Erro desconhecido na API Grafeno"
                
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_msg
                )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending PIX: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao processar PIX: {str(e)}"
        )


# =====================================================
# BENEFICIARIES
# =====================================================

@router.get("/beneficiaries")
async def list_client_beneficiaries(
    page: int = 1,
    per_page: int = 50,
    account = Depends(get_current_grafeno_client)
):
    """Lista beneficiários cadastrados na Grafeno."""
    # Se for master, usa headers da conta principal
    if hasattr(account, 'is_grafeno_master') and account.is_grafeno_master:
        headers = get_grafeno_headers_master()
    else:
        headers = get_grafeno_headers(account)
    
    url = f"{GRAFENO_PAYMENTS_URL}/beneficiaries"
    
    params = {
        "page[number]": page,
        "page[size]": per_page,
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers=headers,
                timeout=30.0
            )
            
            return {
                "success": response.status_code == 200,
                "data": response.json() if response.status_code == 200 else None,
                "status_code": response.status_code,
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Erro ao conectar com a API Grafeno",
        }

@router.post("/beneficiaries")
async def create_client_beneficiary(
    beneficiary: dict,
    account = Depends(get_current_grafeno_client)
):
    """
    Cadastra um novo beneficiário na Grafeno.
    Payload esperado: { "name": "...", "documentNumber": "...", "pixKey": "...", "keyType": "..." }
    """
    # Se for master, usa headers da conta principal
    if hasattr(account, 'is_grafeno_master') and account.is_grafeno_master:
        headers = get_grafeno_headers_master()
    else:
        headers = get_grafeno_headers(account)
    
    url = f"{GRAFENO_PAYMENTS_URL}/beneficiaries"
    
    # Preparar payload para Grafeno
    # A Grafeno parece exigir dados bancários mesmo se for só PIX em alguns contextos
    # Vamos adicionar dados fictícios se não forem fornecidos, para permitir o cadastro
    payload = {
        "name": beneficiary.get("name"),
        "documentNumber": beneficiary.get("documentNumber", "").replace(".", "").replace("-", "").replace("/", ""),
        "pixDetails": {
            "key": beneficiary.get("pixKey"),
            "keyType": beneficiary.get("keyType", "cpf").lower()
        },
        # Campos bancários obrigatórios (Workaround)
        "bankCode": "274", # Grafeno Padrão
        "agency": "0001",
        "account": "000000000",
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "data": response.json()
                }
            else:
                # Tenta extrair mensagem de erro detalhada
                try:
                    err_json = response.json()
                    # Formata erros de validação se houver
                    if "errors" in err_json:
                        details = []
                        for err in err_json["errors"]:
                            field = err.get("field", "Geral")
                            msg = err.get("message", "Erro")
                            details.append(f"{field}: {msg}")
                        error_msg = "; ".join(details)
                    else:
                        error_msg = err_json.get("message") or err_json.get("error") or response.text
                except:
                    error_msg = response.text
                
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_msg
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


# =====================================================
# PIX CHARGE (QR CODE)
# =====================================================

@router.post("/pix/charge")
async def create_pix_charge(
    value: float,
    payer_name: str,
    payer_document: str,
    payer_email: Optional[str] = None,
    due_date: Optional[str] = None,
    request: Request = None,
    account = Depends(get_current_grafeno_client),
    db: Session = Depends(get_db)
):
    """Cria uma cobrança PIX (QR Code)."""
    import uuid as uuid_lib
    from datetime import date as date_type, timedelta
    
    # Se for master, usa headers da conta principal
    if hasattr(account, 'is_grafeno_master') and account.is_grafeno_master:
        headers = get_grafeno_headers_master()
        account_uuid = account.uuid
        pix_key = "43aa6af5-c6e1-42f1-9cf9-d5606d1b8a75"
        account_email = account.email
    else:
        headers = get_grafeno_headers(account)
        account_uuid = account.uuid
        pix_key = account.pix_key if account.pix_key else "43aa6af5-c6e1-42f1-9cf9-d5606d1b8a75"
        account_email = account.email
    
    client_control_number = str(uuid_lib.uuid4())[:25]
    
    if due_date is None:
        # Padrão: Vencimento em 3 dias para evitar erro "deve ser depois de hoje"
        due_date = (date_type.today() + timedelta(days=3)).isoformat()
    
    payload = {
        "paymentMethod": "pix",
        "dueDate": due_date,
        "value": round(float(value), 2),
        "clientControlNumber": client_control_number,
        "expiresAfter": 1,
        "pix": {
            "key": pix_key,
            "keyType": "random"
        },
        "payer": {
            "name": payer_name,
            "email": payer_email or account_email,
            "documentNumber": payer_document.replace(".", "").replace("-", "").replace("/", ""),
            "address": {
                "zipCode": "01001000",
                "street": "Praça da Sé",
                "number": "1",
                "complement": "Lado ímpar",
                "neighborhood": "Sé",
                "city": "São Paulo",
                "state": "SP",
                "country": "BR"
            },
            "phone": {
                "countryCode": "55",
                "areaCode": "11",
                "number": "999999999"
            }
        },
        "grantor": {
            "name": "FLC BANK LTDA",
            "documentNumber": "88650081000116",
            "address": {
                "street": "Avenida Paulista",
                "number": "1000",
                "complement": "Conjunto 100",
                "zipCode": "01310-100",
                "neighborhood": "Bela Vista",
                "city": "São Paulo",
                "state": "SP",
                "country": "BR"
            }
        }
    }
    
    url = f"{GRAFENO_PAYMENTS_URL}/charges"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            try:
                response_data = response.json()
                logger.info(f"Grafeno Charge Response: {response_data}")
                with open("grafeno_debug.log", "w") as f:
                    import json
                    json.dump(response_data, f, indent=2)
            except:
                response_data = {"raw": response.text}
                logger.info(f"Grafeno Charge Response (Raw): {response.text}")
            
            if response.status_code in [200, 201]:
                # Registrar auditoria
                audit = AuditLog(
                    action="GRAFENO_PIX_CHARGE_CREATED",
                    entity_type="grafeno_account" if not hasattr(account, 'is_grafeno_master') else "user",
                    entity_id=account_uuid,
                    extra_data={
                        "client_control_number": client_control_number,
                        "value": value,
                        "payer_name": payer_name,
                    },
                    ip_address=request.client.host if request and request.client else None,
                )
                db.add(audit)
                db.commit()
                
                # Extrair dados da estrutura aninhada da resposta Grafeno
                # Estrutura: data.attributes.pixData.data.attributes
                data_obj = response_data.get("data", {})
                attrs = data_obj.get("attributes", {})
                
                # Extrair dados do PIX (aninhado em pixData.data.attributes)
                pix_data_container = attrs.get("pixData", {})
                pix_data_obj = pix_data_container.get("data", {})
                pix_attrs = pix_data_obj.get("attributes", {})
                
                # Extrair QR Code e EMV
                pix_emv = pix_attrs.get("emv")
                pix_image = pix_attrs.get("encodedImage")

                return {
                    "success": True,
                    "charge_id": data_obj.get("id"),
                    "status": attrs.get("status"),
                    "pix_qrcode": pix_image,
                    "pix_copy_paste": pix_emv,
                    "pix_txid": pix_data_obj.get("id"),
                    "client_control_number": attrs.get("clientControlNumber"),
                    "due_date": attrs.get("dueDate"),
                    "value": float(attrs.get("value", value)),
                }
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response_data.get("message") or response_data.get("error") or str(response_data),
                }
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Erro ao conectar com a API Grafeno",
        }


# =====================================================
# TRANSFERS LIST
# =====================================================

@router.get("/transfers")
async def get_client_transfers(
    page: int = 1,
    per_page: int = 50,
    status: Optional[str] = None,
    account = Depends(get_current_grafeno_client)
):
    """Lista as transferências da conta do cliente."""
    # Se for master, usa headers da conta principal
    if hasattr(account, 'is_grafeno_master') and account.is_grafeno_master:
        headers = get_grafeno_headers_master()
    else:
        headers = get_grafeno_headers(account)
    
    params = {
        "page[number]": page,
        "page[size]": per_page,
    }
    if status:
        params["filter[status]"] = status
    
    url = f"{GRAFENO_PAYMENTS_URL}/transfer_requests"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=headers,
                params=params,
                timeout=30.0
            )
            
            return {
                "success": response.status_code == 200,
                "data": response.json() if response.status_code == 200 else None,
                "status_code": response.status_code,
                "error": response.text if response.status_code != 200 else None,
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Erro ao conectar com a API Grafeno",
        }


# =====================================================
# PIX KEYS
# =====================================================

@router.get("/pix-keys")
async def get_pix_keys(
    account = Depends(get_current_grafeno_client)
):
    """
    Retorna as chaves PIX da conta.
    Como a Grafeno não expõe endpoint de chaves PIX via API,
    retornamos a chave EVP cadastrada no sistema.
    """
    # Se for master, retorna a chave principal
    if hasattr(account, 'is_grafeno_master') and account.is_grafeno_master:
        return {
            "success": True,
            "keys": [
                {
                    "key": "43aa6af5-c6e1-42f1-9cf9-d5606d1b8a75",
                    "type": "evp",
                    "type_label": "Chave Aleatória",
                    "status": "active",
                    "created_at": "2024-01-01T00:00:00Z",
                    "account_number": "08185935-7",
                    "agency": "0001",
                    "bank_code": "274",
                    "bank_name": "Grafeno",
                }
            ],
            "account_number": "08185935-7",
        }
    
    # Para contas cadastradas, retorna a chave PIX se houver
    keys = []
    if account.pix_key:
        keys.append({
            "key": account.pix_key,
            "type": "evp",
            "type_label": "Chave Aleatória",
            "status": "active",
            "created_at": account.created_at.isoformat() if account.created_at else None,
            "account_number": account.account_number,
            "agency": account.agency,
            "bank_code": account.bank_code or "274",
            "bank_name": "Grafeno",
        })
    
    return {
        "success": True,
        "keys": keys,
        "account_number": account.account_number,
    }


@router.get("/pix-keys/qrcode")
async def generate_pix_qrcode(
    value: Optional[float] = None,
    description: Optional[str] = None,
    account = Depends(get_current_grafeno_client)
):
    """
    Gera um QR Code PIX estático ou dinâmico para recebimento.
    """
    import qrcode
    import io
    import base64
    import crcmod
    
    def _calculate_crc16(payload: str) -> str:
        """Calcula o CRC16 CCITT-FALSE do payload."""
        crc16_func = crcmod.mkCrcFun(0x11021, initCrc=0xFFFF, xorOut=0x0000)
        crc = crc16_func(payload.encode('utf-8'))
        return format(crc, '04X')

    def _format_emv_field(id: str, val: str) -> str:
        """Formata um campo no padrão EMV (ID + Length + Value)."""
        length = str(len(val)).zfill(2)
        return f"{id}{length}{val}"

    def create_pix_payload(pix_key: str, merchant_name: str, merchant_city: str, amount: float = None, desc: str = None) -> str:
        """Gera payload PIX BR Code."""
        # Payload Format Indicator (ID 00)
        payload = _format_emv_field("00", "01")
        
        # Merchant Account Information - PIX (ID 26)
        gui = _format_emv_field("00", "br.gov.bcb.pix")
        pix = _format_emv_field("01", pix_key)
        if desc:
            desc_clean = desc[:25].upper()
            pix += _format_emv_field("02", desc_clean)
        merchant_info = gui + pix
        payload += _format_emv_field("26", merchant_info)
        
        # Merchant Category Code (ID 52)
        payload += _format_emv_field("52", "0000")
        
        # Transaction Currency (ID 53) - BRL
        payload += _format_emv_field("53", "986")
        
        # Transaction Amount (ID 54)
        if amount and amount > 0:
            amount_str = f"{float(amount):.2f}"
            payload += _format_emv_field("54", amount_str)
        
        # Country Code (ID 58)
        payload += _format_emv_field("58", "BR")
        
        # Merchant Name (ID 59)
        payload += _format_emv_field("59", merchant_name[:25].upper())
        
        # Merchant City (ID 60)
        payload += _format_emv_field("60", merchant_city[:15].upper())
        
        # CRC16 (ID 63)
        payload += "6304"
        crc = _calculate_crc16(payload)
        payload = payload[:-4] + f"6304{crc}"
        
        return payload
    
    # Dados da conta
    if hasattr(account, 'is_grafeno_master') and account.is_grafeno_master:
        pix_key = "43aa6af5-c6e1-42f1-9cf9-d5606d1b8a75"
        merchant_name = "FLC BANK"
        merchant_city = "SAO PAULO"
    else:
        pix_key = account.pix_key or "43aa6af5-c6e1-42f1-9cf9-d5606d1b8a75"
        merchant_name = (account.name or "FLC BANK")[:25].upper()
        merchant_city = (account.address_city or "SAO PAULO")[:15].upper()
    
    # Gerar payload PIX
    try:
        payload = create_pix_payload(
            pix_key=pix_key,
            merchant_name=merchant_name,
            merchant_city=merchant_city,
            amount=value,
            desc=description,
        )
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Erro ao gerar payload PIX",
        }
    
    # Gerar QR Code
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Converter para base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return {
            "success": True,
            "qrcode_base64": f"data:image/png;base64,{qr_base64}",
            "payload": payload,
            "pix_key": pix_key,
            "value": value,
            "description": description,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Erro ao gerar QR Code",
        }


class PixKeyValidationRequest(BaseModel):
    """Request para validar chave PIX"""
    pix_key: str
    pix_key_type: str  # cpf, cnpj, email, phone, evp


@router.post("/pix-keys/validate")
async def validate_pix_key(
    request_data: PixKeyValidationRequest,
    account = Depends(get_current_grafeno_client)
):
    """
    Valida uma chave PIX e retorna os dados do titular.
    """
    # Normalizar chave
    pix_key = request_data.pix_key.strip()
    key_type = request_data.pix_key_type.lower()
    
    # Validações básicas locais
    if key_type == "cpf":
        pix_key = pix_key.replace(".", "").replace("-", "")
        if len(pix_key) != 11:
            return {
                "success": False,
                "error": "CPF inválido",
                "message": "CPF deve ter 11 dígitos",
            }
    elif key_type == "cnpj":
        pix_key = pix_key.replace(".", "").replace("/", "").replace("-", "")
        if len(pix_key) != 14:
            return {
                "success": False,
                "error": "CNPJ inválido",
                "message": "CNPJ deve ter 14 dígitos",
            }
    elif key_type == "email":
        if "@" not in pix_key:
            return {
                "success": False,
                "error": "Email inválido",
                "message": "Email deve conter @",
            }
    elif key_type == "phone":
        pix_key = pix_key.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not pix_key.startswith("55"):
            pix_key = "55" + pix_key
        if len(pix_key) < 12 or len(pix_key) > 13:
            return {
                "success": False,
                "error": "Telefone inválido",
                "message": "Telefone deve estar no formato +55 DDD NÚMERO",
            }
    elif key_type == "evp":
        if len(pix_key) != 36:
            return {
                "success": False,
                "error": "Chave aleatória inválida",
                "message": "Chave EVP deve ser um UUID válido",
            }
    
    return {
        "success": True,
        "validated": True,
        "pix_key": pix_key,
        "pix_key_type": key_type,
        "message": "Chave PIX válida. Dados do titular serão confirmados na transferência.",
    }


# =====================================================
# BENEFICIÁRIOS - Gestão de beneficiários Grafeno
# =====================================================

class AddBeneficiaryRequest(BaseModel):
    """Request para adicionar beneficiário.
    
    IMPORTANTE: A Grafeno exige dados bancários completos para cadastro de beneficiário.
    Apenas a chave PIX não é suficiente.
    """
    name: str
    document_number: str  # CPF ou CNPJ (deve ser válido)
    bank_code: str  # Código do banco (obrigatório)
    agency: str  # Agência (obrigatório)
    account: str  # Conta com dígito (obrigatório)
    pix_key: Optional[str] = None
    pix_key_type: Optional[str] = None  # cpf, cnpj, email, phone, evp


@router.get("/beneficiaries")
async def list_beneficiaries(
    page: int = 1,
    per_page: int = 50,
    document_number: Optional[str] = None,
    account = Depends(get_current_grafeno_client),
):
    """
    Lista os beneficiários cadastrados na conta Grafeno.
    
    Os beneficiários devem ser cadastrados antes de criar transferências.
    """
    # Se for master, usa headers da conta principal
    if hasattr(account, 'is_grafeno_master') and account.is_grafeno_master:
        headers = get_grafeno_headers_master()
    else:
        headers = get_grafeno_headers(account)
    
    params = {
        "page[number]": page,
        "page[size]": per_page,
    }
    
    if document_number:
        clean_doc = document_number.replace(".", "").replace("-", "").replace("/", "")
        params["filter[documentNumber]"] = clean_doc
    
    url = f"{GRAFENO_PAYMENTS_URL}/beneficiaries"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers=headers,
                timeout=30.0
            )
            
            try:
                response_data = response.json()
            except:
                response_data = {"raw": response.text}
            
            # Formatar beneficiários para retorno
            beneficiaries = []
            if response.status_code == 200:
                data = response_data.get("data", [])
                if isinstance(data, list):
                    for b in data:
                        attrs = b.get("attributes", {})
                        beneficiaries.append({
                            "id": b.get("id"),
                            "name": attrs.get("name"),
                            "document_number": attrs.get("documentNumber"),
                            "bank_code": attrs.get("bankCode"),
                            "agency": attrs.get("agency"),
                            "account": attrs.get("account"),
                            "pix_key": attrs.get("pixDetails", {}).get("key") if attrs.get("pixDetails") else None,
                            "pix_key_type": attrs.get("pixDetails", {}).get("keyType") if attrs.get("pixDetails") else None,
                            "created_at": attrs.get("createdAt"),
                        })
            
            return {
                "success": response.status_code == 200,
                "beneficiaries": beneficiaries,
                "total": len(beneficiaries),
                "page": page,
                "per_page": per_page,
                "raw_response": response_data if response.status_code != 200 else None,
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Erro ao listar beneficiários",
        }


@router.post("/beneficiaries")
async def add_beneficiary(
    beneficiary: AddBeneficiaryRequest,
    request: Request,
    account = Depends(get_current_grafeno_client),
    db: Session = Depends(get_db)
):
    """
    Adiciona um novo beneficiário à conta Grafeno.
    
    O beneficiário deve ser cadastrado ANTES de criar uma transferência para ele.
    """
    # Se for master, usa headers da conta principal
    if hasattr(account, 'is_grafeno_master') and account.is_grafeno_master:
        headers = get_grafeno_headers_master()
        account_uuid = account.uuid
    else:
        headers = get_grafeno_headers(account)
        account_uuid = account.uuid
    
    # Limpar documento
    clean_doc = beneficiary.document_number.replace(".", "").replace("-", "").replace("/", "")
    
    # Montar payload
    payload = {
        "name": beneficiary.name,
        "documentNumber": clean_doc,
    }
    
    # Adicionar dados PIX se fornecidos
    if beneficiary.pix_key and beneficiary.pix_key_type:
        payload["pixDetails"] = {
            "key": beneficiary.pix_key,
            "keyType": beneficiary.pix_key_type,
        }
    
    # Adicionar dados bancários se fornecidos
    if beneficiary.bank_code:
        payload["bankCode"] = beneficiary.bank_code
    if beneficiary.agency:
        payload["agency"] = beneficiary.agency
    if beneficiary.account:
        payload["account"] = beneficiary.account
    
    url = f"{GRAFENO_PAYMENTS_URL}/beneficiaries"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            try:
                response_data = response.json()
            except:
                response_data = {"raw": response.text}
            
            success = response.status_code in [200, 201]
            
            # Extrair ID do beneficiário
            beneficiary_id = None
            if success and isinstance(response_data, dict):
                data = response_data.get("data", {})
                if isinstance(data, dict):
                    beneficiary_id = data.get("id")
            
            # Registrar auditoria
            audit = AuditLog(
                action="GRAFENO_BENEFICIARY_ADDED",
                entity_type="grafeno_account" if not hasattr(account, 'is_grafeno_master') else "user",
                entity_id=account_uuid,
                extra_data={
                    "beneficiary_id": beneficiary_id,
                    "name": beneficiary.name,
                    "document_number": clean_doc,
                    "success": success,
                },
                ip_address=request.client.host if request.client else None,
            )
            db.add(audit)
            db.commit()
            
            return {
                "success": success,
                "beneficiary_id": beneficiary_id,
                "message": "Beneficiário cadastrado com sucesso!" if success else "Erro ao cadastrar beneficiário",
                "data": response_data,
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Erro ao conectar com API Grafeno",
        }


@router.get("/beneficiaries/{beneficiary_id}")
async def get_beneficiary(
    beneficiary_id: str,
    account = Depends(get_current_grafeno_client),
):
    """
    Consulta os dados de um beneficiário específico.
    """
    # Se for master, usa headers da conta principal
    if hasattr(account, 'is_grafeno_master') and account.is_grafeno_master:
        headers = get_grafeno_headers_master()
    else:
        headers = get_grafeno_headers(account)
    
    url = f"{GRAFENO_PAYMENTS_URL}/beneficiaries/{beneficiary_id}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=headers,
                timeout=30.0
            )
            
            try:
                response_data = response.json()
            except:
                response_data = {"raw": response.text}
            
            if response.status_code == 200:
                data = response_data.get("data", {})
                attrs = data.get("attributes", {})
                
                return {
                    "success": True,
                    "beneficiary": {
                        "id": data.get("id"),
                        "name": attrs.get("name"),
                        "document_number": attrs.get("documentNumber"),
                        "bank_code": attrs.get("bankCode"),
                        "agency": attrs.get("agency"),
                        "account": attrs.get("account"),
                        "pix_key": attrs.get("pixDetails", {}).get("key") if attrs.get("pixDetails") else None,
                        "pix_key_type": attrs.get("pixDetails", {}).get("keyType") if attrs.get("pixDetails") else None,
                        "created_at": attrs.get("createdAt"),
                    },
                }
            else:
                return {
                    "success": False,
                    "error": "Beneficiário não encontrado",
                    "data": response_data,
                }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@router.delete("/beneficiaries/{beneficiary_id}")
async def delete_beneficiary(
    beneficiary_id: str,
    request: Request,
    account = Depends(get_current_grafeno_client),
    db: Session = Depends(get_db)
):
    """
    Remove um beneficiário cadastrado.
    """
    # Se for master, usa headers da conta principal
    if hasattr(account, 'is_grafeno_master') and account.is_grafeno_master:
        headers = get_grafeno_headers_master()
        account_uuid = account.uuid
    else:
        headers = get_grafeno_headers(account)
        account_uuid = account.uuid
    
    url = f"{GRAFENO_PAYMENTS_URL}/beneficiaries/{beneficiary_id}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                url,
                headers=headers,
                timeout=30.0
            )
            
            success = response.status_code in [200, 204]
            
            # Registrar auditoria
            audit = AuditLog(
                action="GRAFENO_BENEFICIARY_DELETED",
                entity_type="grafeno_account" if not hasattr(account, 'is_grafeno_master') else "user",
                entity_id=account_uuid,
                extra_data={
                    "beneficiary_id": beneficiary_id,
                    "success": success,
                },
                ip_address=request.client.host if request.client else None,
            )
            db.add(audit)
            db.commit()
            
            return {
                "success": success,
                "message": "Beneficiário removido com sucesso!" if success else "Erro ao remover beneficiário",
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
