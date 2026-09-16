import subprocess
import time

TARGETS = [
    ("CTO", "SaaS", "Zurich", "Switzerland"),
    ("CFO", "Manufacturing", "Milan", "Italy"),
    ("CEO", "Logistics", "Munich", "Germany"),
]

DB_NAME = "outreach_queue_baseline_v2.sqlite3"
MAX_QUERIES = 8 

def run_target(role, industry, location, country):
    print(f"\n{'='*50}\nStarting Target: {role} | {industry} | {location} | {country}\n{'='*50}")
    cmd = [
        ".venv/bin/python3",
        "public_osint_market_research.py",
        "--role", role,
        "--industry", industry,
        "--location", location,
        "--country", country,
        "--database", DB_NAME,
        "--max-queries", str(MAX_QUERIES)
    ]
    
    subprocess.run(cmd)

if __name__ == "__main__":
    for target in TARGETS:
        run_target(*target)
        print("\nSleeping for 15 seconds to respect rate limits...\n")
        time.sleep(15)
