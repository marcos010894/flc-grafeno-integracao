"""
FLC Bank - Router de Usuários
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.user import User, UserRole, UserStatus
from app.schemas.user import UserResponse, UserUpdate, UserListResponse
from app.utils.security import get_current_user, get_current_master, get_password_hash

router = APIRouter(prefix="/users", tags=["Usuários"])


@router.get("/", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    role: Optional[UserRole] = None,
    status: Optional[UserStatus] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Lista usuários (apenas para MASTER).
    Suporta filtros por role, status e busca.
    """
    query = db.query(User)
    
    if role:
        query = query.filter(User.role == role)
    if status:
        query = query.filter(User.status == status)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.full_name.ilike(search_term)) |
            (User.email.ilike(search_term)) |
            (User.cpf_cnpj.ilike(search_term))
        )
    
    total = query.count()
    users = query.order_by(User.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    
    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/active", response_model=list[UserResponse])
async def list_active_users(
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Lista apenas usuários ativos (para seleção em alocação).
    """
    users = db.query(User).filter(
        User.status == UserStatus.ACTIVE,
        User.role == UserRole.USER
    ).order_by(User.full_name).all()
    
    return users


@router.get("/{user_uuid}", response_model=UserResponse)
async def get_user(
    user_uuid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtém detalhes de um usuário.
    Usuários comuns só podem ver seus próprios dados.
    """
    # Usuário comum só pode ver a si mesmo
    if not current_user.is_admin and current_user.uuid != user_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para ver este usuário"
        )
    
    user = db.query(User).filter(User.uuid == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    return user


@router.put("/{user_uuid}", response_model=UserResponse)
async def update_user(
    user_uuid: str,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Atualiza dados de um usuário.
    Usuários comuns só podem atualizar seus próprios dados (exceto status).
    """
    # Buscar usuário
    user = db.query(User).filter(User.uuid == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    # Verificar permissão
    if not current_user.is_admin and current_user.uuid != user_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para editar este usuário"
        )
    
    # Usuário comum não pode alterar status
    if not current_user.is_admin and user_data.status is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para alterar status"
        )
    
    # Atualizar campos
    update_data = user_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    return user


@router.post("/{user_uuid}/block")
async def block_user(
    user_uuid: str,
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Bloqueia um usuário (apenas MASTER).
    """
    user = db.query(User).filter(User.uuid == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    if user.role == UserRole.MASTER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível bloquear um MASTER"
        )
    
    user.status = UserStatus.BLOCKED
    db.commit()
    
    return {"message": "Usuário bloqueado com sucesso"}


@router.post("/{user_uuid}/activate")
async def activate_user(
    user_uuid: str,
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Ativa um usuário (apenas MASTER).
    """
    user = db.query(User).filter(User.uuid == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    user.status = UserStatus.ACTIVE
    db.commit()
    
    return {"message": "Usuário ativado com sucesso"}


@router.delete("/{user_uuid}")
async def delete_user(
    user_uuid: str,
    current_user: User = Depends(get_current_master),
    db: Session = Depends(get_db)
):
    """
    Remove um usuário e todos os dados relacionados (apenas MASTER).
    Como o ledger é imutável (para auditoria), apenas anonimizamos o usuário.
    """
    from sqlalchemy import text
    
    user = db.query(User).filter(User.uuid == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    if user.role == UserRole.MASTER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível remover um MASTER"
        )
    
    user_id = user.id
    user_email = user.email
    
    try:
        # Anonimizar e bloquear o usuário (ledger é preservado para auditoria)
        db.execute(text("""
            UPDATE users SET 
                email = CONCAT('deleted_', id, '@removed.local'),
                full_name = 'Usuário Removido',
                cpf_cnpj = NULL,
                phone = NULL,
                pix_key = NULL,
                status = 'BLOCKED'
            WHERE id = :user_id
        """), {"user_id": user_id})
        
        db.commit()
        
        return {
            "message": f"Usuário {user_email} removido com sucesso",
            "note": "Dados anonimizados, histórico de ledger preservado para auditoria"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao remover usuário: {str(e)}"
        )
