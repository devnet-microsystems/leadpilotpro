import urllib.request
import json
from strict_e2e_test import SESSION_TOKEN

req = urllib.request.Request("http://127.0.0.1:8001/api/send", method="POST")
req.add_header("Cookie", f"session_token={SESSION_TOKEN}")
req.add_header('Content-Type', 'application/json')
req.data = json.dumps({"campaign": "sovereign selling", "limit": 1}).encode('utf-8')
res = urllib.request.urlopen(req)
print(res.read())
