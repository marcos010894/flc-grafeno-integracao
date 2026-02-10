"""
Script de teste para verificar a criação de cobrança PIX via Grafeno
Testa se o payload está correto e se a API retorna o QR Code
"""

import asyncio
import sys
import os

# Adicionar o diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decimal import Decimal
from app.services.grafeno import GrafenoService


async def test_pix_charge():
    """Testa a criação de uma cobrança PIX"""
    
    print("=" * 60)
    print("TESTE: Criação de Cobrança PIX via Grafeno")
    print("=" * 60)
    
    # Inicializar serviço
    grafeno = GrafenoService()
    
    # Dados de teste
    test_data = {
        "value": Decimal("10.00"),
        "payer_name": "João da Silva",
        "payer_document": "11144477735",  # CPF válido com dígitos verificadores corretos
        "payer_email": "joao@example.com",
    }
    
    print(f"\nDados da cobranca:")
    print(f"   Valor: R$ {test_data['value']}")
    print(f"   Pagador: {test_data['payer_name']}")
    print(f"   Documento: {test_data['payer_document']}")
    print(f"   Email: {test_data['payer_email']}")
    
    print(f"\nEnviando requisicao para Grafeno...")
    
    # Criar cobrança
    result = await grafeno.create_pix_charge(**test_data)
    
    print(f"\nResultado:")
    print(f"   Sucesso: {result.get('success')}")
    
    if result.get('success'):
        print(f"   [OK] Cobranca criada com sucesso!")
        print(f"\n   Charge ID: {result.get('charge_id')}")
        print(f"   Status: {result.get('status')}")
        print(f"   Vencimento: {result.get('due_date')}")
        print(f"   Valor: R$ {result.get('value')}")
        
        # Verificar se tem QR Code
        if result.get('pix_copy_paste'):
            print(f"\n   [OK] PIX Copia e Cola gerado:")
            print(f"   {result.get('pix_copy_paste')[:50]}...")
        else:
            print(f"\n   [AVISO] PIX Copia e Cola nao encontrado na resposta")
        
        # Verificar se tem imagem do QR Code
        if result.get('pix_qrcode'):
            print(f"\n   [OK] QR Code (imagem base64) gerado")
            print(f"   Tamanho: {len(result.get('pix_qrcode'))} caracteres")
        else:
            print(f"\n   [AVISO] QR Code (imagem) nao encontrado na resposta")
        
        print(f"\n   Controle: {result.get('client_control_number')}")
        
    else:
        print(f"   [ERRO] Erro ao criar cobranca")
        print(f"\n   Status Code: {result.get('status_code')}")
        print(f"   Erro: {result.get('error')}")
        print(f"\n   Resposta completa:")
        import json
        print(json.dumps(result.get('raw_response', {}), indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 60)
    return result


if __name__ == "__main__":
    result = asyncio.run(test_pix_charge())
    
    # Exit code baseado no sucesso
    sys.exit(0 if result.get('success') else 1)
