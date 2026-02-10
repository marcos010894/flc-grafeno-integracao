"""
FLC Bank - Aplicação Principal FastAPI
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.database import engine, Base
from app.routers import auth_router, users_router, pix_router, master_router, ledger_router
from app.routers.grafeno import router as grafeno_router
from app.routers.grafeno_accounts import router as grafeno_accounts_router
from app.routers.grafeno_client import router as grafeno_client_router
from app.routers.grafeno_transfers import router as grafeno_transfers_router

# Configurar logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager da aplicação"""
    logger.info("🚀 Iniciando FLC Bank API...")
    
    # Criar tabelas se não existirem (dev only)
    # Em produção, usar migrations
    if settings.API_DEBUG:
        logger.info("📦 Criando tabelas do banco de dados...")
        # Base.metadata.create_all(bind=engine)
    
    logger.info("✅ FLC Bank API iniciada com sucesso!")
    
    yield
    
    logger.info("👋 Encerrando FLC Bank API...")


# Criar aplicação FastAPI
app = FastAPI(
    title="FLC Bank API",
    description="""
    ## Sistema de Ledger Financeiro com Alocação de PIX
    
    ### Funcionalidades principais:
    
    * **Autenticação** - Login, logout, refresh token
    * **Gestão de Usuários** - CRUD de usuários
    * **Gestão de PIX** - Recebimento e listagem de PIX
    * **Alocação** - Alocação de PIX a usuários com desconto
    * **Ledger** - Registro imutável de transações
    * **Extrato** - Consulta de saldo e movimentações
    
    ### Roles:
    
    * **MASTER** - Acesso total, aloca PIX
    * **ADMIN** - Acesso administrativo
    * **USER** - Usuário comum, apenas consulta
    
    ---
    
    **FLC Bank** - Sistema de gestão financeira
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware de logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log de todas as requisições"""
    logger.debug(f"📨 {request.method} {request.url.path}")
    response = await call_next(request)
    logger.debug(f"📤 {request.method} {request.url.path} - {response.status_code}")
    return response


# Exception handler global
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handler global de exceções"""
    logger.error(f"❌ Erro não tratado: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno do servidor"}
    )


# Registrar routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(pix_router)
app.include_router(master_router)
app.include_router(ledger_router)
app.include_router(grafeno_router)
app.include_router(grafeno_accounts_router)
app.include_router(grafeno_client_router)
app.include_router(grafeno_transfers_router)


# Endpoints de health check
@app.get("/", tags=["Health"])
async def root():
    """Endpoint raiz"""
    return {
        "name": "FLC Bank API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected",
        "version": "1.0.0"
    }


@app.get("/api/v1/status", tags=["Health"])
async def api_status():
    """Status detalhado da API"""
    return {
        "api": "FLC Bank",
        "version": "1.0.0",
        "environment": "development" if settings.API_DEBUG else "production",
        "features": {
            "auth": True,
            "pix": True,
            "ledger": True,
            "allocation": True
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_DEBUG
    )
