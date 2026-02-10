"""
FLC Bank - Router de Contas Grafeno (Onboarding)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
import httpx
import os

from app.database import get_db
from app.models.user import User
from app.models.grafeno_account import GrafenoAccount, OnboardingStatus
from app.models.audit import AuditLog
from app.schemas.grafeno_account import (
    GrafenoAccountCreate, 
    GrafenoAccountResponse, 
    GrafenoAccountListResponse
)
from app.utils.security import get_current_master
from app.config import settings

router = APIRouter(prefix="/grafeno-accounts", tags=["Grafeno Accounts"])

# URL da API Grafeno para onboarding
GRAFENO_ONBOARDING_URL = "https://cadastros.grafeno.be/api/onboardings/v2/complete/clients"

# Token do Grafeno (mesmo usado no serviço de pagamentos)
GRAFENO_TOKEN = os.getenv("GRAFENO_API_TOKEN", "38387c01-b705-4425-9006-59a8c134d8b0.9V9v4B_L0XVcx-tmrEEUMNAKvSk")


# =============================================================================
# ENDPOINT PÚBLICO PARA REGISTRO DE CONTA
# =============================================================================

@router.post("/register", response_model=dict)
async def register_grafeno_account(
    account_data: GrafenoAccountCreate,
    db: Session = Depends(get_db)
):
    """
    Endpoint PÚBLICO para registro de nova conta Grafeno.
    Não requer autenticação - usado no formulário de cadastro.
    """
    
    # Verificar se já existe conta com esse CNPJ
    clean_cnpj = account_data.documentNumber.replace(".", "").replace("/", "").replace("-", "")
    existing = db.query(GrafenoAccount).filter(
        GrafenoAccount.document_number == clean_cnpj
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Já existe uma conta cadastrada com este CNPJ"
        )
    
    # Criar registro local
    grafeno_account = GrafenoAccount(
        # Dados da empresa
        name=account_data.name,
        company_name=account_data.companyName,
        document_number=clean_cnpj,
        legal_nature=account_data.legalNature.value,
        tax_regime=account_data.taxRegime.value if account_data.taxRegime else None,
        nire=account_data.nire,
        
        # Contato
        commercial_phone=account_data.commercialPhone,
        email=account_data.email,
        
        # Endereço
        address_street=account_data.address.street,
        address_number=account_data.address.number,
        address_complement=account_data.address.complement,
        address_neighborhood=account_data.address.neighborhood,
        address_city=account_data.address.city,
        address_state=account_data.address.state,
        address_country=account_data.address.country,
        address_zipcode=account_data.address.zipCode.replace("-", ""),
        
        # Administrador
        admin_name=account_data.administrator.name,
        admin_email=account_data.administrator.email,
        admin_phone=account_data.administrator.phone,
        admin_document=account_data.administrator.documentNumber.replace(".", "").replace("-", ""),
        
        # Faturamento
        revenue_informed=str(account_data.revenue.informed).lower() if account_data.revenue else "false",
        revenue_value=account_data.revenue.value if account_data.revenue else None,
        revenue_period_start=account_data.revenue.periodStartAt if account_data.revenue else None,
        revenue_period_end=account_data.revenue.periodEndAt if account_data.revenue else None,
        
        # Assinaturas
        required_signers=account_data.requiredSigners,
        
        # Capital Social
        social_capital=account_data.socialCapital,
        
        # Senha local
        password=account_data.password,
        
        # Arquivo do contrato social
        article_of_association_filename=account_data.articleOfAssociation.filename,
        article_of_association_content=account_data.articleOfAssociation.content,
        
        # Documento de identidade do administrador (se fornecido)
        admin_identity_filename=account_data.administrator.identityDocument.filename if account_data.administrator.identityDocument else None,
        admin_identity_content=account_data.administrator.identityDocument.content if account_data.administrator.identityDocument else None,
        
        # Status inicial
        status=OnboardingStatus.PENDING
    )
    
    db.add(grafeno_account)
    db.flush()
    
    # Preparar payload para Grafeno
    grafeno_payload = {
        "name": account_data.name,
        "companyName": account_data.companyName,
        "legalNature": account_data.legalNature.value,
        "commercialPhone": account_data.commercialPhone,
        "email": account_data.email,
        "documentNumber": clean_cnpj,
        "address": {
            "street": account_data.address.street,
            "number": account_data.address.number,
            "complement": account_data.address.complement or "",
            "neighborhood": account_data.address.neighborhood,
            "city": account_data.address.city,
            "state": account_data.address.state,
            "country": account_data.address.country,
            "zipCode": account_data.address.zipCode.replace("-", "")
        },
        "administrator": {
            "name": account_data.administrator.name,
            "email": account_data.administrator.email,
            "phone": account_data.administrator.phone,
            "documentNumber": account_data.administrator.documentNumber.replace(".", "").replace("-", ""),
        },
        "articleOfAssociation": {
            "filename": account_data.articleOfAssociation.filename,
            "content": account_data.articleOfAssociation.content
        },
        "requiredSigners": account_data.requiredSigners,
        "revenue": {"informed": False}
    }
    
    # Adicionar documento de identidade se fornecido
    if account_data.administrator.identityDocument:
        grafeno_payload["administrator"]["identityDocument"] = {
            "filename": account_data.administrator.identityDocument.filename,
            "content": account_data.administrator.identityDocument.content
        }
    
    # Adicionar campos opcionais
    if account_data.socialCapital:
        grafeno_payload["socialCapital"] = account_data.socialCapital
    if account_data.nire:
        grafeno_payload["nire"] = account_data.nire
    if account_data.taxRegime:
        grafeno_payload["taxRegime"] = account_data.taxRegime.value
    if account_data.revenue and account_data.revenue.informed:
        grafeno_payload["revenue"] = {
            "informed": True,
            "value": float(account_data.revenue.value) if account_data.revenue.value else None,
            "periodStartAt": account_data.revenue.periodStartAt or "",
            "periodEndAt": account_data.revenue.periodEndAt or ""
        }
    
    # Tentar enviar para Grafeno
    grafeno_error = None
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": GRAFENO_TOKEN
            }
            
            response = await client.post(
                GRAFENO_ONBOARDING_URL,
                json=grafeno_payload,
                headers=headers
            )
            
            response_text = response.text
            if response_text:
                try:
                    grafeno_response = response.json()
                except:
                    grafeno_response = {"raw_response": response_text}
            else:
                grafeno_response = {"status_code": response.status_code, "message": "Empty response"}
            
            if response.status_code in [200, 201]:
                grafeno_account.status = OnboardingStatus.SUBMITTED
                grafeno_account.submitted_at = datetime.now()
                grafeno_account.grafeno_id = grafeno_response.get("id") or grafeno_response.get("onboardingId")
                grafeno_account.grafeno_response = grafeno_response
            else:
                grafeno_error = grafeno_response
                grafeno_account.grafeno_response = {
                    "error": True,
                    "status_code": response.status_code,
                    "response": grafeno_response
                }
                
    except httpx.TimeoutException:
        grafeno_error = "Timeout ao conectar com Grafeno"
        grafeno_account.grafeno_response = {"error": "timeout"}
    except Exception as e:
        grafeno_error = str(e)
        grafeno_account.grafeno_response = {"error": str(e)}
    
    # Auditoria (sem user_id pois é público)
    audit = AuditLog(
        user_id=None,
        action="GRAFENO_ACCOUNT_REGISTERED",
        entity_type="grafeno_account",
        entity_id=grafeno_account.uuid,
        extra_data={
            "company_name": account_data.companyName,
            "document_number": account_data.documentNumber,
            "grafeno_submitted": grafeno_account.status == OnboardingStatus.SUBMITTED,
            "grafeno_error": str(grafeno_error) if grafeno_error else None
        }
    )
    db.add(audit)
    
    db.commit()
    db.refresh(grafeno_account)
    
    return {
        "success": True,
        "message": "Conta registrada com sucesso! Aguarde a aprovação." if not grafeno_error else f"Conta salva. Envio para Grafeno pendente: {grafeno_error}",
        "uuid": grafeno_account.uuid,
        "status": grafeno_account.status.value,
        "grafeno_submitted": grafeno_account.status == OnboardingStatus.SUBMITTED
    }


# =============================================================================
# ENDPOINTS PROTEGIDOS (REQUEREM MASTER)
# =============================================================================

@router.post("/create", response_model=dict)
async def create_grafeno_account(
    account_data: GrafenoAccountCreate,
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Cria uma nova conta mãe Grafeno (onboarding).
    Salva os dados localmente e envia para a API do Grafeno.
    """
    
    # Verificar se já existe conta com esse CNPJ
    existing = db.query(GrafenoAccount).filter(
        GrafenoAccount.document_number == account_data.documentNumber.replace(".", "").replace("/", "").replace("-", "")
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Já existe uma conta cadastrada com este CNPJ"
        )
    
    # Criar registro local primeiro
    grafeno_account = GrafenoAccount(
        # Dados da empresa
        name=account_data.name,
        company_name=account_data.companyName,
        document_number=account_data.documentNumber.replace(".", "").replace("/", "").replace("-", ""),
        legal_nature=account_data.legalNature.value,
        tax_regime=account_data.taxRegime.value if account_data.taxRegime else None,
        nire=account_data.nire,
        
        # Contato
        commercial_phone=account_data.commercialPhone,
        email=account_data.email,
        
        # Endereço
        address_street=account_data.address.street,
        address_number=account_data.address.number,
        address_complement=account_data.address.complement,
        address_neighborhood=account_data.address.neighborhood,
        address_city=account_data.address.city,
        address_state=account_data.address.state,
        address_country=account_data.address.country,
        address_zipcode=account_data.address.zipCode.replace("-", ""),
        
        # Administrador
        admin_name=account_data.administrator.name,
        admin_email=account_data.administrator.email,
        admin_phone=account_data.administrator.phone,
        admin_document=account_data.administrator.documentNumber.replace(".", "").replace("-", ""),
        
        # Faturamento
        revenue_informed=str(account_data.revenue.informed).lower() if account_data.revenue else "false",
        revenue_value=account_data.revenue.value if account_data.revenue else None,
        revenue_period_start=account_data.revenue.periodStartAt if account_data.revenue else None,
        revenue_period_end=account_data.revenue.periodEndAt if account_data.revenue else None,
        
        # Assinaturas
        required_signers=account_data.requiredSigners,
        
        # Capital Social
        social_capital=account_data.socialCapital,
        
        # Senha local
        password=account_data.password,
        
        # Arquivo do contrato social (salvar nome e conteúdo para retry)
        article_of_association_filename=account_data.articleOfAssociation.filename,
        article_of_association_content=account_data.articleOfAssociation.content,
        
        # Documento de identidade do administrador (se fornecido)
        admin_identity_filename=account_data.administrator.identityDocument.filename if account_data.administrator.identityDocument else None,
        admin_identity_content=account_data.administrator.identityDocument.content if account_data.administrator.identityDocument else None,
        
        # Status inicial
        status=OnboardingStatus.PENDING
    )
    
    db.add(grafeno_account)
    db.flush()  # Para obter o ID
    
    # Preparar payload para Grafeno
    grafeno_payload = {
        "name": account_data.name,
        "companyName": account_data.companyName,
        "legalNature": account_data.legalNature.value,
        "commercialPhone": account_data.commercialPhone,
        "email": account_data.email,
        "documentNumber": account_data.documentNumber.replace(".", "").replace("/", "").replace("-", ""),
        "address": {
            "street": account_data.address.street,
            "number": account_data.address.number,
            "complement": account_data.address.complement or "",
            "neighborhood": account_data.address.neighborhood,
            "city": account_data.address.city,
            "state": account_data.address.state,
            "country": account_data.address.country,
            "zipCode": account_data.address.zipCode.replace("-", "")
        },
        "administrator": {
            "name": account_data.administrator.name,
            "email": account_data.administrator.email,
            "phone": account_data.administrator.phone,
            "documentNumber": account_data.administrator.documentNumber.replace(".", "").replace("-", ""),
            **({"identityDocument": {
                "filename": account_data.administrator.identityDocument.filename,
                "content": account_data.administrator.identityDocument.content
            }} if account_data.administrator.identityDocument else {})
        },
        "articleOfAssociation": {
            "filename": account_data.articleOfAssociation.filename,
            "content": account_data.articleOfAssociation.content
        },
        "requiredSigners": account_data.requiredSigners,
        "revenue": {
            "informed": False
        }
    }
    
    # Adicionar capital social se informado
    if account_data.socialCapital:
        grafeno_payload["socialCapital"] = account_data.socialCapital
    
    # Adicionar NIRE se informado
    if account_data.nire:
        grafeno_payload["nire"] = account_data.nire
    
    # Adicionar regime tributário se informado
    if account_data.taxRegime:
        grafeno_payload["taxRegime"] = account_data.taxRegime.value
    
    # Atualizar faturamento se informado
    if account_data.revenue and account_data.revenue.informed:
        grafeno_payload["revenue"] = {
            "informed": True,
            "value": float(account_data.revenue.value) if account_data.revenue.value else None,
            "periodStartAt": account_data.revenue.periodStartAt or "",
            "periodEndAt": account_data.revenue.periodEndAt or ""
        }
    
    # Tentar enviar para Grafeno
    grafeno_response = None
    grafeno_error = None
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": GRAFENO_TOKEN
            }
            
            response = await client.post(
                GRAFENO_ONBOARDING_URL,
                json=grafeno_payload,
                headers=headers
            )
            
            # Verificar se a resposta tem conteúdo
            response_text = response.text
            if response_text:
                try:
                    grafeno_response = response.json()
                except:
                    grafeno_response = {"raw_response": response_text}
            else:
                grafeno_response = {"status_code": response.status_code, "message": "Empty response"}
            
            if response.status_code in [200, 201]:
                # Sucesso - atualizar status
                grafeno_account.status = OnboardingStatus.SUBMITTED
                grafeno_account.submitted_at = datetime.now()
                grafeno_account.grafeno_id = grafeno_response.get("id") or grafeno_response.get("onboardingId")
                grafeno_account.grafeno_response = grafeno_response
            else:
                # Erro da API - manter como pendente mas salvar resposta
                grafeno_error = grafeno_response
                grafeno_account.grafeno_response = {
                    "error": True,
                    "status_code": response.status_code,
                    "response": grafeno_response
                }
                
    except httpx.TimeoutException:
        grafeno_error = "Timeout ao conectar com Grafeno"
        grafeno_account.grafeno_response = {"error": "timeout"}
    except Exception as e:
        grafeno_error = str(e)
        grafeno_account.grafeno_response = {"error": str(e)}
    
    # Auditoria
    audit = AuditLog(
        user_id=current_user.id,
        action="GRAFENO_ACCOUNT_CREATED",
        entity_type="grafeno_account",
        entity_id=grafeno_account.uuid,
        extra_data={
            "company_name": account_data.companyName,
            "document_number": account_data.documentNumber,
            "grafeno_submitted": grafeno_account.status == OnboardingStatus.SUBMITTED,
            "grafeno_error": grafeno_error
        }
    )
    db.add(audit)
    
    db.commit()
    db.refresh(grafeno_account)
    
    return {
        "success": True,
        "message": "Conta criada com sucesso" if not grafeno_error else f"Conta salva localmente. Erro ao enviar para Grafeno: {grafeno_error}",
        "uuid": grafeno_account.uuid,
        "status": grafeno_account.status.value,
        "grafeno_id": grafeno_account.grafeno_id,
        "grafeno_submitted": grafeno_account.status == OnboardingStatus.SUBMITTED
    }


