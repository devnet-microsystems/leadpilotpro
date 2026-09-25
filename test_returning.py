import sqlite3
import db_connector
conn = db_connector.get_connection(':memory:')
conn.execute("CREATE TABLE foo (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)")
cur = conn.execute("INSERT INTO foo (name) VALUES ('bar') RETURNING id")
print("lastrowid:", cur.lastrowid)
row = cur.fetchone()
print("fetch:", row[0] if row else None)

cur2 = conn.execute("INSERT INTO foo (name) VALUES ('baz')")
print("lastrowid2:", cur2.lastrowid)
