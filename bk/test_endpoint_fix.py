"""
Script rápido para testar a correção do endpoint grafeno_client
"""

import asyncio
import httpx

async def test_endpoint():
    """Testa o endpoint do grafeno_client"""
    
    url = "http://localhost:8000/grafeno-client/pix/charge"
    
    params = {
        "value": 25.50,
        "payer_name": "Maria Silva",
        "payer_document": "11144477735",
        "payer_email": "maria@example.com"
    }
    
    # Você precisará do token de autenticação
    # headers = {"Authorization": "Bearer SEU_TOKEN_AQUI"}
    
    print("Testando endpoint /grafeno-client/pix/charge")
    print(f"Params: {params}")
    print("\nNOTA: Este teste requer autenticação. Execute via frontend ou com token válido.")
    
if __name__ == "__main__":
    asyncio.run(test_endpoint())
