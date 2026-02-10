"""
Listar TODAS as transferencias (nao so pendentes)
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.grafeno import GrafenoService
import json

async def list_all():
    grafeno = GrafenoService()
    
    print("=" * 80)
    print("Listando TODAS as transferencias")
    print("=" * 80)
    
    # Listar todas
    result = await grafeno.list_transfers(page=1, per_page=10)
    
    print(f"\nSuccess: {result.get('success')}")
    
    if result.get('success'):
        data = result.get('data', {})
        transfers = data.get('data', [])
        
        print(f"\nTotal de transferencias: {len(transfers)}")
        
        if len(transfers) > 0:
            print(f"\nTransferencias encontradas:")
            for i, t in enumerate(transfers, 1):
                attrs = t.get('attributes', {})
                print(f"\n{i}. ID: {t.get('id')}")
                print(f"   UUID: {attrs.get('apiPartnerTransactionUuid')}")
                print(f"   Valor: R$ {attrs.get('value')}")
                print(f"   Status: {attrs.get('status')}")
                print(f"   Metodo: {attrs.get('transferMethod')}")
                print(f"   Criado em: {attrs.get('createdAt')}")
        else:
            print("\nNenhuma transferencia encontrada!")
            
        print(f"\nResposta completa:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"\nErro: {result}")

if __name__ == "__main__":
    asyncio.run(list_all())
