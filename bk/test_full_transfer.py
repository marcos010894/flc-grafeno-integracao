"""
Teste completo: Criar transferencia e verificar status
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.grafeno import GrafenoService
from decimal import Decimal

async def test_full_flow():
    grafeno = GrafenoService()
    
    print("=" * 80)
    print("TESTE COMPLETO: Criar Transferencia PIX")
    print("=" * 80)
    
    # 1. Criar transferência
    print("\n1. Criando transferencia PIX de R$ 12,00...")
    
    result = await grafeno.create_pix_transfer(
        value=Decimal("12.00"),
        pix_key="11144477735",  # CPF de teste
        pix_key_type="cpf",
        beneficiary_name="Teste Beneficiario",
        beneficiary_document="11144477735",
        description="Teste de transferencia"
    )
    
    print(f"\nResultado da criacao:")
    print(f"Success: {result.get('success')}")
    print(f"Status Code: {result.get('status_code')}")
    print(f"Transaction UUID: {result.get('transaction_uuid')}")
    
    if not result.get('success'):
        print(f"\nERRO ao criar transferencia:")
        print(f"Data: {result.get('data')}")
        print(f"Error: {result.get('error')}")
        return
    
    print(f"\nTransferencia criada com sucesso!")
    transaction_uuid = result.get('transaction_uuid')
    
    # 2. Aguardar um pouco
    print(f"\nAguardando 3 segundos...")
    await asyncio.sleep(3)
    
    # 3. Verificar se está pendente
    print(f"\n2. Verificando transferencias pendentes...")
    pending = await grafeno.list_pending_transfers()
    
    if pending.get('success'):
        transfers = pending.get('data', {}).get('data', [])
        print(f"\nTotal pendentes: {len(transfers)}")
        
        if len(transfers) > 0:
            print(f"\nTransferencias pendentes encontradas:")
            for t in transfers:
                t_uuid = t.get('attributes', {}).get('apiPartnerTransactionUuid')
                t_value = t.get('attributes', {}).get('value')
                print(f"  - UUID: {t_uuid}")
                print(f"    Valor: R$ {t_value}")
                
                if t_uuid == transaction_uuid:
                    print(f"    >>> Esta e a transferencia que criamos!")
                    
                    # Tentar aprovar
                    print(f"\n3. Tentando aprovar...")
                    approve_result = await grafeno.approve_transfer(t_uuid)
                    
                    print(f"\nResultado da aprovacao:")
                    print(f"Success: {approve_result.get('success')}")
                    print(f"Status Code: {approve_result.get('status_code')}")
                    print(f"Data: {approve_result.get('data')}")
        else:
            print(f"\nNenhuma transferencia pendente!")
            print(f"A transferencia UUID {transaction_uuid} nao esta na lista de pendentes.")
            print(f"Possibilidades:")
            print(f"  1. Foi aprovada automaticamente pela Grafeno")
            print(f"  2. Foi rejeitada")
            print(f"  3. Ainda nao apareceu na lista")
    else:
        print(f"\nErro ao listar pendentes: {pending}")

if __name__ == "__main__":
    asyncio.run(test_full_flow())
