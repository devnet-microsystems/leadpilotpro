import subprocess
import time
import os

if os.path.exists(".env"):
    with open(".env") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                key, val = line.strip().split("=", 1)
                os.environ[key] = val

TARGETS = [
    ("CTO", "SaaS", "Zurich", "Switzerland"),
    ("CFO", "Manufacturing", "Milan", "Italy"),
    ("CEO", "Logistics", "Munich", "Germany"),
]

DB_NAME = "outreach_queue_baseline_v3.sqlite3"
MAX_QUERIES = 15  # Increased since we now have 3 providers (Brave, DDG, SearXNG)

def run_target(role, industry, location, country):
    print(f"\n{'='*50}\nStarting Target: {role} | {industry} | {location} | {country}\n{'='*50}")
    
    # We explicitly enable Brave, and disable DDG/SearXNG for this baseline test
    env = os.environ.copy()
    env["BRAVE_ENABLED"] = "true"
    env["SEARXNG_ENABLED"] = "false"
    env["DDG_ENABLED"] = "false"
    
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
    
    subprocess.run(cmd, env=env)

if __name__ == "__main__":
    if not os.getenv("BRAVE_API_KEY"):
        print("ERROR: BRAVE_API_KEY environment variable is missing!")
        print("Please export it (e.g. export BRAVE_API_KEY='...') and run this script again.")
        exit(1)
        
    for target in TARGETS:
        run_target(*target)
        print("\nSleeping for 15 seconds to respect rate limits...\n")
        time.sleep(15)
