"""
FLC Bank - Routers Package
"""

from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.pix import router as pix_router
from app.routers.master import router as master_router
from app.routers.ledger import router as ledger_router

__all__ = [
    "auth_router", "users_router", "pix_router", 
    "master_router", "ledger_router"
]
