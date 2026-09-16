import os
from dotenv import load_dotenv
load_dotenv()

from osint_engine.providers import BraveProvider
p = BraveProvider()
print("API Key:", "SET" if p.api_key else "NOT SET")
print("Enabled:", p.enabled)

try:
    res = p.search("SaaS Founders UK", limit=5)
    print("State:", res.state)
    print("Error:", res.error)
    print("Results:", len(res.results))
    for r in res.results:
        print(r.url, r.title)
except Exception as e:
    print("EXCEPTION:", str(e))
