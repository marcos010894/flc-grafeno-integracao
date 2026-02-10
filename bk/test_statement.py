"""
Teste do endpoint de extrato
"""

import asyncio
import httpx

async def test_statement():
    url = "http://localhost:8000/grafeno-client/statement"
    
    # Você precisa de um token válido aqui
    # Pegue do localStorage do navegador ou faça login primeiro
    token = "SEU_TOKEN_AQUI"  # Substitua pelo token real
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    print("Testando endpoint de extrato...")
    print(f"URL: {url}\n")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, timeout=30.0)
        
        print(f"Status Code: {response.status_code}")
        print(f"\nResposta:")
        
        try:
            data = response.json()
            print(f"Success: {data.get('success')}")
            print(f"Status Code: {data.get('status_code')}")
            
            if data.get('success'):
                entries = data.get('data', {}).get('data', [])
                print(f"\nTotal de entradas: {len(entries)}")
                
                if len(entries) > 0:
                    print(f"\nPrimeiras 3 entradas:")
                    for i, entry in enumerate(entries[:3], 1):
                        attrs = entry.get('attributes', {})
                        print(f"\n{i}. Data: {attrs.get('entryAt')}")
                        print(f"   Descrição: {attrs.get('description')}")
                        print(f"   Valor: R$ {attrs.get('amount')}")
                else:
                    print("\nNenhuma entrada encontrada")
            else:
                print(f"\nErro: {data.get('error')}")
                print(f"Message: {data.get('message')}")
        except Exception as e:
            print(f"Erro ao processar resposta: {e}")
            print(f"Resposta raw: {response.text[:500]}")

if __name__ == "__main__":
    print("IMPORTANTE: Edite o script e adicione um token válido antes de executar!")
    print("Você pode pegar o token do localStorage do navegador.\n")
    # asyncio.run(test_statement())
