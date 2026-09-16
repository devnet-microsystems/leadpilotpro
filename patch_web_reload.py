import re

with open("web_server.py", "r") as f:
    content = f.read()

old_sync = """@app.post("/api/imap/sync")
def api_imap_sync(user: dict = Depends(get_current_user)):
    import sys
    sys.path.append(str(ROOT))
    import imap_poller
    db = OutreachDatabase(DB_PATH)
    res = imap_poller.sync_imap_inbox(db)"""

new_sync = """@app.post("/api/imap/sync")
def api_imap_sync(user: dict = Depends(get_current_user)):
    import sys
    import importlib
    sys.path.append(str(ROOT))
    import imap_poller
    importlib.reload(imap_poller)
    db = OutreachDatabase(DB_PATH)
    res = imap_poller.sync_imap_inbox(db)"""

content = content.replace(old_sync, new_sync)

with open("web_server.py", "w") as f:
    f.write(content)
print("Done patching web_server.py for reload")
