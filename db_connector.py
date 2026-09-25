import os
import sqlite3
import re

def get_connection(db_path=None, **kwargs):
    """
    Ritorna una connessione PostgreSQL se LEADPILOT_DB_URL è configurato (e inizia per postgres),
    altrimenti ritorna una connessione SQLite standard (per test/sviluppo locale).
    """
    db_url = os.environ.get("LEADPILOT_DB_URL", "")
    if db_url.startswith("postgres"):
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(db_url)
        return PGWrapper(conn)
    else:
        path = db_path or os.environ.get("LEADPILOT_DB_PATH") or "outreach_queue.sqlite3"
        # Support default arguments like the original code
        kwargs.setdefault("timeout", 10.0)
        kwargs.setdefault("isolation_level", None)
        conn = sqlite3.connect(path, **kwargs)
        conn.row_factory = sqlite3.Row
        return conn


class PGWrapper:
    """Wrapper that mimics a sqlite3 connection for PostgreSQL."""
    def __init__(self, conn):
        self.conn = conn
        # Autocommit equivalent to isolation_level=None
        self.conn.autocommit = True
        
    @property
    def row_factory(self):
        return None
        
    @row_factory.setter
    def row_factory(self, val):
        pass # psycopg2.extras.DictCursor is used instead

    def cursor(self):
        import psycopg2.extras
        return PGCursor(self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor))

    def execute(self, sql, params=()):
        c = self.cursor()
        c.execute(sql, params)
        return c

    def executemany(self, sql, seq_of_parameters):
        c = self.cursor()
        c.executemany(sql, seq_of_parameters)
        return c

    def executescript(self, sql_script):
        c = self.cursor()
        # split by ; and execute, or just execute entirely since psycopg2 supports multiple statements
        c.cur.execute(sql_script)
        return c

    def commit(self):
        self.conn.commit()
        
    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()


class PGCursor:
    def __init__(self, cur):
        self.cur = cur
        self.lastrowid = None
        
    @property
    def rowcount(self):
        return self.cur.rowcount

    @property
    def description(self):
        return self.cur.description

    def _translate_sql(self, sql):
        # 1. Translate ? to %s OUTSIDE of string literals
        result = []
        in_string = False
        string_char = None
        for char in sql:
            if char in ("'", '"'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                result.append(char)
            elif char == '?' and not in_string:
                result.append('%s')
            else:
                result.append(char)
        sql = "".join(result)
        
        # 2. SQLite specific dialect translations
        # Replace INSERT OR IGNORE INTO with standard ON CONFLICT DO NOTHING
        # (This is a simplified approach. In a perfect world we parse the AST, but a regex works for LeadPilotPro's simple queries)
        sql_upper = sql.upper()
        if "INSERT OR IGNORE INTO" in sql_upper:
            # Reconstruct the query
            sql = re.sub(r'(?i)INSERT\s+OR\s+IGNORE\s+INTO', 'INSERT INTO', sql)
            # Append ON CONFLICT DO NOTHING if it does not have it yet
            if "ON CONFLICT" not in sql.upper():
                sql += " ON CONFLICT DO NOTHING"
                
        # Handle RETURNING id for auto-increment emulation
        is_insert = sql.strip().upper().startswith("INSERT INTO")
        if is_insert and "RETURNING " not in sql.upper():
            # Check table name to avoid returning id on tables that don't have it
            match = re.search(r'(?i)INSERT\s+INTO\s+([a-zA-Z0-9_]+)', sql)
            if match:
                table_name = match.group(1).lower()
                if table_name not in ('suppression_list', 'settings', 'sqlite_master'):
                    sql += " RETURNING id"
                    
        return sql

    def execute(self, sql, params=()):
        original_sql = sql
        sql = self._translate_sql(sql)
        self.cur.execute(sql, params)
        if sql.strip().upper().endswith("RETURNING ID"):
            row = self.cur.fetchone()
            if row:
                self.lastrowid = row[0]
            else:
                self.lastrowid = None
        return self

    def executemany(self, sql, seq_of_parameters):
        sql = self._translate_sql(sql)
        self.cur.executemany(sql, seq_of_parameters)
        return self

    def fetchone(self):
        row = self.cur.fetchone()
        if row:
            return dict(row) # convert to dict so it acts like sqlite3.Row
        return None
        
    def fetchall(self):
        rows = self.cur.fetchall()
        return [dict(r) for r in rows]
        
    def close(self):
        self.cur.close()

    def __iter__(self):
        rows = self.fetchall()
        return iter(rows)
