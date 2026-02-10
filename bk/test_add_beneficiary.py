import httpx
import asyncio
import os
import json
import uuid

# Token hardcoded from grafeno_client.py for testing
TOKEN = os.getenv("GRAFENO_API_TOKEN", "38387c01-b705-4425-9006-59a8c134d8b0.9V9v4B_L0XVcx-tmrEEUMNAKvSk")
HEADERS = {
    "Authorization": TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Account-Number": "08185935-7", 
}

URL = "https://pagamentos.grafeno.be/api/v2/beneficiaries"

async def test_add_beneficiary():
    print(f"Testing adding beneficiary to: {URL}")
    
    # Random name to avoid duplication errors during testing
    random_id = str(uuid.uuid4())[:8]
    payload = {
        "name": f"TESTE AGENTE {random_id}",
        "documentNumber": "33400689000109", # Use a valid formatted CNPJ for testing (Google Brasil)
        "pixDetails": {
            "key": f"test+{random_id}@example.com",
            "keyType": "email"
        },
        "bankCode": "274",
        "agency": "0001",
        "account": "000000000"
    }
    
    print("\nPayload sending:")
    print(json.dumps(payload, indent=2))
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(URL, json=payload, headers=HEADERS, timeout=30.0)
            
            print(f"\nStatus Code: {response.status_code}")
            try:
                data = response.json()
                print("Response Body:")
                print(json.dumps(data, indent=2))
                
            except Exception as e:
                print(f"Raw Response: {response.text}")
                
    except Exception as e:
        print(f"\nERROR: Could not connect. {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_add_beneficiary())
