import httpx
import asyncio
import os

# Token hardcoded from grafeno_client.py for testing
TOKEN = os.getenv("GRAFENO_API_TOKEN", "38387c01-b705-4425-9006-59a8c134d8b0.9V9v4B_L0XVcx-tmrEEUMNAKvSk")
ACCOUNT_NUMBER = "08185935-7"

HEADERS = {
    "Authorization": TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Account-Number": ACCOUNT_NUMBER,
}

URL = "https://pagamentos.grafeno.be/api/v2/balance/"

async def test_balance():
    print(f"Testing connection to: {URL}")
    print(f"Using Token: {TOKEN[:5]}...{TOKEN[-5:]}")
    print(f"Account: {ACCOUNT_NUMBER}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(URL, headers=HEADERS, timeout=30.0)
            
            print(f"\nStatus Code: {response.status_code}")
            try:
                data = response.json()
                print("Response Data:", data)
                
                if response.status_code == 200:
                    print("\nSUCCESS! Connection established.")
                else:
                    print("\nFAILED. Check credentials.")
            except Exception as e:
                print(f"Raw Response: {response.text}")
                
    except Exception as e:
        print(f"\nERROR: Could not connect. {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_balance())