@router.get("/list", response_model=GrafenoAccountListResponse)
async def list_grafeno_accounts(
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Lista todas as contas Grafeno cadastradas.
    """
    accounts = db.query(GrafenoAccount).order_by(GrafenoAccount.created_at.desc()).all()
    
    return GrafenoAccountListResponse(
        accounts=[
            GrafenoAccountResponse(
                uuid=acc.uuid,
                name=acc.name,
                company_name=acc.company_name,
                document_number=acc.document_number,
                legal_nature=acc.legal_nature,
                email=acc.email,
                commercial_phone=acc.commercial_phone,
                status=acc.status.value,
                grafeno_id=acc.grafeno_id,
                account_number=acc.account_number,
                agency=acc.agency,
                pix_key=acc.pix_key,
                created_at=acc.created_at,
                submitted_at=acc.submitted_at,
                approved_at=acc.approved_at
            )
            for acc in accounts
        ],
        total=len(accounts)
    )


@router.get("/{account_uuid}", response_model=dict)
async def get_grafeno_account(
    account_uuid: str,
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Retorna detalhes de uma conta Grafeno.
    """
    account = db.query(GrafenoAccount).filter(
        GrafenoAccount.uuid == account_uuid
    ).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conta não encontrada"
        )
    
    return {
        "uuid": account.uuid,
        "name": account.name,
        "company_name": account.company_name,
        "document_number": account.document_number,
        "legal_nature": account.legal_nature,
        "tax_regime": account.tax_regime,
        "email": account.email,
        "commercial_phone": account.commercial_phone,
        "nire": account.nire,
        "address": {
            "street": account.address_street,
            "number": account.address_number,
            "complement": account.address_complement,
            "neighborhood": account.address_neighborhood,
            "city": account.address_city,
            "state": account.address_state,
            "country": account.address_country,
            "zipCode": account.address_zipcode
        },
        "administrator": {
            "name": account.admin_name,
            "email": account.admin_email,
            "phone": account.admin_phone,
            "documentNumber": account.admin_document
        },
        "required_signers": account.required_signers,
        "status": account.status.value,
        "grafeno_id": account.grafeno_id,
        "grafeno_response": account.grafeno_response,
        "account_number": account.account_number,
        "agency": account.agency,
        "bank_code": account.bank_code,
        "pix_key": account.pix_key,
        "password": account.password,  # Retorna a senha como solicitado
        "created_at": account.created_at.isoformat() if account.created_at else None,
        "submitted_at": account.submitted_at.isoformat() if account.submitted_at else None,
        "approved_at": account.approved_at.isoformat() if account.approved_at else None
    }


