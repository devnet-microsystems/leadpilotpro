import sqlite3
import sys

DB_PATH = 'outreach_queue.sqlite3'
BACKUP_PATH = 'outreach_queue.BACKUP-2026-09-17.sqlite3'

def get_count(cursor, table):
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    return cursor.fetchone()[0]

def print_counts(cursor, label):
    print(f"--- {label} ---")
    tables = [
        'campaigns', 'templates', 'email_archive', 'prospects', 
        'research_campaigns', 'campaign_queries', 'send_events',
        'sales_offers', 'ideal_customer_profiles', 'query_templates', 'query_runs', 'prospect_sources', 'sessions'
    ]
    for t in tables:
        try:
            print(f"{t}: {get_count(cursor, t)}")
        except sqlite3.OperationalError:
            pass
            
def main():
    conn = sqlite3.connect(DB_PATH)
    backup_conn = sqlite3.connect(BACKUP_PATH)
    
    cur = conn.cursor()
    b_cur = backup_conn.cursor()
    
    print_counts(cur, "Current Before")
    
    # 1. Remove EMAIL_ARCHIVE id=327
    cur.execute("DELETE FROM email_archive WHERE id=327")
    
    # 2. Restore PROSPECTS id=163 from backup
    b_cur.execute("SELECT * FROM prospects WHERE id=163")
    p163 = b_cur.fetchone()
    if p163:
        columns = [desc[0] for desc in b_cur.description]
        placeholders = ','.join(['?'] * len(columns))
        cur.execute(f"INSERT OR REPLACE INTO prospects ({','.join(columns)}) VALUES ({placeholders})", p163)
        
    # 3. Restore SEND_EVENTS id=330 from backup
    b_cur.execute("SELECT * FROM send_events WHERE id=330")
    se330 = b_cur.fetchone()
    if se330:
        columns = [desc[0] for desc in b_cur.description]
        placeholders = ','.join(['?'] * len(columns))
        cur.execute(f"INSERT OR REPLACE INTO send_events ({','.join(columns)}) VALUES ({placeholders})", se330)
        
    # 4. Remove SALES_OFFERS id=35
    cur.execute("DELETE FROM sales_offers WHERE id=35")
    
    # 5. Remove IDEAL_CUSTOMER_PROFILES id=32
    cur.execute("DELETE FROM ideal_customer_profiles WHERE id=32")
    
    # 6. Remove RESEARCH_CAMPAIGNS id=32
    cur.execute("DELETE FROM research_campaigns WHERE id=32")
    
    # 7. Remove CAMPAIGN_QUERIES associated to campaign_id=32
    cur.execute("DELETE FROM campaign_queries WHERE research_campaign_id=32")
    
    # 8. Remove QUERY_TEMPLATES associated to campaign 32
    try:
        cur.execute("DELETE FROM query_templates WHERE research_campaign_id=32")
    except sqlite3.OperationalError:
        try:
            cur.execute("DELETE FROM query_templates WHERE campaign_id=32")
        except sqlite3.OperationalError:
            pass
            
    # 9. Remove QUERY_RUNS added by test. 
    cur.execute("SELECT id FROM query_runs")
    c_qr = set(row[0] for row in cur.fetchall())
    b_cur.execute("SELECT id FROM query_runs")
    b_qr = set(row[0] for row in b_cur.fetchall())
    test_qr = c_qr - b_qr
    for qr_id in test_qr:
        cur.execute("DELETE FROM query_runs WHERE id=?", (qr_id,))
        
    # 10. Remove PROSPECT_SOURCES added by test.
    cur.execute("SELECT id FROM prospect_sources")
    c_ps = set(row[0] for row in cur.fetchall())
    b_cur.execute("SELECT id FROM prospect_sources")
    b_ps = set(row[0] for row in b_cur.fetchall())
    test_ps = c_ps - b_ps
    for ps_id in test_ps:
        cur.execute("DELETE FROM prospect_sources WHERE id=?", (ps_id,))
        
    # 11. Remove SESSIONS created by tests.
    try:
        cur.execute("SELECT id FROM sessions")
        c_sess = set(row[0] for row in cur.fetchall())
        try:
            b_cur.execute("SELECT id FROM sessions")
            b_sess = set(row[0] for row in b_cur.fetchall())
        except sqlite3.OperationalError:
            b_sess = set()
        test_sess = c_sess - b_sess
        for sess_id in test_sess:
            cur.execute("DELETE FROM sessions WHERE id=?", (sess_id,))
    except sqlite3.OperationalError:
        pass
        
    # P3 Migrations: email_quality, qualification_status, rejection_reason
    columns = [col[1] for col in cur.execute("PRAGMA table_info(prospects)").fetchall()]
    if 'email_quality' not in columns:
        print("Aggiunta colonna email_quality a prospects...")
        cur.execute("ALTER TABLE prospects ADD COLUMN email_quality TEXT DEFAULT 'UNKNOWN'")
    if 'qualification_status' not in columns:
        print("Aggiunta colonna qualification_status a prospects...")
        cur.execute("ALTER TABLE prospects ADD COLUMN qualification_status TEXT DEFAULT 'REVIEW_REQUIRED'")
    if 'rejection_reason' not in columns:
        print("Aggiunta colonna rejection_reason a prospects...")
        cur.execute("ALTER TABLE prospects ADD COLUMN rejection_reason TEXT")
    
    conn.commit()
    print("Database migration completed successfully!")
        
    print_counts(cur, "Current After")
    
    # Verify
    print("--- Verifications ---")
    cur.execute("SELECT id FROM prospects WHERE id=163")
    print(f"prospects.id=163: {'Exists' if cur.fetchone() else 'Missing'}")
    
    cur.execute("SELECT id FROM send_events WHERE id=330")
    print(f"send_events.id=330: {'Exists' if cur.fetchone() else 'Missing'}")
    
    cur.execute("SELECT id FROM email_archive WHERE id=327")
    print(f"archive.id=327: {'Exists' if cur.fetchone() else 'Missing'}")
    
    cur.execute("SELECT id FROM research_campaigns WHERE id=32")
    print(f"research_campaign.id=32: {'Exists' if cur.fetchone() else 'Missing'}")
    
    cur.execute("SELECT id FROM sales_offers WHERE id=35")
    print(f"offer.id=35: {'Exists' if cur.fetchone() else 'Missing'}")
    
    cur.execute("SELECT id FROM ideal_customer_profiles WHERE id=32")
    print(f"ICP.id=32: {'Exists' if cur.fetchone() else 'Missing'}")
    
    cur.execute("SELECT id, name FROM campaigns ORDER BY id LIMIT 14")
    c_camp = cur.fetchall()
    b_cur.execute("SELECT id, name FROM campaigns ORDER BY id LIMIT 14")
    b_camp = b_cur.fetchall()
    print(f"14 storiche campagne identiche: {c_camp == b_camp and len(c_camp) == 14}")
    
    cur.execute("SELECT id, name FROM templates ORDER BY id LIMIT 16")
    c_temp = cur.fetchall()
    b_cur.execute("SELECT id, name FROM templates ORDER BY id LIMIT 16")
    b_temp = b_cur.fetchall()
    print(f"16 storici templates identici: {c_temp == b_temp and len(c_temp) == 16}")
    
    conn.close()
    backup_conn.close()

if __name__ == '__main__':
    main()
