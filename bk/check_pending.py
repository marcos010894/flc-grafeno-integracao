"""
Verificacao rapida de transferencias pendentes
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.grafeno import GrafenoService

async def check():
    grafeno = GrafenoService()
    pending = await grafeno.list_pending_transfers()
    
    if pending.get('success'):
        transfers = pending.get('data', {}).get('data', [])
        print(f"Transferencias pendentes: {len(transfers)}")
        if len(transfers) == 0:
            print("SUCESSO! Nenhuma transferencia pendente - foi aprovada automaticamente!")
        else:
            print("Ainda ha transferencias pendentes:")
            for t in transfers:
                print(f"  - ID: {t.get('id')}, Valor: R$ {t.get('attributes', {}).get('value')}")
    else:
        print(f"Erro: {pending}")

if __name__ == "__main__":
    asyncio.run(check())