@router.post("/{account_uuid}/retry-submit")
async def retry_submit_grafeno(
    account_uuid: str,
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Tenta reenviar o onboarding para o Grafeno.
    """
    account = db.query(GrafenoAccount).filter(
        GrafenoAccount.uuid == account_uuid
    ).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conta não encontrada"
        )
    
    if account.status not in [OnboardingStatus.PENDING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Conta já foi submetida. Status atual: {account.status.value}"
        )
    
    # Verificar se temos o arquivo do contrato social
    if not account.article_of_association_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contrato social não encontrado. Recrie a conta com o documento."
        )
    
    # Preparar payload para Grafeno
    grafeno_payload = {
        "name": account.name,
        "companyName": account.company_name,
        "legalNature": account.legal_nature,
        "commercialPhone": account.commercial_phone,
        "email": account.email,
        "documentNumber": account.document_number,
        "address": {
            "street": account.address_street,
            "number": account.address_number,
            "complement": account.address_complement or "",
            "neighborhood": account.address_neighborhood,
            "city": account.address_city,
            "state": account.address_state,
            "country": account.address_country,
            "zipCode": account.address_zipcode
        },
        "administrator": {
            "name": account.admin_name,
            "email": account.admin_email,
            "phone": account.admin_phone,
            "documentNumber": account.admin_document
        },
        "articleOfAssociation": {
            "filename": account.article_of_association_filename,
            "content": account.article_of_association_content
        },
        "requiredSigners": account.required_signers,
        "revenue": {
            "informed": False
        }
    }
    
    # Adicionar documento de identidade do administrador se existir
    if account.admin_identity_content:
        grafeno_payload["administrator"]["identityDocument"] = {
            "filename": account.admin_identity_filename,
            "content": account.admin_identity_content
        }
    
    # Adicionar campos opcionais
    if account.nire:
        grafeno_payload["nire"] = account.nire
    if account.tax_regime:
        grafeno_payload["taxRegime"] = account.tax_regime
    if account.social_capital:
        grafeno_payload["socialCapital"] = float(account.social_capital)
    
    # Tentar enviar para Grafeno
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": GRAFENO_TOKEN
            }
            
            response = await client.post(
                GRAFENO_ONBOARDING_URL,
                json=grafeno_payload,
                headers=headers
            )
            
            response_text = response.text
            try:
                grafeno_response = response.json() if response_text else {}
            except:
                grafeno_response = {"raw_response": response_text, "status_code": response.status_code}
            
            if response.status_code in [200, 201]:
                account.status = OnboardingStatus.SUBMITTED
                account.submitted_at = datetime.now()
                account.grafeno_id = grafeno_response.get("id") or grafeno_response.get("onboardingId")
                account.grafeno_response = grafeno_response
                db.commit()
                
                return {
                    "success": True,
                    "message": "Conta enviada para o Grafeno com sucesso!",
                    "grafeno_id": account.grafeno_id,
                    "status": account.status.value
                }
            else:
                account.grafeno_response = {
                    "error": True,
                    "status_code": response.status_code,
                    "response": grafeno_response
                }
                db.commit()
                
                return {
                    "success": False,
                    "message": f"Erro do Grafeno: HTTP {response.status_code}",
                    "grafeno_response": grafeno_response
                }
                
    except httpx.TimeoutException:
        return {"success": False, "message": "Timeout ao conectar com Grafeno"}
    except Exception as e:
        return {"success": False, "message": f"Erro: {str(e)}"}


@router.post("/{account_uuid}/activate")
async def activate_grafeno_account(
    account_uuid: str,
    account_number: str = None,
    agency: str = "0001",
    pix_key: str = None,
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Ativa uma conta Grafeno manualmente.
    Útil para contas já aprovadas no Grafeno que precisam ser ativadas no sistema.
    """
    from app.services.email import email_service
    
    account = db.query(GrafenoAccount).filter(
        GrafenoAccount.uuid == account_uuid
    ).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conta não encontrada"
        )
    
    # Atualizar dados da conta
    account.status = OnboardingStatus.ACTIVE
    account.approved_at = datetime.now()
    
    if account_number:
        account.account_number = account_number
    if agency:
        account.agency = agency
    if pix_key:
        account.pix_key = pix_key
    
    # Auditoria
    audit = AuditLog(
        user_id=current_user.id,
        action="GRAFENO_ACCOUNT_ACTIVATED",
        entity_type="grafeno_account",
        entity_id=account.uuid,
        extra_data={
            "account_number": account_number,
            "agency": agency,
            "pix_key": pix_key
        }
    )
    db.add(audit)
    db.commit()
    
    # Enviar notificação por email
    if account.email:
        try:
            email_service.notify_account_status(
                user_email=account.email,
                user_name=account.admin_name or account.name or "Cliente",
                company_name=account.company_name or account.name or "Empresa",
                status="approved",
            )
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
    
    return {
        "success": True,
        "message": "Conta ativada com sucesso!",
        "uuid": account.uuid,
        "status": account.status.value,
        "account_number": account.account_number,
        "agency": account.agency
    }


