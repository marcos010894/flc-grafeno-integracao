"""
Script de teste para simular webhook de confirmação de transferência
"""

import asyncio
import httpx
import json

async def test_transfer_webhook():
    """Simula webhook de confirmação de transferência"""
    
    url = "http://localhost:8000/grafeno/webhook"
    
    # Payload simulando webhook da Grafeno para confirmação de transferência
    payload = {
        "kind": "confirmation",
        "data": {
            "api_partner_transaction_uuid": "test-uuid-12345",
            "value": 12.00,  # R$ 12,00 - dentro do limite de auto-aprovação
            "status": "pending",
            "beneficiary": {
                "name": "V2X CARTÕES E MEIOS DE PAGAMENTOS LTDA",
                "documentNumber": "12345678000100"
            }
        },
        "signature": "test-signature",
        "digest": "test-digest"
    }
    
    print("=" * 80)
    print("TESTE: Webhook de Confirmação de Transferência")
    print("=" * 80)
    print(f"\nURL: {url}")
    print(f"Payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=30.0)
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"\nResposta:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "auto_approved":
                print("\n✅ SUCESSO! Transferência aprovada automaticamente!")
            elif result.get("status") == "pending_manual_approval":
                print("\n⚠️ Transferência aguardando aprovação manual (valor acima do limite)")
            else:
                print(f"\n❌ Status inesperado: {result.get('status')}")
        else:
            print(f"\n❌ Erro: Status code {response.status_code}")

if __name__ == "__main__":
    asyncio.run(test_transfer_webhook())
