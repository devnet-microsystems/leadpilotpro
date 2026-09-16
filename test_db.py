import sqlite3
import sys

def main():
    conn = sqlite3.connect('outreach_queue.sqlite3')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = """
    SELECT prospects.business_email as email, prospects.target_url,
           prospects.email_confidence,
           prospects.confidence_type,
           prospect_sources.engine,
           prospect_sources.source_url,
           prospect_sources.query
    FROM prospects
    JOIN prospect_sources
         ON prospects.id = prospect_sources.prospect_id
    ORDER BY prospect_sources.discovered_at DESC
    LIMIT 10;
    """
    
    print("\nDatabase provenance verification:")
    for row in cursor.execute(query).fetchall():
        domain = row['target_url'].replace('https://', '')
        print(f"Email: {row['email']}, Domain: {domain}, Engine: {row['engine']}, Query: {row['query']}, URL: {row['source_url']}")
        
    print("\nChecking deduplication:")
    query_dedup = """
    SELECT prospects.business_email, COUNT(prospect_sources.id) as source_count
    FROM prospects
    JOIN prospect_sources ON prospects.id = prospect_sources.prospect_id
    GROUP BY prospects.id
    HAVING source_count > 1
    LIMIT 5;
    """
    for row in cursor.execute(query_dedup).fetchall():
        print(f"Lead {row['business_email']} has {row['source_count']} sources tracked.")

if __name__ == '__main__':
    main()
