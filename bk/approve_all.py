"""
Script simples para aprovar TODAS as transferencias pendentes
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.grafeno import GrafenoService

async def approve_all():
    grafeno = GrafenoService()
    
    print("Buscando transferencias pendentes...")
    result = await grafeno.auto_approve_pending_transfers(auto_approve_all=True)
    
    print(f"\nResultado:")
    print(f"Aprovadas: {result.get('approved')}")
    print(f"Rejeitadas: {result.get('rejected')}")
    print(f"Total: {result.get('total')}")
    
    if result.get('errors'):
        print(f"\nErros:")
        for error in result.get('errors'):
            print(f"  - {error}")

if __name__ == "__main__":
    asyncio.run(approve_all())
