import re

with open("web_server.py", "r") as f:
    content = f.read()

new_endpoint = """
class DeleteContactsRequest(BaseModel):
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
        return {"success": False, "error": str(e)}

class ApproveRequest(BaseModel):
"""

content = content.replace("class ApproveRequest(BaseModel):", new_endpoint)

with open("web_server.py", "w") as f:
    f.write(content)
print("Done patching web_server.py for delete")
