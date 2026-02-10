"""
Teste direto com a API Grafeno para verificar se retorna dados reais ou mockados
"""

import asyncio
import httpx
import json
from datetime import date, timedelta

async def test_grafeno_direct():
    """Testa diretamente a API Grafeno"""
    
    # Token atual
    token = "38387c01-b705-4425-9006-59a8c134d8b0.9V9v4B_L0XVcx-tmrEEUMNAKvSk"
    url = "https://pagamentos.grafeno.be/api/v2/charges"
    
    # Payload mínimo
    payload = {
        "paymentMethod": "pix",
        "dueDate": (date.today() + timedelta(days=1)).isoformat(),
        "value": 10.00,
        "clientControlNumber": "test-123",
        "expiresAfter": 1,
        "pix": {
            "key": "43aa6af5-c6e1-42f1-9cf9-d5606d1b8a75",
            "keyType": "random"
        },
        "payer": {
            "name": "Teste",
            "email": "teste@example.com",
            "documentNumber": "11144477735",
            "address": {
                "zipCode": "01001000",
                "street": "Praça da Sé",
                "number": "1",
                "complement": "Lado ímpar",
                "neighborhood": "Sé",
                "city": "São Paulo",
                "state": "SP",
                "country": "BR"
            },
            "phone": {
                "countryCode": "55",
                "areaCode": "11",
                "number": "999999999"
            }
        },
        "grantor": {
            "name": "FLC BANK LTDA",
            "documentNumber": "88650081000116",
            "address": {
                "street": "Avenida Paulista",
                "number": "1000",
                "complement": "Conjunto 100",
                "zipCode": "01310-100",
                "neighborhood": "Bela Vista",
                "city": "São Paulo",
                "state": "SP",
                "country": "BR"
            }
        }
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    print("=" * 80)
    print("TESTE DIRETO: API Grafeno")
    print("=" * 80)
    print(f"\nURL: {url}")
    print(f"Token: {token[:20]}...")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers, timeout=30.0)
        
        print(f"\nStatus Code: {response.status_code}")
        
        try:
            data = response.json()
            print("\nResposta JSON:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # Verificar se tem dados mockados
            if "data" in data:
                pix_data = data.get("data", {}).get("attributes", {}).get("pixData", {})
                pix_attrs = pix_data.get("data", {}).get("attributes", {})
                emv = pix_attrs.get("emv", "")
                encoded_image = pix_attrs.get("encodedImage", "")
                
                print("\n" + "=" * 80)
                print("ANÁLISE:")
                print("=" * 80)
                
                if emv == "some long emv" or "some long" in emv:
                    print("\n❌ PROBLEMA IDENTIFICADO!")
                    print("   A API Grafeno está retornando dados MOCKADOS.")
                    print("\n   Possíveis causas:")
                    print("   1. Token é de documentação/exemplo")
                    print("   2. Conta está em modo sandbox/teste")
                    print("   3. Conta precisa ser ativada para produção")
                    print("   4. Falta configuração na conta Grafeno")
                    print("\n   SOLUÇÃO:")
                    print("   - Entre em contato com o suporte da Grafeno")
                    print("   - Verifique se a conta está ativa para produção")
                    print("   - Solicite um token de produção válido")
                else:
                    print("\n✅ API retornou dados REAIS!")
                    print(f"   EMV: {emv[:50]}...")
                    print(f"   Imagem: {len(encoded_image)} caracteres")
        except Exception as e:
            print(f"\nErro ao processar resposta: {e}")
            print(f"Resposta raw: {response.text}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(test_grafeno_direct())
