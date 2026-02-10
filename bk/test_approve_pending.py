"""
Script para testar aprovação de transferências pendentes
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.grafeno import GrafenoService
from decimal import Decimal

async def test_pending_transfers():
    grafeno = GrafenoService()
    
    print("=" * 80)
    print("TESTE: Listar e Aprovar Transferências Pendentes")
    print("=" * 80)
    
    # 1. Listar transferências pendentes
    print("\n1. Listando transferências pendentes...")
    pending = await grafeno.list_pending_transfers()
    
    print(f"\nStatus: {pending.get('success')}")
    
    if not pending.get('success'):
        print(f"❌ Erro ao listar: {pending}")
        return
    
    data = pending.get('data', {})
    transfers = data.get('data', [])
    
    print(f"\nTotal de transferências pendentes: {len(transfers)}")
    
    if not transfers:
        print("\n✅ Nenhuma transferência pendente!")
        return
    
    # 2. Mostrar detalhes de cada transferência
    print("\n" + "=" * 80)
    print("TRANSFERÊNCIAS PENDENTES:")
    print("=" * 80)
    
    for i, transfer in enumerate(transfers, 1):
        transfer_id = transfer.get('id')
        attrs = transfer.get('attributes', {})
        value = attrs.get('value', 0)
        status = attrs.get('status', 'unknown')
        api_uuid = attrs.get('apiPartnerTransactionUuid')
        beneficiary = attrs.get('beneficiary', {})
        
        print(f"\n{i}. Transferência ID: {transfer_id}")
        print(f"   UUID: {api_uuid}")
        print(f"   Valor: R$ {value}")
        print(f"   Status: {status}")
        print(f"   Beneficiário: {beneficiary.get('name', 'N/A')}")
        
        # 3. Tentar aprovar
        if api_uuid:
            print(f"\n   Tentando aprovar...")
            result = await grafeno.approve_transfer(api_uuid)
            
            if result.get('success'):
                print(f"   ✅ APROVADA com sucesso!")
            else:
                print(f"   ❌ Erro ao aprovar:")
                print(f"   Status Code: {result.get('status_code')}")
                print(f"   Resposta: {result.get('data')}")
        else:
            print(f"   ⚠️ UUID não encontrado, não é possível aprovar")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(test_pending_transfers())
