import sqlite3
import db_connector

def migrate():
    conn = db_connector.get_connection('outreach_queue.sqlite3')
    cur = conn.cursor()
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
    conn.close()

if __name__ == '__main__':
    migrate()
