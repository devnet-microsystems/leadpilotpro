import sys
import time
from pathlib import Path

# Add current dir to path to import web_server
sys.path.append(str(Path(__file__).parent))

from web_server import lusha_prospect, LushaAdvancedSearchRequest

user_mock = {"id": 1, "username": "admin"}

roles = ["CTO", "Founder", "Managing Director", "VP Engineering", "CEO"]
industries = ["Computer Software", "Internet", "Information Technology & Services", "Financial Services", "Venture Capital & Private Equity"]

# High-Ticket Tech Hubs (Svizzera, Liechtenstein, UAE, AUS/NZ, Nord Europa)
states = [
    "Zurich", "Geneva", "Zug", "Vaduz",             # CH & FL (Finanza & Crypto)
    "Dubai", "Abu Dhabi",                           # UAE (Capitali / SaaS)
    "Sydney", "Melbourne", "Auckland",              # AUS & NZ
    "Stockholm", "Oslo", "Copenhagen", "Helsinki",  # Nordics (Tech Hubs)
    "Amsterdam"                                     # NL (Europe Gateway)
]

# 5 ruoli * 5 industrie * 14 stati = 350 micro-queries
queries = []
for role in roles:
    for ind in industries:
        for state in states:
            queries.append({"role": role, "industry": ind, "state": state})

print(f"[*] Caricate {len(queries)} micro-query per i mercati High-Ticket.")

# Limita a 3 query per fare un test veloce
queries = queries[:3]

print(f"[*] Eseguiremo solo {len(queries)} query come richiesto.")
print(f"[*] Tempo stimato di completamento: {len(queries) * 15 / 60:.2f} minuti.")

for q in queries:
    target = f"{q['role']} {q['industry']} {q['state']}"
    print(f"[*] Lancio LeadPilot Pro per: {target}")
    
    req = LushaAdvancedSearchRequest(
        role=q['role'],
        industry=q['industry'],
        state=q['state'],
        limit=5
    )
    
    try:
        res = lusha_prospect(req, user_mock)
        print(f"    -> Risultato: OK")
    except Exception as e:
        print(f"    -> Errore: {e}")
        
    print("    -> Pausa tattica di 15 secondi per API rate limits...")
    time.sleep(15)

print("[*] Loop completato. Il Database è pronto.")