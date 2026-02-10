"""
FLC Bank - Router de Autenticação
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import get_db
from app.models.user import User
from app.models.audit import AuditLog
from app.schemas.user import UserLogin, Token, UserResponse, UserCreate
from app.utils.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token, decode_token,
    get_current_user
)
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Autenticação de usuário.
    Retorna access_token e refresh_token.
    """
    # Buscar usuário
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user or not verify_password(credentials.password, user.password_hash):
        # Registrar tentativa falha
        audit = AuditLog(
            user_email=credentials.email,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            action="LOGIN_FAILED",
            extra_data={"reason": "invalid_credentials"}
        )
        db.add(audit)
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo ou bloqueado"
        )
    
    # Criar tokens
    token_data = {
        "sub": user.uuid,
        "email": user.email,
        "role": user.role.value
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    # Atualizar último login
    user.last_login_at = datetime.utcnow()
    
    # Registrar login
    audit = AuditLog(
        user_id=user.id,
        user_email=user.email,
        user_role=user.role.value,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        action="LOGIN_SUCCESS"
    )
    db.add(audit)
    db.commit()
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Renova o access_token usando o refresh_token.
    """
    payload = decode_token(refresh_token)
    
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )
    
    user_uuid = payload.get("sub")
    user = db.query(User).filter(User.uuid == user_uuid).first()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado ou inativo"
        )
    
    # Criar novos tokens
    token_data = {
        "sub": user.uuid,
        "email": user.email,
        "role": user.role.value
    }
    
    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)
    
    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Retorna informações do usuário autenticado.
    """
    return current_user


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout do usuário (invalida tokens).
    """
    # Registrar logout
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        user_role=current_user.role.value,
        ip_address=request.client.host if request.client else None,
        action="LOGOUT"
    )
    db.add(audit)
    db.commit()
    
    return {"message": "Logout realizado com sucesso"}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Registro de novo usuário.
    Por padrão, novos usuários são criados com role USER.
    """
    # Verificar se email já existe
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado"
        )
    
    # Verificar CPF/CNPJ
    if user_data.cpf_cnpj:
        existing_cpf = db.query(User).filter(User.cpf_cnpj == user_data.cpf_cnpj).first()
        if existing_cpf:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CPF/CNPJ já cadastrado"
            )
    
    # Criar usuário
    user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        cpf_cnpj=user_data.cpf_cnpj,
        phone=user_data.phone,
        pix_key=user_data.pix_key,
        pix_key_type=user_data.pix_key_type,
        role=user_data.role
    )
    
    db.add(user)
    
    # Registrar auditoria
    audit = AuditLog(
        user_email=user_data.email,
        ip_address=request.client.host if request.client else None,
        action="USER_REGISTERED",
        entity_type="USER",
        new_values={
            "email": user_data.email,
            "full_name": user_data.full_name,
            "role": user_data.role.value
        }
    )
    db.add(audit)
    
    db.commit()
    db.refresh(user)
    
    # Retornar com id para uso no fluxo de registro + depósito
    return {
        "id": user.id,
        "uuid": user.uuid,
        "email": user.email,
        "full_name": user.full_name,
        "cpf_cnpj": user.cpf_cnpj,
        "phone": user.phone,
        "role": user.role.value,
        "status": user.status.value,
        "pix_key": user.pix_key,
        "pix_key_type": user.pix_key_type.value if user.pix_key_type else None,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }
