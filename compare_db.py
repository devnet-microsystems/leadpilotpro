import sqlite3
import db_connector

def compare_db(db1_path, db2_path, tables):
    conn1 = db_connector.get_connection(db1_path)
    conn2 = db_connector.get_connection(db2_path)
    
    conn1.row_factory = sqlite3.Row
    conn2.row_factory = sqlite3.Row
    
    cur1 = conn1.cursor()
    cur2 = conn2.cursor()
    
    print(f"Comparing Current: {db1_path} vs Backup: {db2_path}\n")
    
    for table in tables:
        print(f"--- Table: {table} ---")
        try:
            # Get counts
            cur1.execute(f"SELECT COUNT(*) as c FROM {table}")
            c1 = cur1.fetchone()['c']
            cur2.execute(f"SELECT COUNT(*) as c FROM {table}")
            c2 = cur2.fetchone()['c']
            print(f"Count Current: {c1} | Count Backup: {c2}")
            
            # Compare IDs if id column exists
            cur1.execute(f"PRAGMA table_info({table})")
            columns = [row['name'] for row in cur1.fetchall()]
            
            id_col = 'id'
            if 'id' not in columns:
                if columns:
                    id_col = columns[0]
                else:
                    print("No columns found")
                    continue
            
            cur1.execute(f"SELECT {id_col} FROM {table} ORDER BY {id_col}")
            ids1 = set([row[id_col] for row in cur1.fetchall()])
            
            cur2.execute(f"SELECT {id_col} FROM {table} ORDER BY {id_col}")
            ids2 = set([row[id_col] for row in cur2.fetchall()])
            
            missing_in_current = ids2 - ids1
            extra_in_current = ids1 - ids2
            
            print(f"IDs missing in Current: {len(missing_in_current)}")
            print(f"IDs extra in Current: {len(extra_in_current)}")
            
            if len(missing_in_current) > 0:
                print(f"Sample missing: {list(missing_in_current)[:5]}")
            if len(extra_in_current) > 0:
                print(f"Sample extra: {list(extra_in_current)[:5]}")
                
        except Exception as e:
            print(f"Error checking {table}: {e}")
        
        print("")

if __name__ == '__main__':
    tables = ['campaigns', 'templates', 'email_archive', 'prospects', 'send_events']
    compare_db('outreach_queue.sqlite3', 'outreach_queue.BACKUP-2026-09-18.sqlite3', tables)
