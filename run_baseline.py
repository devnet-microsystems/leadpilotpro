import subprocess
import time

TARGETS = [
    ("CTO", "SaaS", "Zurich", "Switzerland"),
    ("CFO", "Manufacturing", "Milan", "Italy"),
    ("CEO", "Logistics", "Munich", "Germany"),
    ("COO", "Construction", "Tuscany", "Italy"),
    ("HR Director", "Software", "London", "UK"),
    ("Sales Director", "SaaS", "Milan", "Italy"),
    ("Procurement Manager", "Manufacturing", "Turin", "Italy"),
    ("IT Director", "Hospitality", "Rome", "Italy"),
    ("Marketing Director", "E-commerce", "Paris", "France"),
    ("Operations Director", "Logistics", "Rotterdam", "Netherlands")
]

DB_NAME = "outreach_queue_baseline.sqlite3"
MAX_QUERIES = 12 # Limit to 12 to avoid instant IP bans during this batch run, but still enough to test the engine

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
    
    # We pipe stdout and stderr to the terminal so we can see the progress
    subprocess.run(cmd)

if __name__ == "__main__":
    for target in TARGETS:
        run_target(*target)
        # Sleep a bit between runs to prevent rate limiting from search providers
        print("\nSleeping for 30 seconds to respect rate limits...\n")
        time.sleep(30)
