import sqlite3
import random
from datetime import datetime, timezone
from pathlib import Path
from public_osint_market_research import LeadStore

DB_PATH = Path("outreach_queue_test_p1_learn.sqlite3")

def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
        
    store = LeadStore(DB_PATH)
    conn = store.connection
    cursor = conn.cursor()
    
    target_key = "CFO|MANUFACTURING|ZURICH|SWITZERLAND"
    
    # Strategy 1: DDG + COMPANY_DISCOVERY + "{industry} companies {location}"
    # Samples: 5, Yield: 10 leads, Avg Relevance: 85 -> Should be very high score
    for i in range(5):
        run_id = f"mock_run_s1_{i}"
        cursor.execute(
            """
            INSERT INTO query_runs
            (run_id, target_key, query_template, query, family, round, provider, raw_results, unique_domains, new_domains, emails_found, duration_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, target_key, "{industry} companies {location}", "Manufacturing companies Zurich", "COMPANY_DISCOVERY", 1, "DuckDuckGoProvider", 10, 5, 2, 2, 1000, utc_now())
        )
        for j in range(2):
            cursor.execute("INSERT INTO prospects (business_email, relevance_score) VALUES (?, ?)", (f"cfo_s1_{i}_{j}@example.com", 85))
            prospect_id = cursor.lastrowid
            cursor.execute("INSERT INTO prospect_sources (prospect_id, engine, query, query_run_id) VALUES (?, ?, ?, ?)", (prospect_id, "DuckDuckGoProvider", "Manufacturing companies Zurich", run_id))
            
    # Strategy 2: SearXNG + PERSON_DISCOVERY + '"{role}" {industry} {location}'
    # Samples: 4, Yield: 5 leads, Avg Relevance: 75
    for i in range(4):
        run_id = f"mock_run_s2_{i}"
        cursor.execute(
            """
            INSERT INTO query_runs
            (run_id, target_key, query_template, query, family, round, provider, raw_results, unique_domains, new_domains, emails_found, duration_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, target_key, '"{role}" {industry} {location}', '"CFO" Manufacturing Zurich', "PERSON_DISCOVERY", 2, "SearXNGProvider", 10, 5, 1, 1, 1000, utc_now())
        )
        if i < 3: # 3 leads out of 4 runs
            cursor.execute("INSERT INTO prospects (business_email, relevance_score) VALUES (?, ?)", (f"cfo_s2_{i}@example.com", 75))
            prospect_id = cursor.lastrowid
            cursor.execute("INSERT INTO prospect_sources (prospect_id, engine, query, query_run_id) VALUES (?, ?, ?, ?)", (prospect_id, "SearXNGProvider", '"CFO" Manufacturing Zurich', run_id))

    # Strategy 3: DDG + TARGET_PAGE_DISCOVERY + "inurl:team {industry} {location}"
    # Samples: 1, Yield: 1 lead, Avg Relevance: 100 -> Should NOT dominate because samples < 3
    run_id = "mock_run_s3_0"
    cursor.execute(
        """
        INSERT INTO query_runs
        (run_id, target_key, query_template, query, family, round, provider, raw_results, unique_domains, new_domains, emails_found, duration_ms, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, target_key, "inurl:team {industry} {location}", "inurl:team Manufacturing Zurich", "TARGET_PAGE_DISCOVERY", 3, "DuckDuckGoProvider", 10, 5, 1, 1, 1000, utc_now())
    )
    cursor.execute("INSERT INTO prospects (business_email, relevance_score) VALUES (?, ?)", ("perfect_cfo@example.com", 100))
    prospect_id = cursor.lastrowid
    cursor.execute("INSERT INTO prospect_sources (prospect_id, engine, query, query_run_id) VALUES (?, ?, ?, ?)", (prospect_id, "DuckDuckGoProvider", "inurl:team Manufacturing Zurich", run_id))

    conn.commit()
    print("Mock history created successfully.")
    
if __name__ == "__main__":
    main()
