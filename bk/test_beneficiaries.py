import httpx
import asyncio
import os
import json

# Token hardcoded from grafeno_client.py for testing
TOKEN = os.getenv("GRAFENO_API_TOKEN", "38387c01-b705-4425-9006-59a8c134d8b0.9V9v4B_L0XVcx-tmrEEUMNAKvSk")
# ACCOUNT_NUMBER = "08185935-7" 

HEADERS = {
    "Authorization": TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Account-Number": "08185935-7", 
}

# The endpoint for beneficiaries usually is at /beneficiaries
URL = "https://pagamentos.grafeno.be/api/v2/beneficiaries"

async def test_beneficiaries():
    print(f"Testing connection to: {URL}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(URL, headers=HEADERS, timeout=30.0)
            
            print(f"\nStatus Code: {response.status_code}")
            try:
                data = response.json()
                print("Response Keys:", data.keys())
                
                if "data" in data:
                    items = data["data"]
                    print(f"\nFound {len(items)} beneficiaries.")
                    if len(items) > 0:
                        print("\nFirst Item Sample:")
                        print(json.dumps(items[0], indent=2))
                else:
                    print("\nNo 'data' key in response.")
                    print(json.dumps(data, indent=2))

            except Exception as e:
                print(f"Error parsing JSON: {e}")
                print(f"Raw Response: {response.text}")
                
    except Exception as e:
        print(f"\nERROR: Could not connect. {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_beneficiaries())
