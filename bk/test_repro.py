import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_grafeno():
    url = "https://pagamentos.grafeno.be/api/v2/charges"
    
    # Payload EXATO do exemplo do usuário
    payload = {
      "paymentMethod": "pix",
      "payer": {
        "address": {
          "country": "BR"
        },
        "phone": {
          "countryCode": "55"
        }
      },
      "grantor": {
        "address": {
          "country": "BR"
        }
      }
    }
    
    # Precisamos de headers de autorização. 
    # Vou tentar usar os do .env ou hardcoded se o user não forneceu. 
    # Assumindo que o sistema já tem autenticação funcionando. 
    # Vou usar o token do MASTER se disponível, ou simular o login.
    
    # Para simplificar, vou tentar reusar a logica de headers do grafeno_service se possivel, 
    # mas como é script isolado, vou tentar pegar do env.
    
    token = "38387c01-b705-4425-9006-59a8c134d8b0.9V9v4B_L0XVcx-tmrEEUMNAKvSk"
    account_number = "08185935-7"
    
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer {token}",
        "Account-Number": account_number
    }
    
    print(f"Sending request to {url}")
    print(f"Payload: {payload}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            print(f"Status: {response.status_code}")
            print("Response Body:")
            print(response.json())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_grafeno())