@router.post("/setup-demo")
async def setup_demo_account(
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Cria ou atualiza uma conta demo para testes.
    Usa a conta principal do Grafeno configurada nas variáveis de ambiente.
    """
    # Verificar se já existe uma conta demo
    demo_document = "00000000000191"  # CNPJ de teste
    
    existing = db.query(GrafenoAccount).filter(
        GrafenoAccount.document_number == demo_document
    ).first()
    
    if existing:
        # Ativar a conta existente
        existing.status = OnboardingStatus.ACTIVE
        existing.approved_at = datetime.now()
        existing.account_number = os.getenv("GRAFENO_ACCOUNT", "08185935-7")
        existing.agency = os.getenv("GRAFENO_AGENCY", "0001")
        existing.password = "demo123"
        db.commit()
        
        return {
            "success": True,
            "message": "Conta demo atualizada!",
            "uuid": existing.uuid,
            "document_number": "00.000.000/0001-91",
            "password": "demo123",
            "account_number": existing.account_number
        }
    
    # Criar nova conta demo
    demo_account = GrafenoAccount(
        name="Empresa Demo",
        company_name="Empresa Demonstração Ltda",
        document_number=demo_document,
        legal_nature="LTDA",
        commercial_phone="11999999999",
        email="demo@flcbank.com.br",
        address_street="Av. Paulista",
        address_number="1000",
        address_neighborhood="Bela Vista",
        address_city="São Paulo",
        address_state="SP",
        address_country="BR",
        address_zipcode="01310100",
        admin_name="Usuário Demo",
        admin_email="demo@flcbank.com.br",
        admin_phone="11999999999",
        admin_document="00000000000",
        required_signers=1,
        status=OnboardingStatus.ACTIVE,
        approved_at=datetime.now(),
        password="demo123",
        account_number=os.getenv("GRAFENO_ACCOUNT", "08185935-7"),
        agency=os.getenv("GRAFENO_AGENCY", "0001"),
        bank_code="274",
    )
    
    db.add(demo_account)
    db.commit()
    db.refresh(demo_account)
    
    return {
        "success": True,
        "message": "Conta demo criada!",
        "uuid": demo_account.uuid,
        "document_number": "00.000.000/0001-91",
        "password": "demo123",
        "account_number": demo_account.account_number,
        "login_info": {
            "cnpj": "00.000.000/0001-91",
            "senha": "demo123"
        }
    }
