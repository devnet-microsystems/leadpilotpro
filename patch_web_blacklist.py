import re

with open("web_server.py", "r") as f:
    content = f.read()

# 1. Update get_unique_contacts
old_get = """@app.get("/api/contacts")
def get_unique_contacts(user: dict = Depends(get_current_user)):
    if not DB_PATH.exists():
        return []
    db = OutreachDatabase(DB_PATH)
    rows = db.connection.execute('''
        SELECT DISTINCT business_email, company_name 
        FROM prospects 
        WHERE business_email IS NOT NULL AND business_email != ''
        ORDER BY company_name, business_email
    ''').fetchall()
    return [dict(r) for r in rows]"""

new_get = """@app.get("/api/contacts")
def get_unique_contacts(user: dict = Depends(get_current_user)):
    if not DB_PATH.exists():
        return []
    db = OutreachDatabase(DB_PATH)
    rows = db.connection.execute('''
        SELECT DISTINCT business_email, company_name 
        FROM prospects 
        WHERE business_email IS NOT NULL AND business_email != ''
        AND business_email NOT IN (
            SELECT business_email FROM prospects 
            WHERE status IN ('rejected', 'unsubscribed')
        )
        ORDER BY company_name, business_email
    ''').fetchall()
    return [dict(r) for r in rows]"""
content = content.replace(old_get, new_get)

# 2. Replace DELETE with POST blacklist
old_delete = """class DeleteContactsRequest(BaseModel):
    emails: list[str]

@app.delete("/api/contacts")
def delete_contacts(req: DeleteContactsRequest, user: dict = Depends(get_current_user)):
    if not DB_PATH.exists():
        return {"success": False, "error": "DB not found"}
    db = OutreachDatabase(DB_PATH)
    try:
        placeholders = ",".join("?" * len(req.emails))
        db.connection.execute(f"DELETE FROM prospects WHERE business_email IN ({placeholders})", req.emails)
        db.connection.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}"""

new_blacklist = """class DeleteContactsRequest(BaseModel):
    emails: list[str]

@app.post("/api/contacts/blacklist")
def blacklist_contacts(req: DeleteContactsRequest, user: dict = Depends(get_current_user)):
    if not DB_PATH.exists():
        return {"success": False, "error": "DB not found"}
    db = OutreachDatabase(DB_PATH)
    try:
        placeholders = ",".join("?" * len(req.emails))
        db.connection.execute(f"UPDATE prospects SET status = 'rejected' WHERE business_email IN ({placeholders})", req.emails)
        db.connection.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}"""
content = content.replace(old_delete, new_blacklist)

with open("web_server.py", "w") as f:
    f.write(content)
print("Done patching web_server.py for blacklist")
