import requests
import json

base_url = "http://127.0.0.1:8000"

try:
    offers_res = requests.get(f"{base_url}/api/sales_offers")
    print(f"GET /api/sales_offers -> Status: {offers_res.status_code}")
    print(f"Offers: {len(offers_res.json())}")
    print(json.dumps(offers_res.json(), indent=2))
except Exception as e:
    print(f"Error fetching offers: {e}")

try:
    icps_res = requests.get(f"{base_url}/api/icps")
    print(f"GET /api/icps -> Status: {icps_res.status_code}")
    print(f"ICPs: {len(icps_res.json())}")
    print(json.dumps(icps_res.json(), indent=2))
except Exception as e:
    print(f"Error fetching ICPs: {e}")
