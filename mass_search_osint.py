import subprocess
import time
import sys
from pathlib import Path

# Configura i tuoi target per lo scraping OSINT su DuckDuckGo
roles = ["CTO", "Founder", "Managing Director", "VP Engineering", "CEO"]
industries = ["SaaS", "Cybersecurity", "Fintech", "Web3", "Marketing"]
states = [
    "Zurich", "Geneva", "Zug", 
    "Dubai", "Abu Dhabi", 
    "Sydney", "Melbourne", 
    "Stockholm", "Oslo", "Amsterdam"
]

queries = []
for role in roles:
    for ind in industries:
        for state in states:
            # Creazione di footprint e permutazioni avanzate (Bing supporta questi operatori)
            # Invece di una sola ricerca, ne facciamo diverse mirate
            
            # 1. Ricerca base orientata alle email
            queries.append(f'"{role}" {ind} {state} "email"')
            # 2. Ricerca orientata ai contatti generali
            queries.append(f'"{role}" {ind} {state} "contact" OR "contatti"')
            # 3. Operatore inurl per trovare pagine specifiche
            queries.append(f'{ind} {state} inurl:contact')
            # 4. Operatore intitle per trovare la pagina del team o chi siamo
            queries.append(f'{ind} {state} intitle:about OR intitle:team')
            # 5. Ricerca del simbolo chiocciola per trovare liste/pdf
            queries.append(f'"{role}" {ind} {state} "@"')

# Rimuovi i duplicati se ce ne sono
queries = list(dict.fromkeys(queries))

print(f"[*] Caricate {len(queries)} micro-query avanzate (multi-query OSINT).")
print(f"[*] ATTENZIONE: Questo scraper scarica ed esplora le pagine reali. Ci vorrà molto più tempo di Lusha.")

# Dividiamo in blocchi da 10 per non bloccare il browser troppo a lungo e non superare limiti CLI
def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

for i, batch in enumerate(chunks(queries, 10), 1):
    print(f"\n==============================================")
    print(f"[*] AVVIO BATCH {i} (10 query)")
    print(f"==============================================")
    
    cmd = [
        ".venv/bin/python", 
        "-u", 
        "public_osint_market_research.py", 
        "--results-per-query", "15", 
        "--queries"
    ] + batch
    
    try:
        # Usa subprocess.Popen se vuoi vedere l'output in tempo reale nel terminale
        subprocess.run(cmd)
    except Exception as e:
        print(f"Errore nell'esecuzione del batch: {e}")
        
    print("[*] Batch completato. Pausa di raffreddamento di 60 secondi...")
    time.sleep(60)

print("[*] Loop OSINT completato.")
