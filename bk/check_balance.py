"""
Verificar saldo e tentar criar uma transferencia
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.grafeno import GrafenoService
from decimal import Decimal

async def check_balance_and_transfer():
    grafeno = GrafenoService()
    
    print("=" * 80)
    print("1. Verificando saldo da conta...")
    print("=" * 80)
    
    balance = await grafeno.get_balance()
    
    if balance.get('success'):
        data = balance.get('data', {})
        print(f"\nSaldo disponivel: R$ {data.get('available_balance', 'N/A')}")
        print(f"Saldo total: R$ {data.get('balance', 'N/A')}")
    else:
        print(f"\nErro ao consultar saldo: {balance}")
    
    print("\n" + "=" * 80)
    print("2. Tentando criar transferencia de R$ 12,00...")
    print("=" * 80)
    
    # Usar a chave PIX do beneficiario que aparece nas transferencias anteriores
    result = await grafeno.create_pix_transfer(
        value=Decimal("12.00"),
        pix_key="235bf37c-ef60-4f43-923b-8466bee09fd4",  # Chave EVP da V2X
        pix_key_type="evp",
        beneficiary_name="V2X CARTOES E MEIOS DE PAGAMENTOS LTDA",
        beneficiary_document="00000000000000",  # CNPJ placeholder
        description="Teste transferencia"
    )
    
    print(f"\nResultado:")
    print(f"Success: {result.get('success')}")
    print(f"Status Code: {result.get('status_code')}")
    
    if result.get('success'):
        print(f"\nTransferencia criada!")
        print(f"UUID: {result.get('transaction_uuid')}")
    else:
        print(f"\nErro ao criar:")
        print(f"Data: {result.get('data')}")
        print(f"Error: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(check_balance_and_transfer())
