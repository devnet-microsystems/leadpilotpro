import re

with open("web_server.py", "r") as f:
    content = f.read()

new_endpoint = """
class UpdateCompanyRequest(BaseModel):
    email: str
    company: str

@app.post("/api/contacts/update_company")
def update_contact_company(req: UpdateCompanyRequest, user: dict = Depends(get_current_user)):
    if not DB_PATH.exists():
        return {"success": False, "error": "DB not found"}
    db = OutreachDatabase(DB_PATH)
    try:
        db.connection.execute(
            "UPDATE prospects SET company_name = ? WHERE business_email = ?",
            (req.company.strip(), req.email.strip())
        )
        db.connection.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

class ApproveRequest(BaseModel):
"""

content = content.replace("class ApproveRequest(BaseModel):", new_endpoint)

with open("web_server.py", "w") as f:
    f.write(content)
print("Done patching web_server.py")
