import os
import sqlite3
import db_connector

def migrate_to_postgres(sqlite_path="outreach_queue.sqlite3"):
    if not os.path.exists(sqlite_path):
        print(f"SQLite file {sqlite_path} not found.")
        return

    pg_url = os.environ.get("LEADPILOT_DB_URL")
    if not pg_url or not pg_url.startswith("postgres"):
        print("Set LEADPILOT_DB_URL to a postgres:// URL to migrate.")
        return

    # 1. Initialize PostgreSQL schema
    print("Initializing PostgreSQL schema...")
    import schema_bootstrap
    schema_bootstrap.ensure_all_schema("postgres_dummy") # The actual path is ignored because LEADPILOT_DB_URL is set

    # 2. Connect to both
    print("Connecting to databases...")
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = db_connector.get_connection()

    # 3. Get all user tables
    tables = [row["name"] for row in sqlite_conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]

    for table in tables:
        print(f"Migrating table {table}...")
        rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"  Table {table} is empty, skipping data.")
            continue
            
        columns = rows[0].keys()
        col_names = ", ".join(columns)
        placeholders = ", ".join(["?"] * len(columns))
        
        # Clean up existing data in PG just in case
        pg_conn.execute(f"DELETE FROM {table}")
        
        insert_sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"
        
        # Insert rows
        # Executemany uses the translated ? to %s in PGWrapper
        values = [tuple(row) for row in rows]
        pg_conn.executemany(insert_sql, values)
        
        # Update sequence for the table if it has an id column
        if "id" in columns:
            try:
                # In postgres, we need to reset the sequence so next inserts don't collide
                seq_name = f"{table}_id_seq"
                max_id_row = pg_conn.execute(f"SELECT MAX(id) FROM {table}").fetchone()
                max_id = max_id_row["max"] if max_id_row and "max" in max_id_row else (max_id_row[0] if max_id_row else 1)
                if max_id:
                    pg_conn.execute(f"SELECT setval('{seq_name}', {max_id})")
            except Exception as e:
                # Sometimes sequence name is different or doesn't exist
                pass

        print(f"  Inserted {len(rows)} rows into {table}.")

    sqlite_conn.close()
    pg_conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate_to_postgres()
