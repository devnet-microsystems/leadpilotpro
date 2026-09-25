import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response, Depends, status, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import sqlite3
import subprocess
import csv
import hashlib
import secrets
import time
from datetime import datetime, timezone
import sqlite3
import subprocess
import csv
import json
import io
import hashlib
import secrets
import time
from datetime import datetime, timezone

from outreach_sender import OutreachDatabase, AuditLog, normalize_email, utc_now

app = FastAPI(title="LeadPilot Pro")

ROOT = Path(__file__).parent
DB_PATH = ROOT / "outreach_queue.sqlite3"
AUDIT_PATH = ROOT / "outreach_audit.jsonl"
STATIC_DIR = ROOT / "static"
STATIC_DIR.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def read_root(request: Request):
    token = request.cookies.get("session_token")
    if token and DB_PATH.exists():
        db = OutreachDatabase(DB_PATH)
        user = db.connection.execute(
            "SELECT 1 FROM sessions WHERE token = ? AND expires_at_utc > ?",
            (token, datetime.now(timezone.utc).isoformat())
        ).fetchone()
        if user:
            return FileResponse(STATIC_DIR / "index.html")
    return FileResponse(STATIC_DIR / "login.html")

def get_current_user(request: Request):
    token = request.cookies.get("session_token")
    if not token or not DB_PATH.exists():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    db = OutreachDatabase(DB_PATH)
    user = db.connection.execute(
        "SELECT u.id, u.username FROM users u JOIN sessions s ON u.id = s.user_id WHERE s.token = ? AND s.expires_at_utc > ?",
        (token, datetime.now(timezone.utc).isoformat())
    ).fetchone()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return dict(user)

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/login")
def login(req: LoginRequest, response: Response):
    if not DB_PATH.exists():
        db = OutreachDatabase(DB_PATH) # Will auto-create admin if empty
    else:
        db = OutreachDatabase(DB_PATH)
        
    user = db.connection.execute("SELECT id, password_hash, salt FROM users WHERE username = ?", (req.username,)).fetchone()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    password_hash = hashlib.pbkdf2_hmac('sha256', req.password.encode('utf-8'), user["salt"], 100000)
    if password_hash != user["password_hash"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc).timestamp() + (7 * 24 * 3600)
    expires_iso = datetime.fromtimestamp(expires_at, timezone.utc).isoformat()
    
    db.connection.execute("INSERT INTO sessions (token, user_id, expires_at_utc) VALUES (?, ?, ?)", (token, user["id"], expires_iso))
    db.connection.commit()
    
    response.set_cookie(key="session_token", value=token, httponly=True, samesite="lax", max_age=7*24*3600)
    return {"success": True}

@app.post("/api/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token and DB_PATH.exists():
        db = OutreachDatabase(DB_PATH)
        db.connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
        db.connection.commit()
    response.delete_cookie("session_token")
    return {"success": True}

@app.get("/api/status")
def get_status(user: dict = Depends(get_current_user)):
    if not DB_PATH.exists():
        return {"pending": 0, "approved": 0, "sent": 0, "total": 0, "suppressed": 0, "campaigns": []}
    
    db = OutreachDatabase(DB_PATH)
    total = db.connection.execute("SELECT COUNT(*) FROM prospects").fetchone()[0]
    pending = len(db.list_prospects("pending_review"))
    approved = len(db.list_prospects("approved"))
    try:
        sent = db.connection.execute("SELECT COUNT(*) FROM email_archive").fetchone()[0]
    except sqlite3.OperationalError:
        sent = 0
    
    # Get campaigns
    try:
        c_rows = db.connection.execute("SELECT name FROM campaigns ORDER BY name").fetchall()
        campaigns = [c["name"] for c in c_rows]
    except sqlite3.OperationalError:
        campaigns = []
    
    return {
        "total": total,
        "pending": pending,
        "approved": approved,
        "sent": sent,
        "campaigns": campaigns
    }

@app.get("/api/dashboard_stats")
def get_dashboard_stats(user: dict = Depends(get_current_user)):
    if not DB_PATH.exists():
        return {"total_campaigns": 0, "queries_generated": 0, "queries_executed": 0, "leads_found": 0, "qualified_leads": 0, "qualified_yield": "0.0%"}
        
    db = OutreachDatabase(DB_PATH)
    c = db.connection.cursor()
    try:
        total_campaigns = c.execute("SELECT COUNT(*) FROM research_campaigns").fetchone()[0]
        row = c.execute("SELECT COUNT(*), SUM(CASE WHEN status='executed' THEN 1 ELSE 0 END) FROM research_queries").fetchone()
        queries_generated = row[0]
        queries_executed = row[1] or 0
        leads_found = c.execute("SELECT COUNT(*) FROM prospects").fetchone()[0]
        qualified_leads = c.execute("SELECT COUNT(*) FROM prospects WHERE relevance_score >= 40").fetchone()[0]
    except sqlite3.OperationalError:
        total_campaigns = queries_generated = queries_executed = leads_found = qualified_leads = 0
        
    yield_pct = f"{(qualified_leads/leads_found)*100:.1f}%" if leads_found > 0 else "0.0%"
    return {
        "total_campaigns": total_campaigns,
        "queries_generated": queries_generated,
        "queries_executed": queries_executed,
        "leads_found": leads_found,
        "qualified_leads": qualified_leads,
        "qualified_yield": yield_pct
    }

@app.get("/api/chart_data")
def get_chart_data(user: dict = Depends(get_current_user)):
    if not DB_PATH.exists():
        return {"dates": [], "counts": []}
        
    db = OutreachDatabase(DB_PATH)
    rows = db.connection.execute('''
        SELECT substr(sent_at_utc, 1, 10) as date, COUNT(*) as count 
        FROM prospects 
        WHERE status = 'sent' AND sent_at_utc IS NOT NULL 
        GROUP BY date 
        ORDER BY date ASC
        LIMIT 14
    ''').fetchall()
    
    dates = [row["date"] for row in rows]
    counts = [row["count"] for row in rows]
    return {"dates": dates, "counts": counts}

@app.get("/api/companies")
def get_companies(user: dict = Depends(get_current_user)):
    if not DB_PATH.exists():
        return {"companies": []}
    db = OutreachDatabase(DB_PATH)
    db.connection.row_factory = sqlite3.Row
    c = db.connection.cursor()
    c.execute("""
        SELECT 
            company_name,
            MAX(target_url) as target_url,
            COUNT(*) as lead_count,
            SUM(CASE WHEN relevance_score >= 40 THEN 1 ELSE 0 END) as qualified_leads,
            MAX(relevance_score) as best_score,
            MAX(imported_at_utc) as last_discovered
        FROM prospects
        GROUP BY company_name, target_url
        ORDER BY best_score DESC, last_discovered DESC
    """)
    return {"companies": [dict(r) for r in c.fetchall()]}

@app.get("/api/companies/{company_name}/leads")
def get_company_leads(company_name: str, user: dict = Depends(get_current_user)):
    if not DB_PATH.exists():
        return {"leads": []}
    db = OutreachDatabase(DB_PATH)
    db.connection.row_factory = sqlite3.Row
    c = db.connection.cursor()
    c.execute("""
        SELECT *
        FROM prospects
        WHERE company_name = ?
        ORDER BY relevance_score DESC
    """, (company_name,))
    return {"leads": [dict(r) for r in c.fetchall()]}

@app.get("/api/analytics")
def get_analytics(user: dict = Depends(get_current_user)):
    if not DB_PATH.exists(): return {}
    db = OutreachDatabase(DB_PATH)
    
    # Lead relevance distribution
    relevance_rows = db.connection.execute("SELECT relevance_score FROM prospects WHERE status != 'rejected'").fetchall()
    high = sum(1 for r in relevance_rows if r["relevance_score"] >= 70)
    medium = sum(1 for r in relevance_rows if 40 <= r["relevance_score"] < 70)
    low = sum(1 for r in relevance_rows if r["relevance_score"] < 40)
    
    # Campaign performance
    camp_rows = db.connection.execute('''
        SELECT rc.name, COUNT(p.id) as leads
        FROM research_campaigns rc
        LEFT JOIN prospects p ON p.research_campaign_id = rc.id
        GROUP BY rc.id
    ''').fetchall()
    
    return {
        "relevance": {"high": high, "medium": medium, "low": low},
        "campaigns": {r["name"]: r["leads"] for r in camp_rows}
    }

@app.get("/api/prospects")
def get_prospects(status: str = "pending_review", date_from: str = None, date_to: str = None, user: dict = Depends(get_current_user)):
    if not DB_PATH.exists():
        return []
    db = OutreachDatabase(DB_PATH)
    return [dict(r) for r in db.list_prospects(status, date_from, date_to)]

@app.get("/api/contacts")
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
    return [dict(r) for r in rows]


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


class DeleteContactsRequest(BaseModel):
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
        return {"success": False, "error": str(e)}

class ApproveRequest(BaseModel):
    campaign_id: int | None = None


    id: int
    reason: str

@app.post("/api/approve")
def approve_prospect(req: ApproveRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    audit = AuditLog(AUDIT_PATH)
    if not req.reason.strip():
        raise HTTPException(status_code=400, detail="Reason required")
    if db.approve(req.id, req.reason, req.campaign_id):
        audit.write("prospect_approved", {"prospect_id": req.id, "reason": req.reason})
        return {"success": True}
    return {"success": False, "detail": "Prospect not found or not pending"}

class ApproveAllRequest(BaseModel):
    campaign: str
    reason: str

@app.post("/api/approve_all")
def api_approve_all(req: ApproveAllRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    audit = AuditLog(AUDIT_PATH)
    count = db.approve_all(req.campaign, req.reason)
    audit.write("campaign_approved", {"campaign": req.campaign, "reason": req.reason, "count": count})
    return {"success": True, "count": count}

class ApproveSelectedRequest(BaseModel):
    ids: list[int]
    campaign: str | None = None
    campaign_id: int | None = None
    reason: str = "Manually selected via Dashboard"

@app.post("/api/approve_selected")
def api_approve_selected(req: ApproveSelectedRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    audit = AuditLog(AUDIT_PATH)
    count = 0
    if req.campaign_id:
        camp_id = req.campaign_id
    elif req.campaign and req.campaign.strip():
        camp_id = db.get_or_create_campaign_id(req.campaign.strip())
    else:
        raise HTTPException(status_code=400, detail="Target campaign or campaign_id is required")
        
    cursor = db.connection.cursor()
    for pid in req.ids:
        cursor.execute("UPDATE prospects SET status='approved', campaign_id=?, reason_for_contact=? WHERE id=? AND status='pending_review'", (camp_id, req.reason, pid))
        if cursor.rowcount > 0:
            count += 1
            audit.write("prospect_approved", {"prospect_id": pid, "campaign_id": camp_id, "reason": req.reason})
    db.connection.commit()
    return {"success": True, "count": count}

class RejectSelectedRequest(BaseModel):
    ids: list[int]

@app.post("/api/reject_selected")
def api_reject_selected(req: RejectSelectedRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    audit = AuditLog(AUDIT_PATH)
    count = 0
    cursor = db.connection.cursor()
    for pid in req.ids:
        cursor.execute("UPDATE prospects SET status='rejected' WHERE id=? AND status IN ('pending_review', 'approved')", (pid,))
        if cursor.rowcount > 0:
            count += 1
            audit.write("prospect_rejected", {"prospect_id": pid})
    db.connection.commit()
    return {"success": True, "count": count}

class RestoreRequest(BaseModel):
    id: int

@app.post("/api/restore")
def api_restore(req: RestoreRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    audit = AuditLog(AUDIT_PATH)
    cursor = db.connection.cursor()
    cursor.execute("UPDATE prospects SET status='pending_review' WHERE id=? AND status='rejected'", (req.id,))
    success = cursor.rowcount > 0
    if success:
        audit.write("prospect_restored", {"prospect_id": req.id})
    db.connection.commit()
    return {"success": success}

class UpdateCompanyRequest(BaseModel):
    id: int
    company_name: str

@app.post("/api/prospects/update_company")
def update_company(req: UpdateCompanyRequest, user: dict = Depends(get_current_user)):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("UPDATE prospects SET company_name=? WHERE id=?", (req.company_name, req.id))
        conn.commit()
    finally:
        conn.close()
    return {"success": True}

class UpdateCampaignRequest(BaseModel):
    id: int
    campaign: str | None = None
    campaign_id: int | None = None

@app.post("/api/prospects/update_campaign")
def update_campaign(req: UpdateCampaignRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    if req.campaign_id:
        camp_id = req.campaign_id
    elif req.campaign and req.campaign.strip():
        camp_id = db.get_or_create_campaign_id(req.campaign.strip())
    else:
        raise HTTPException(status_code=400, detail="Target campaign or campaign_id is required")

    try:
        db.connection.execute("UPDATE prospects SET campaign_id=? WHERE id=?", (camp_id, req.id))
        db.connection.commit()
    finally:
        pass
    return {"success": True}

@app.get("/api/archive")
def get_archive(date_from: str = None, date_to: str = None, user: dict = Depends(get_current_user)):
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        query = """
            SELECT e.id as archive_id, e.business_email, c.name as campaign, e.sent_at_utc, e.message_text,
                   p.id as prospect_id, p.status as prospect_status
            FROM email_archive e
            LEFT JOIN campaigns c ON e.campaign_id = c.id
            LEFT JOIN prospects p ON e.business_email = p.business_email
            WHERE 1=1
        """
        params = []
        if date_from:
            query += " AND substr(e.sent_at_utc, 1, 10) >= ?"
            params.append(date_from)
        if date_to:
            query += " AND substr(e.sent_at_utc, 1, 10) <= ?"
            params.append(date_to)
            
        query += " ORDER BY e.sent_at_utc DESC LIMIT 100"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

class CampaignRequest(BaseModel):
    name: str
    template: str

@app.get("/api/campaigns")
def get_campaigns(user: dict = Depends(get_current_user)):
    if not DB_PATH.exists():
        return []
    db = OutreachDatabase(DB_PATH)
    try:
        rows = db.connection.execute("SELECT * FROM campaigns ORDER BY created_at_utc DESC").fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []

@app.post("/api/campaigns")
def create_campaign(req: CampaignRequest, user: dict = Depends(get_current_user)):
    if not req.name.strip() or not req.template.strip():
        raise HTTPException(status_code=400, detail="Name and template are required")
    from datetime import datetime, timezone
    db = OutreachDatabase(DB_PATH)
    try:
        db.connection.execute("INSERT INTO campaigns (name, template, created_at_utc) VALUES (?, ?, ?)",
            (req.name.strip(), req.template.strip(), datetime.now(timezone.utc).isoformat()))
        db.connection.commit()
        return {"success": True}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Campaign already exists")

@app.delete("/api/campaigns/{name}")
def delete_campaign(name: str, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    db.connection.execute("DELETE FROM campaigns WHERE name=?", (name,))
    db.connection.commit()
    return {"success": True}

# --- LeadPilot 2.0 AI Research Campaigns ---

class OfferRequest(BaseModel):
    name: str
    description: str

class ICPRequest(BaseModel):
    name: str
    roles: str
    industries: str
    locations: str

class ResearchCampaignRequest(BaseModel):
    name: str
    offer_id: int
    icp_id: int

@app.get("/api/sales_offers")
def get_sales_offers(user: dict = Depends(get_current_user)):
    if not DB_PATH.exists(): return []
    db = OutreachDatabase(DB_PATH)
    rows = db.connection.execute("SELECT * FROM sales_offers ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]

@app.post("/api/sales_offers")
def create_sales_offer(req: OfferRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    db.connection.execute(
        "INSERT INTO sales_offers (name, description, created_at_utc) VALUES (?, ?, ?)",
        (req.name.strip(), req.description.strip(), datetime.now(timezone.utc).isoformat())
    )
    db.connection.commit()
    return {"success": True}

@app.get("/api/icps")
def get_icps(user: dict = Depends(get_current_user)):
    if not DB_PATH.exists(): return []
    db = OutreachDatabase(DB_PATH)
    rows = db.connection.execute("SELECT * FROM ideal_customer_profiles ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]

@app.post("/api/icps")
def create_icp(req: ICPRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    db.connection.execute(
        "INSERT INTO ideal_customer_profiles (name, roles, industries, company_sizes, countries, languages, created_at_utc) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (req.name.strip(), req.roles.strip(), req.industries.strip(), 'Any', req.locations.strip(), 'English', datetime.now(timezone.utc).isoformat())
    )
    db.connection.commit()
    return {"success": True}

@app.get("/api/research_campaigns")
def get_research_campaigns(product_id: int = None, user: dict = Depends(get_current_user)):
    if not DB_PATH.exists(): return []
    db = OutreachDatabase(DB_PATH)

    # Optional product filter keeps the legacy endpoint backward-compatible
    # while supporting the product-driven P5.x frontend.
    query = """
        SELECT rc.*, o.name as offer_name, i.name as icp_name
        FROM research_campaigns rc
        LEFT JOIN sales_offers o ON rc.offer_id = o.id
        LEFT JOIN ideal_customer_profiles i ON rc.icp_id = i.id
    """
    params = ()
    if product_id is not None:
        query += " WHERE rc.product_id = ?"
        params = (product_id,)
    query += " ORDER BY rc.created_at_utc DESC"

    rows = db.connection.execute(query, params).fetchall()
    return [dict(r) for r in rows]

@app.post("/api/research_campaigns")
def create_research_campaign(req: ResearchCampaignRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    db.connection.execute(
        "INSERT INTO research_campaigns (name, offer_id, icp_id, status, created_at_utc) VALUES (?, ?, ?, 'DRAFT', ?)",
        (req.name.strip(), req.offer_id, req.icp_id, datetime.now(timezone.utc).isoformat())
    )
    # Also trigger template generation for the campaign
    campaign_id = db.connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.connection.commit()
    
    # Generate queries automatically
    try:
        from osint_engine.generator import QueryGenerator
        gen = QueryGenerator(str(DB_PATH))
        gen.generate_templates_for_campaign(campaign_id)
    except Exception as e:
        print(f"Error generating templates: {e}")
        
    return {"success": True}

@app.post("/api/research_campaigns/{id}/launch")
def launch_research_campaign(id: int, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    db.connection.execute("UPDATE research_campaigns SET status = 'RUNNING' WHERE id = ?", (id,))
    db.connection.commit()
    
    import subprocess
    cmd = ["python3", "public_osint_market_research.py", "--campaign-id", str(id)]
    subprocess.Popen(cmd)
    
    return {"success": True, "message": "Campaign launched in background."}

@app.get("/api/templates")
def get_templates(user: dict = Depends(get_current_user)):
    if not DB_PATH.exists():
        return []
    db = OutreachDatabase(DB_PATH)
    try:
        rows = db.connection.execute("SELECT name FROM templates ORDER BY name").fetchall()
        return [r["name"] for r in rows]
    except sqlite3.OperationalError:
        return []

@app.get("/api/templates/{name}")
def get_template_content(name: str, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    try:
        row = db.connection.execute("SELECT content FROM templates WHERE name=?", (name,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Template not found")
        return {"content": row["content"]}
    except sqlite3.OperationalError:
        raise HTTPException(status_code=404, detail="Template not found")

class TemplateRequest(BaseModel):
    content: str

@app.post("/api/templates/{name}")
def save_template(name: str, req: TemplateRequest, user: dict = Depends(get_current_user)):
    if not name.endswith(".txt"):
        name += ".txt"
    from datetime import datetime, timezone
    db = OutreachDatabase(DB_PATH)
    db.connection.execute(
        "INSERT INTO templates (name, content, created_at_utc) VALUES (?, ?, ?) ON CONFLICT(name) DO UPDATE SET content=excluded.content",
        (name, req.content, datetime.now(timezone.utc).isoformat())
    )
    db.connection.commit()
    return {"success": True, "message": "Template saved successfully"}

@app.delete("/api/templates/{name}")
def delete_template(name: str, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    db.connection.execute("DELETE FROM templates WHERE name=?", (name,))
    db.connection.commit()
    return {"success": True, "message": "Template deleted"}

@app.get("/api/queries")
def get_queries(user: dict = Depends(get_current_user)):
    if not DB_PATH.exists():
        return []
    db = OutreachDatabase(DB_PATH)
    try:
        rows = db.connection.execute("SELECT query FROM research_queries").fetchall()
        return [r["query"] for r in rows]
    except sqlite3.OperationalError:
        return []

class ToggleQueryRequest(BaseModel):
    is_enabled: int

@app.post("/api/campaign_queries/{query_id}/toggle")
def toggle_campaign_query(query_id: int, req: ToggleQueryRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    db.connection.execute("UPDATE campaign_queries SET is_enabled = ? WHERE id = ?", (req.is_enabled, query_id))
    db.connection.commit()
    return {"status": "success"}

@app.post("/api/campaigns/{campaign_id}/generate_plan")
def generate_campaign_plan(campaign_id: int, user: dict = Depends(get_current_user)):
    from osint_engine.generator import QueryGenerator
    gen = QueryGenerator(db_path=str(DB_PATH))
    queries = gen.get_concrete_queries(campaign_id)
    
    db = OutreachDatabase(DB_PATH)
    db.connection.execute("DELETE FROM campaign_queries WHERE campaign_id=?", (campaign_id,))
    
    for q in queries:
        db.connection.execute("""
            INSERT INTO campaign_queries (campaign_id, family, query, target_key, is_enabled)
            VALUES (?, ?, ?, ?, 1)
        """, (campaign_id, q["family"], q["query"], q["target_key"]))
    db.connection.commit()
    return {"generated": len(queries)}

@app.get("/api/campaigns/{campaign_id}/queries")
def get_campaign_queries(campaign_id: int, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    db.connection.row_factory = sqlite3.Row
    rows = db.connection.execute("SELECT * FROM campaign_queries WHERE campaign_id=?", (campaign_id,)).fetchall()
    return [dict(r) for r in rows]

class UpdateCampaignQueryRequest(BaseModel):
    query: str

@app.put("/api/campaign_queries/{query_id}")
def update_campaign_query(query_id: int, req: UpdateCampaignQueryRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    db.connection.execute("UPDATE campaign_queries SET query = ? WHERE id = ?", (req.query, query_id))
    db.connection.commit()
    return {"status": "success"}

import subprocess
import sys
import os

@app.post("/api/campaigns/{campaign_id}/launch")
def launch_campaign(campaign_id: int, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    db.connection.execute("UPDATE research_campaigns SET status = 'RUNNING' WHERE id = ?", (campaign_id,))
    db.connection.commit()
    
    # Avvia in background il motore OSINT
    base_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(base_dir, ".venv", "bin", "python")
    cmd = [venv_python, "public_osint_market_research.py", "--campaign-id", str(campaign_id)]
    
    # Eseguiamo il processo scollegato in modo che non blocchi il server
    subprocess.Popen(cmd, cwd=base_dir, start_new_session=True)
    
    return {"status": "success"}

class QueryRequest(BaseModel):
    query: str

@app.post("/api/queries")
def add_query(req: QueryRequest, user: dict = Depends(get_current_user)):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
        
    db = OutreachDatabase(DB_PATH)
    try:
        db.connection.execute("INSERT INTO research_queries (query) VALUES (?)", (query,))
        db.connection.commit()
        return {"success": True, "message": "Query added"}
    except sqlite3.IntegrityError:
        return {"success": True, "message": "Query already exists"}

@app.delete("/api/queries")
def delete_query(req: QueryRequest, user: dict = Depends(get_current_user)):
    query_to_delete = req.query.strip()
    db = OutreachDatabase(DB_PATH)
    cursor = db.connection.execute("DELETE FROM research_queries WHERE query=?", (query_to_delete,))
    db.connection.commit()
    
    if cursor.rowcount == 0:
        return {"success": False, "message": "Query not found"}
            
    return {"success": True, "message": "Query deleted"}

@app.put("/api/queries")
def edit_query(req: dict, user: dict = Depends(get_current_user)):
    old_query = req.get("old_query", "").strip()
    new_query = req.get("new_query", "").strip()
    if not old_query or not new_query:
        raise HTTPException(status_code=400, detail="Invalid request")
        
    db = OutreachDatabase(DB_PATH)
    try:
        cursor = db.connection.execute("UPDATE research_queries SET query=? WHERE query=?", (new_query, old_query))
        if cursor.rowcount == 0:
            return {"success": False, "message": "Original query not found"}
        db.connection.commit()
        return {"success": True, "message": "Query updated"}
    except sqlite3.IntegrityError:
        return {"success": False, "message": "New query already exists"}

@app.get("/api/query_history")
def get_query_history(user: dict = Depends(get_current_user)):
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM search_history ORDER BY executed_at_utc DESC LIMIT 100").fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

RESEARCH_LOG_PATH = ROOT / "research.log"

def run_research_task(queries: list[str] = None):
    with open(RESEARCH_LOG_PATH, "w") as f:
        f.write("Starting background OSINT research...\n")
        if queries:
            f.write(f"Targeting specific queries: {', '.join(queries)}\n")
        else:
            f.write("Targeting all active queries in database.\n")
            
        venv_python = ROOT / ".venv" / "bin" / "python"
        cmd = [str(venv_python), "-u", str(ROOT / "public_osint_market_research.py"), "--results-per-query", "15"]
        if queries:
            cmd.extend(["--queries"] + queries)
        
        subprocess.run(cmd, cwd=str(ROOT), stdout=f, stderr=subprocess.STDOUT)

class ResearchRequest(BaseModel):
    queries: list[str] | None = None

@app.post("/api/research")
def start_research(req: ResearchRequest, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    background_tasks.add_task(run_research_task, req.queries)
    return {"success": True, "message": "Research started in background."}

class SendRequest(BaseModel):
    campaign: str
    limit: int
    scheduled_at: str | None = None

SEND_LOG_PATH = ROOT / "campaign_send.log"

def run_send_task(campaign: str, limit: int):
    with open(SEND_LOG_PATH, "w") as f:
        f.write(f"Starting campaign '{campaign}' (limit: {limit})...\n")

    db = OutreachDatabase(DB_PATH)
    row = db.connection.execute("SELECT template FROM campaigns WHERE name=?", (campaign,)).fetchone()
    if not row:
        with open(SEND_LOG_PATH, "a") as f:
            f.write(f"Error: Campaign not found.\n")
        return
    template = row["template"]
    
    template_row = db.connection.execute("SELECT content FROM templates WHERE name=?", (template,)).fetchone()
    if not template_row:
        with open(SEND_LOG_PATH, "a") as f:
            f.write(f"Error: Template not found.\n")
        return
        
    venv_python = ROOT / ".venv" / "bin" / "python"
    
    with open(SEND_LOG_PATH, "a") as f:
        subprocess.run([
            str(venv_python), "-u", str(ROOT / "outreach_sender.py"),
            "--database", str(DB_PATH),
            "--audit-log", str(AUDIT_PATH),
            "send",
            "--campaign", campaign,
            "--template-content", template_row["content"],
            "--limit", str(limit),
            "--send", "--confirm-send"
        ], cwd=str(ROOT), stdout=f, stderr=subprocess.STDOUT)

@app.post("/api/send")
def trigger_send(req: SendRequest, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    
    # SAFETY CHECK: Prevent sending if template contains AI placeholders
    camp_id = db.get_or_create_campaign_id(req.campaign.strip())
    row = db.connection.execute("SELECT template FROM campaigns WHERE id = ?", (camp_id,)).fetchone()
    if row:
        template = row["template"]
        if "[INSERISCI" in template.upper() or "[INSERT" in template.upper():
            raise HTTPException(status_code=400, detail="Il template contiene dei segnaposto non compilati (es. [INSERISCI...]). Modifica il template prima di inviare la campagna!")
            

    if req.scheduled_at:
        camp_id = db.get_or_create_campaign_id(req.campaign.strip())
        db.connection.execute(
            "INSERT INTO scheduled_jobs (campaign_id, daily_limit, scheduled_at_utc) VALUES (?, ?, ?)",
            (camp_id, req.limit, req.scheduled_at)
        )
        db.connection.commit()
        return {"success": True, "message": f"Campaign scheduled for {req.scheduled_at}"}
    
    background_tasks.add_task(run_send_task, req.campaign, req.limit)
    return {"success": True, "message": "Campaign outreach started in background."}

@app.get("/api/send_logs")
def get_send_logs(user: dict = Depends(get_current_user)):
    if not SEND_LOG_PATH.exists():
        return {"logs": ""}
    with open(SEND_LOG_PATH, "r") as f:
        return {"logs": f.read()}

@app.get("/api/research_logs")
def get_research_logs(user: dict = Depends(get_current_user)):
    if not RESEARCH_LOG_PATH.exists():
        return {"logs": ""}
    with open(RESEARCH_LOG_PATH, "r") as f:
        return {"logs": f.read()}

@app.get("/api/download_log/{log_type}")
def download_log(log_type: str, user: dict = Depends(get_current_user)):
    if log_type == "send":
        path = SEND_LOG_PATH
        filename = "campaign_send_logs.txt"
    elif log_type == "research":
        path = RESEARCH_LOG_PATH
        filename = "osint_research_logs.txt"
    else:
        raise HTTPException(status_code=400, detail="Invalid log type")
        
    if not path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")
        
    return FileResponse(path, media_type='text/plain', filename=filename)

class ImportCsvRequest(BaseModel):
    campaign: str
    csv_content: str

class ManualAddRequest(BaseModel):
    email: str
    company_name: str
    campaign: str

@app.post("/api/prospects/manual_add")
def api_manual_add(req: ManualAddRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    email = normalize_email(req.email)
    
    if not email or "@" not in email:
        return {"success": False, "error": "Indirizzo email non valido."}
        
    if db.is_suppressed(email):
        return {"success": False, "error": "Email presente nella blocklist (soppressa)."}
        
    camp_id = None
    if req.campaign and req.campaign.strip():
        camp_id = db.get_or_create_campaign_id(req.campaign.strip())
        
    cursor = db.connection.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO prospects
        (target_url, company_name, business_email, source_file, campaign_id, imported_at_utc)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("", req.company_name.strip() or "Unknown Company", email, "Manual Entry", camp_id, utc_now())
    )
    
    added = cursor.rowcount > 0
    db.connection.commit()
    
    if added:
        return {"success": True, "message": "Lead aggiunto con successo!"}
    else:
        return {"success": False, "error": "Questo lead esiste già nel database."}
        
@app.post("/api/import_csv")
def api_import_csv(req: ImportCsvRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    audit = AuditLog(AUDIT_PATH)
    
    csv_text = req.csv_content.lstrip('\ufeff')
    f = io.StringIO(csv_text)
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames or []
    
    email_col = next((h for h in fieldnames if h.lower().strip() in ["email", "email address", "work email", "verified email", "verified corporate email"]), None)
    company_col = next((h for h in fieldnames if h.lower().strip() in ["company", "company name", "organization", "extracted name/title", "company name/title"]), None)
    name_col = next((h for h in fieldnames if h.lower().strip() in ["first name", "name", "full name", "contact name", "contact", "last name", "person"]), None)
    url_col = next((h for h in fieldnames if h.lower().strip() in ["website", "company website", "target url", "url", "domain"]), None)
    
    if not email_col or not company_col:
        return {"success": False, "error": "CSV must contain at least an Email and a Company column."}
        
    added = 0
    skipped = 0
    cursor = db.connection.cursor()
    
    for row in reader:
        email = normalize_email(row.get(email_col, ""))
        company = row.get(company_col, "").strip()
        if not company:
            company = "Unknown company"
            
        url = row.get(url_col, "").strip() if url_col else ""
        name = row.get(name_col, "").strip() if name_col else ""
        if name:
            company = f"{company} ({name})"
            
        if not email or "@" not in email:
            skipped += 1
            continue
            
        if db.is_suppressed(email):
            skipped += 1
            continue
            
        camp_id = db.get_or_create_campaign_id(req.campaign.strip())
        cursor.execute(
            """
            INSERT OR IGNORE INTO prospects
            (target_url, company_name, business_email, source_file, campaign_id, imported_at_utc)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (url, company, email, "UI_CSV_Upload", camp_id, utc_now())
        )
        if cursor.rowcount > 0:
            added += 1
        else:
            skipped += 1
            
    db.connection.commit()
    audit.write("csv_imported_ui", {"campaign": req.campaign, "added": added, "skipped": skipped})
    return {"success": True, "added": added, "skipped": skipped}

class QuickSendLead(BaseModel):
    email: str
    company: str

class QuickSendRequest(BaseModel):
    campaign: str
    leads: list[QuickSendLead]
    limit: int = 50

@app.post("/api/quick_send")
def api_quick_send(req: QuickSendRequest, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    audit = AuditLog(AUDIT_PATH)
    
    # SAFETY CHECK: Prevent sending if template contains AI placeholders
    camp_id = db.get_or_create_campaign_id(req.campaign.strip())
    row = db.connection.execute("SELECT template FROM campaigns WHERE id = ?", (camp_id,)).fetchone()
    if row:
        template = row["template"]
        if "[INSERISCI" in template.upper() or "[INSERT" in template.upper():
            raise HTTPException(status_code=400, detail="Il template contiene dei segnaposto non compilati (es. [INSERISCI...]). Modifica il template prima di inviare la campagna!")

    cursor = db.connection.cursor()
    added = 0
    skipped = 0
    
    for lead in req.leads:
        email = normalize_email(lead.email)
        company = lead.company.strip() or "Unknown Company"
        
        if not email or "@" not in email:
            skipped += 1
            continue
            
        if db.is_suppressed(email):
            skipped += 1
            continue
            
        cursor.execute(
            """
            INSERT INTO prospects (target_url, company_name, business_email, source_file, campaign_id, status, imported_at_utc, reason_for_contact)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'Quick Send UI')
            ON CONFLICT(business_email) DO UPDATE SET status='approved', campaign_id=excluded.campaign_id, reason_for_contact='Quick Send UI'
            """,
            ("", company, email, "Quick_Send_UI", camp_id, utc_now())
        )
        added += 1
        
    db.connection.commit()
    audit.write("quick_send_imported", {"campaign": req.campaign, "added": added, "skipped": skipped})
    
    if added > 0:
        background_tasks.add_task(run_send_task, req.campaign, req.limit)
        return {"success": True, "added": added, "skipped": skipped, "message": f"{added} leads importati ed invio avviato!"}
    else:
        return {"success": False, "error": "Nessun lead valido trovato da inviare."}

class GenerateRequest(BaseModel):
    context: str | None = ""

@app.post("/api/generate_template")
def generate_template(req: GenerateRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    rows = db.connection.execute("SELECT key, value FROM settings").fetchall()
    settings = {r["key"]: r["value"] for r in rows}
    
    api_key = settings.get("ai_api_key", "")
    base_url = settings.get("ai_base_url", "https://api.openai.com/v1").rstrip("/")
    model = settings.get("ai_model", "gpt-4o")
    
    if not api_key:
        raise HTTPException(status_code=400, detail="AI API Key is not configured in Settings.")
        
    url = f"{base_url}/chat/completions"
    
    messages = [
        {"role": "system", "content": "You are an expert sales copywriter. Write a short, professional cold email."}
    ]
    if req.context:
        messages.append({"role": "user", "content": f"Please write the email based on this context: {req.context}"})
    else:
        messages.append({"role": "user", "content": "Please write the email now."})
        
    data = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0.7
    }).encode("utf-8")
    
    import urllib.request
    request = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    })
    
    try:
        with urllib.request.urlopen(request) as response:
            result = json.loads(response.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            return {"success": True, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

class SettingsRequest(BaseModel):
    smtp_host: str
    smtp_port: str
    smtp_user: str
    smtp_password: str
    smtp_from_email: str
    company_name: str
    company_website: str
    daily_limit: str
    delay_minimum: str
    delay_maximum: str
    ai_api_key: str | None = ""
    ai_base_url: str | None = "https://api.openai.com/v1"
    ai_model: str | None = "gpt-4o"
    lusha_api_key: str | None = ""
    imap_host: str | None = ""
    imap_port: str | None = "993"

@app.get("/api/settings")
def get_settings(user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    rows = db.connection.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}

@app.post("/api/settings")
def update_settings(req: SettingsRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    settings = [
        ("smtp_host", req.smtp_host),
        ("smtp_port", req.smtp_port),
        ("smtp_user", req.smtp_user),
        ("smtp_password", req.smtp_password),
        ("smtp_from_email", req.smtp_from_email),
        ("company_name", req.company_name),
        ("company_website", req.company_website),
        ("daily_limit", req.daily_limit),
        ("delay_minimum", req.delay_minimum),
        ("delay_maximum", req.delay_maximum),
        ("ai_api_key", req.ai_api_key),
        ("ai_base_url", req.ai_base_url),
        ("ai_model", req.ai_model),
        ("lusha_api_key", req.lusha_api_key),
        ("imap_host", req.imap_host),
        ("imap_port", req.imap_port)
    ]
    for key, val in settings:
        db.connection.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, val))
    db.connection.commit()
    return {"success": True}

class ManualMarkRequest(BaseModel):
    prospect_id: int
    
@app.post("/api/prospects/mark_replied")
def api_mark_replied(req: ManualMarkRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    # Using a fake message_id and body for manual marking
    db.mark_replied(req.prospect_id, "manual-mark", "Manually Marked as Replied", "")
    return {"success": True}

class RequeueRequest(BaseModel):
    prospect_ids: list[int]
    campaign_id: int

@app.post("/api/prospects/requeue")
def api_prospects_requeue(req: RequeueRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    try:
        # Note: We update status to 'approved' and change the campaign_id,
        # but we DO NOT clear message_id, so the sender can thread it!
        placeholders = ",".join("?" * len(req.prospect_ids))
        query = f"UPDATE prospects SET status = 'approved', campaign_id = ?, last_error = NULL WHERE id IN ({placeholders})"
        db.connection.execute(query, [req.campaign_id] + req.prospect_ids)
        db.connection.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/prospects/mark_unsubscribed")
def api_mark_unsubscribed(req: ManualMarkRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    email = db.connection.execute("SELECT business_email FROM prospects WHERE id = ?", (req.prospect_id,)).fetchone()
    if email:
        db.mark_unsubscribed(email[0], "Manually Marked as Unsubscribed")
        return {"success": True}
    return {"success": False, "error": "Prospect non trovato."}

@app.post("/api/imap/sync")
def api_imap_sync(user: dict = Depends(get_current_user)):
    import sys
    import importlib
    sys.path.append(str(ROOT))
    import imap_poller
    importlib.reload(imap_poller)
    db = OutreachDatabase(DB_PATH)
    res = imap_poller.sync_imap_inbox(db)
    return res

class LushaSearchRequest(BaseModel):
    domain: str
    role: str
    limit: int = 10

@app.post("/api/lusha/search")
def lusha_search(req: LushaSearchRequest, user: dict = Depends(get_current_user)):
    import json
    import urllib.request
    
    db = OutreachDatabase(DB_PATH)
    settings = {r["key"]: r["value"] for r in db.connection.execute("SELECT key, value FROM settings").fetchall()}
    api_key = settings.get("lusha_api_key", "").strip()
    
    if not api_key:
        raise HTTPException(status_code=400, detail="Lusha API Key is missing in Settings.")
        
    url = "https://api.lusha.com/v3/contacts/search-and-enrich"
    headers = {
        "api_key": api_key,
        "Content-Type": "application/json"
    }
    
    # We will use search-and-enrich since it yields emails directly
    payload = {
        "companyDomains": [req.domain.strip()],
        "contactJobTitles": [req.role.strip()],
        "limit": min(req.limit, 50) # Keep limit sane
    }
    
    req_obj = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req_obj) as response:
            res_body = response.read()
            data = json.loads(res_body)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        raise HTTPException(status_code=e.code, detail=f"Lusha API Error: {err_msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    added = 0
    skipped = 0
    
    cursor = db.connection.cursor()
    
    for contact in data.get("data", []):
        email = contact.get("emailAddresses", [{}])[0].get("email", "")
        if not email:
            skipped += 1
            continue
            
        first = contact.get("firstName", "")
        last = contact.get("lastName", "")
        name = f"{first} {last}".strip()
        
        company = contact.get("company", {}).get("name", req.domain)
        if name:
            company = f"{company} ({name})"
            
        target_url = contact.get("company", {}).get("domain", req.domain)
        if not target_url.startswith("http"):
            target_url = "https://" + target_url
            
        if db.is_suppressed(email):
            skipped += 1
            continue
            
        cursor.execute(
            """
            INSERT OR IGNORE INTO prospects
            (target_url, company_name, business_email, source_file, campaign_id, imported_at_utc)
            VALUES (?, ?, ?, ?, NULL, ?)
            """,
            (target_url, company, email, "Lusha API", utc_now())
        )
        if cursor.rowcount > 0:
            added += 1
        else:
            skipped += 1
            
    db.connection.commit()
    
    return {
        "success": True,
        "added": added,
        "skipped": skipped
    }

@app.get("/api/lusha/credits")
def lusha_credits(user: dict = Depends(get_current_user)):
    import json
    import urllib.request
    
    db = OutreachDatabase(DB_PATH)
    settings = {r["key"]: r["value"] for r in db.connection.execute("SELECT key, value FROM settings").fetchall()}
    api_key = settings.get("lusha_api_key", "").strip()
    
    if not api_key:
        return {"status": "error", "message": "API Key missing"}
        
    url = "https://api.lusha.com/v3/account/usage"
    headers = {
        "api_key": api_key,
        "Content-Type": "application/json"
    }
    
    req_obj = urllib.request.Request(url, headers=headers, method="GET")
    
    try:
        with urllib.request.urlopen(req_obj) as response:
            data = json.loads(response.read())
            # For this endpoint, we'll return the full data and let the frontend parse it.
            return {"status": "success", "data": data}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        return {"status": "error", "message": f"API Error: {e.code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class LushaAdvancedSearchRequest(BaseModel):
    country: str | None = None
    state: str | None = None
    industry: str | None = None
    role: str | None = None
    size_min: int | None = None
    size_max: int | None = None
    limit: int = 25

@app.post("/api/lusha/prospect")
def lusha_prospect(req: LushaAdvancedSearchRequest, user: dict = Depends(get_current_user)):
    import json
    import urllib.request
    
    db = OutreachDatabase(DB_PATH)
    settings = {r["key"]: r["value"] for r in db.connection.execute("SELECT key, value FROM settings").fetchall()}
    api_key = settings.get("lusha_api_key", "").strip()
    
    if not api_key:
        raise HTTPException(status_code=400, detail="Lusha API Key is missing in Settings.")
        
    url_prospect = "https://api.lusha.com/v3/contacts/prospecting"
    url_enrich = "https://api.lusha.com/v3/contacts/enrich"
    headers = {
        "api_key": api_key,
        "Content-Type": "application/json"
    }
    
    # 1. Build Prospecting Filters
    filters = {"companies": {"include": {}}, "contacts": {"include": {}}}
    
    if req.country or req.state:
        loc = {}
        if req.country: loc["country"] = req.country.strip()
        if req.state: loc["state"] = req.state.strip()
        filters["companies"]["include"]["locations"] = [loc]
        
    if req.industry:
        filters["companies"]["include"]["industriesLabels"] = [req.industry.strip()]
        
    if req.size_min is not None or req.size_max is not None:
        size_filter = {}
        if req.size_min: size_filter["min"] = req.size_min
        if req.size_max: size_filter["max"] = req.size_max
        filters["companies"]["include"]["sizes"] = [size_filter]
        
    if req.role:
        filters["contacts"]["include"]["titles"] = [req.role.strip()]
        
    payload_prospect = {
        "pagination": {"page": 0, "size": min(req.limit, 50)},
        "filters": filters
    }
    
    # Send Prospect Request
    req_obj = urllib.request.Request(
        url_prospect,
        data=json.dumps(payload_prospect).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req_obj) as response:
            res_body = response.read()
            data_prospect = json.loads(res_body)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        raise HTTPException(status_code=e.code, detail=f"Lusha Prospect API Error: {err_msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    results = data_prospect.get("results", [])
    if not results:
        return {"success": True, "added": 0, "skipped": 0, "detail": "No prospects matched your filters."}
        
    # Extract IDs for Enrichment
    contact_ids = [c["id"] for c in results if "id" in c]
    if not contact_ids:
        return {"success": True, "added": 0, "skipped": 0, "detail": "No valid contact IDs returned."}
        
    # 2. Enrich the Contacts to get Emails
    payload_enrich = {
        "ids": contact_ids,
        "reveal": ["emails"]
    }
    
    req_enrich = urllib.request.Request(
        url_enrich,
        data=json.dumps(payload_enrich).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req_enrich) as response:
            res_body = response.read()
            data_enrich = json.loads(res_body)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        raise HTTPException(status_code=e.code, detail=f"Lusha Enrich API Error: {err_msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    added = 0
    skipped = 0
    cursor = db.connection.cursor()
    
    enriched_results = data_enrich.get("results", [])
    for contact in enriched_results:
        if contact.get("error"):
            skipped += 1
            continue
            
        emails = contact.get("emails", [])
        if not emails:
            skipped += 1
            continue
            
        email = emails[0].get("email", "")
        if not email:
            skipped += 1
            continue
            
        first = contact.get("firstName", "")
        last = contact.get("lastName", "")
        name = f"{first} {last}".strip()
        
        company_data = contact.get("company", {})
        target_url = company_data.get("domain", "")
        if target_url and not target_url.startswith("http"):
            target_url = "https://" + target_url
            
        company_name = company_data.get("name", "Unknown Company")
        if name:
            company_name = f"{company_name} ({name})"
            
        if db.is_suppressed(email):
            skipped += 1
            continue
            
        cursor.execute(
            """
            INSERT OR IGNORE INTO prospects
            (target_url, company_name, business_email, source_file, campaign_id, imported_at_utc)
            VALUES (?, ?, ?, ?, NULL, ?)
            """,
            (target_url, company_name, email, "Lusha Prospecting", utc_now())
        )
        if cursor.rowcount > 0:
            added += 1
        else:
            skipped += 1
            
    db.connection.commit()
    return {
        "success": True,
        "added": added,
        "skipped": skipped
    }

class TestSmtpRequest(BaseModel):
    email: str
    template: str

@app.post("/api/test_smtp")
def api_test_smtp(req: TestSmtpRequest, user: dict = Depends(get_current_user)):
    import smtplib, ssl, traceback
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    db = OutreachDatabase(DB_PATH)
    rows = db.connection.execute("SELECT key, value FROM settings").fetchall()
    settings = {r["key"]: r["value"] for r in rows}
    
    try:
        t_row = db.connection.execute("SELECT content FROM templates WHERE name = ?", (req.template,)).fetchone()
        if not t_row:
            return {"success": False, "log": f"Template not found: {req.template}"}
            
        content = t_row["content"]
        lines = content.split('\n')
        subject = "Test Subject"
        body = content
        
        if lines and lines[0].startswith("Subject:"):
            subject = lines[0].replace("Subject:", "").strip()
            body = "\n".join(lines[1:]).strip()
            
        subject = subject.replace("{company_name}", "Test Agency")
        body = body.replace("{first_name}", "Admin").replace("{company_name}", "Test Agency").replace("{location}", "your city").replace("{reason_for_contact}", "testing the SMTP connection")
        
        msg = MIMEMultipart()
        msg['From'] = f"{settings.get('company_name', 'System')} <{settings.get('smtp_from_email', '')}>"
        msg['To'] = req.email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        log_msgs = []
        log_msgs.append(f"Connecting to {settings.get('smtp_host')}:{settings.get('smtp_port')}...")
        
        context = ssl.create_default_context()
        with smtplib.SMTP(settings.get('smtp_host'), int(settings.get('smtp_port')), timeout=10) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            log_msgs.append("TLS established. Authenticating...")
            server.login(settings.get('smtp_user'), settings.get('smtp_password'))
            log_msgs.append("Authenticated successfully. Sending email...")
            server.send_message(msg)
            
        log_msgs.append("Success: Test email sent successfully to " + req.email)
        return {"success": True, "log": "\n".join(log_msgs)}
    except Exception as e:
        err = traceback.format_exc()
        return {"success": False, "log": f"FAILED:\n{err}"}
    
class PasswordRequest(BaseModel):
    old_password: str
    new_password: str

@app.post("/api/change_password")
def change_password(req: PasswordRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    u = db.connection.execute("SELECT password_hash, salt FROM users WHERE id = ?", (user["id"],)).fetchone()
    old_hash = hashlib.pbkdf2_hmac('sha256', req.old_password.encode('utf-8'), u["salt"], 100000)
    if old_hash != u["password_hash"]:
        raise HTTPException(status_code=400, detail="Invalid old password")
        
    new_salt = os.urandom(16)
    new_hash = hashlib.pbkdf2_hmac('sha256', req.new_password.encode('utf-8'), new_salt, 100000)
    db.connection.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (new_hash, new_salt, user["id"]))
    db.connection.commit()
    return {"success": True}

import asyncio

async def scheduler_loop():
    while True:
        try:
            if DB_PATH.exists():
                db = OutreachDatabase(DB_PATH)
                now_iso = datetime.now(timezone.utc).isoformat()
                
                # Find pending jobs that are due
                jobs = db.connection.execute(
                    """
                    SELECT j.id, c.name as campaign, j.daily_limit 
                    FROM scheduled_jobs j
                    JOIN campaigns c ON j.campaign_id = c.id
                    WHERE j.status = 'pending' AND j.scheduled_at_utc <= ?
                    """, 
                    (now_iso,)
                ).fetchall()
                
                for job in jobs:
                    db.connection.execute("UPDATE scheduled_jobs SET status = 'completed' WHERE id = ?", (job["id"],))
                    db.connection.commit()
                    
                    # Run the job
                    run_send_task(job["campaign"], job["daily_limit"])
                    
        except Exception as e:
            print(f"Scheduler error: {e}")
            
        await asyncio.sleep(60)


# ==============================================================================
# P5.3C: Orchestrator Endpoints
# ==============================================================================

@app.get("/api/orchestrator/pipeline_status")
def orchestrator_pipeline_status(product_id: int, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    
    q_discovered = "SELECT count(distinct p.id) FROM prospects p JOIN prospect_sources ps ON p.id = ps.prospect_id JOIN query_runs qr ON ps.query_run_id = qr.run_id JOIN campaign_queries cq ON qr.target_key = cq.target_key JOIN research_campaigns rc ON cq.campaign_id = rc.id WHERE rc.product_id = ?"
    discovered = db.connection.execute(q_discovered, (product_id,)).fetchone()[0] or 0
    
    q_qualified = "SELECT count(distinct p.id) FROM prospects p JOIN prospect_product_fit pf ON p.id = pf.prospect_id WHERE pf.product_id = ? AND pf.fit_status = 'FIT'"
    qualified = db.connection.execute(q_qualified, (product_id,)).fetchone()[0] or 0
    
    q_rejected = """
        SELECT count(distinct p.id)
        FROM prospects p
        LEFT JOIN prospect_product_fit pf ON p.id = pf.prospect_id AND pf.product_id = ?
        WHERE pf.fit_status IN ('REJECT', 'UNFIT', 'UNQUALIFIED')
           OR (pf.id IS NULL AND p.qualification_status IN ('REJECTED', 'UNQUALIFIED'))
    """
    rejected = db.connection.execute(q_rejected, (product_id,)).fetchone()[0] or 0
    
    q_approved = "SELECT count(*) FROM product_campaigns WHERE product_id = ? AND status = 'APPROVED'"
    approved = db.connection.execute(q_approved, (product_id,)).fetchone()[0] or 0
    
    exported = 0
    
    return {
        "discovered": discovered,
        "qualified": qualified,
        "rejected": rejected,
        "approved": approved,
        "exported": exported
    }

@app.post("/api/orchestrator/evaluate_fit")
def orchestrator_evaluate_fit(payload: dict, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    product_id = payload.get("product_id")
    if not product_id:
         raise HTTPException(status_code=400, detail="Missing product_id")
    db = OutreachDatabase(DB_PATH)
    q = "SELECT COUNT(*) FROM prospect_product_fit WHERE product_id = ? AND fit_status = 'FIT'"
    count = db.connection.execute(q, (product_id,)).fetchone()[0]
    
    return {"success": True, "stats": {"qualified": count}}

@app.get("/api/orchestrator/evidence")
def orchestrator_evidence(product_id: int, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    q = "SELECT p.id, p.company_name, p.target_url, pf.fit_status, pf.reason, pf.matched_signals, pf.evidence_reviewed_at FROM prospects p JOIN prospect_product_fit pf ON p.id = pf.prospect_id WHERE pf.product_id = ? AND pf.fit_status = 'FIT'"
    rows = db.connection.execute(q, (product_id,)).fetchall()
    return [dict(r) for r in rows]

@app.post("/api/orchestrator/prospect/{id}/review")
def orchestrator_review_prospect(id: int, payload: dict, user: dict = Depends(get_current_user)):
    action = payload.get("action")
    db = OutreachDatabase(DB_PATH)
    if action == "APPROVE":
        db.connection.execute("UPDATE prospect_product_fit SET evidence_reviewed_at = ? WHERE prospect_id = ?", (datetime.now(timezone.utc).isoformat(), id))
    elif action == "REJECT":
        reason = payload.get("reason", "Manual Override")
        db.connection.execute("UPDATE prospects SET qualification_status = 'REJECTED', rejection_reason = ? WHERE id = ?", (reason, id))
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    db.connection.commit()
    return {"success": True}

@app.post("/api/orchestrator/auto_pilot")
def orchestrator_auto_pilot(payload: dict, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    product_id = payload.get("product_id")
    if not product_id:
         raise HTTPException(status_code=400, detail="Missing product_id")
         
    import sqlite3
    from product_intelligence.campaign_builder import create_campaign_from_product
    
    conn = sqlite3.connect(str(DB_PATH))
    product = conn.execute("SELECT status FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product or product[0] != "READY":
        conn.close()
        raise HTTPException(status_code=400, detail="Questo prodotto non è ancora stato analizzato dall'IA. Vai nella tab 'Sell a Product', seleziona il prodotto e clicca 'Analyze Product / Market' prima di avviare l'Auto-Pilot.")

    rc = conn.execute("SELECT id FROM research_campaigns WHERE product_id = ? ORDER BY id DESC LIMIT 1", (product_id,)).fetchone()
    if not rc:
        rc_id = create_campaign_from_product(str(DB_PATH), product_id)
    else:
        rc_id = rc[0]
        
    if not rc_id:
        conn.close()
        raise HTTPException(status_code=400, detail="Could not create campaign for this product.")
        
    conn.execute("UPDATE research_campaigns SET status = 'RUNNING' WHERE id = ?", (rc_id,))
    conn.commit()
    conn.close()
    
    def run_auto_pilot(db_path_str: str, prod_id: int, camp_id: int):
        import subprocess
        from pathlib import Path
        from datetime import datetime, timezone
        from product_intelligence.agent import ProductIntelligenceAgent
        
        log_path = Path(db_path_str).parent / f"campaign_{camp_id}_osint.log"
        global_log = Path(db_path_str).parent / "system_logs.log"
        
        def write_log(msg):
            timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
            line = f"[{timestamp}] [Auto-Pilot {camp_id}] {msg}\n"
            with open(log_path, "a") as f: f.write(line)
            with open(global_log, "a") as f: f.write(line)
            
        write_log(f"--- ENGAGING AUTO-PILOT FOR CAMPAIGN {camp_id} ---")
        
        venv_python = ROOT / ".venv" / "bin" / "python"
        py_bin = str(venv_python) if venv_python.exists() else "python3"
        cmd = [py_bin, "-u", "public_osint_market_research.py", "--campaign-id", str(camp_id)]
        
        write_log("Running OSINT Discovery...")
        
        with open(log_path, "a") as log_file:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(ROOT), text=True)
            for line in iter(process.stdout.readline, ''):
                log_file.write(line)
                log_file.flush()
                with open(global_log, "a") as gf: gf.write(line)
            process.stdout.close()
            returncode = process.wait()
        
        write_log(f"OSINT Discovery completed with code {returncode}. Starting AI Evaluation...")
        
        write_log("OSINT Discovery completed. Evaluation is performed inline.")
        
        # 3. Auto-Approve (Confidence >= 75)
        import sqlite3
        conn2 = sqlite3.connect(db_path_str)
        conn2.execute("UPDATE prospect_product_fit SET evidence_reviewed_at=?, evidence_reviewed_by=? WHERE product_id=? AND fit_status='FIT' AND fit_score >= 75", (datetime.now(timezone.utc).isoformat(), "auto_pilot", prod_id))
        conn2.commit()
        
        # 4. Finish
        conn2.execute("UPDATE research_campaigns SET status = 'COMPLETED' WHERE id = ?", (camp_id,))
        conn2.commit()
        conn2.close()
        write_log("Auto-Pilot sequence complete.")
            
    background_tasks.add_task(run_auto_pilot, str(DB_PATH), product_id, rc_id)
    return {"success": True, "message": "Auto-Pilot started!", "campaign_id": rc_id}


# ==============================================================================
# P5.1: Product Endpoints
# ==============================================================================

from pydantic import BaseModel

class ProductCreateRequest(BaseModel):
    name: str

class ProductSourceRequest(BaseModel):
    source_type: str
    content: str

@app.post("/api/products")
def api_create_product(req: ProductCreateRequest, user: dict = Depends(get_current_user)):
    from product_intelligence.store import create_product
    return create_product(str(DB_PATH), req.name)

@app.get("/api/products")
def api_list_products(user: dict = Depends(get_current_user)):
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM products ORDER BY updated_at_utc DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/products/{id}")
def api_get_product(id: int, user: dict = Depends(get_current_user)):
    from product_intelligence.store import get_product
    p = get_product(str(DB_PATH), id)
    if not p:
        raise HTTPException(404, "Not found")
    return p

@app.post("/api/products/{id}/sources")
def api_add_product_source(id: int, req: ProductSourceRequest, user: dict = Depends(get_current_user)):
    from product_intelligence.store import add_source
    from product_intelligence.extractor import extract_from_text, extract_from_url
    
    if req.source_type == "URL":
        try:
            source_content = extract_from_url(req.content)
        except Exception as e:
            raise HTTPException(400, f"Could not extract content from URL: {str(e)}")
    else:
        source_content = extract_from_text(req.content, "Pasted Text")
        
    src = add_source(
        str(DB_PATH), 
        product_id=id,
        source_type=source_content.source_type.value,
        source_name=source_content.source_name,
        source_url=source_content.source_url,
        extracted_text=source_content.extracted_text,
        content_hash=source_content.content_hash,
        language=source_content.language
    )
    return {"success": True, "source_id": src["id"]}

@app.post("/api/products/{id}/sources/pdf")
async def api_add_product_pdf(id: int, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Upload one PDF source using the existing hardened PDF extractor."""
    from product_intelligence.store import get_product, add_source, list_sources
    from product_intelligence.extractor import extract_from_pdf, MAX_PDF_SOURCES

    product = get_product(str(DB_PATH), id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    existing_pdf_count = sum(
        1 for source in list_sources(str(DB_PATH), id)
        if str(source.get("source_type", "")).upper() == "PDF"
    )
    if existing_pdf_count >= MAX_PDF_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"PDF source limit reached ({MAX_PDF_SOURCES} per product)."
        )

    filename = Path(file.filename or "document.pdf").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    raw = await file.read()
    try:
        source_content = extract_from_pdf(raw, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    src = add_source(
        str(DB_PATH),
        product_id=id,
        source_type=source_content.source_type.value,
        source_name=source_content.source_name,
        source_url=source_content.source_url,
        extracted_text=source_content.extracted_text,
        content_hash=source_content.content_hash,
        language=source_content.language
    )
    return {
        "success": True,
        "source_id": src["id"],
        "filename": filename,
        "pages": source_content.metadata.get("pages", 0),
        "word_count": source_content.word_count,
        "char_count": source_content.char_count
    }


@app.get("/api/products/{id}/sources")
def api_get_product_sources(id: int, user: dict = Depends(get_current_user)):
    from product_intelligence.store import list_sources
    return list_sources(str(DB_PATH), id)

@app.post("/api/products/{id}/analyze")
def api_analyze_product(id: int, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    from product_intelligence.store import get_product, set_product_status
    p = get_product(str(DB_PATH), id)
    if not p:
        raise HTTPException(404, "Not found")
    
    set_product_status(str(DB_PATH), id, "ANALYZING")
    
    def run_analysis(db_path_str: str, prod_id: int):
        import logging
        from pathlib import Path
        from datetime import datetime, timezone
        from product_intelligence.provider import get_ai_provider
        from product_intelligence.agent import ProductIntelligenceAgent
        from product_intelligence.store import get_sources_with_text, save_product_analysis, set_product_status
        from product_intelligence.models import ProductSourceContent, SourceType
        
        log_path = Path(db_path_str).parent / f"product_{prod_id}_analysis.log"
        global_log_path = Path(db_path_str).parent / "system_logs.log"
        
        def write_log(msg):
            timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
            line = f"[{timestamp}] [Analysis Product {prod_id}] {msg}\n"
            with open(log_path, "a") as f: f.write(line)
            with open(global_log_path, "a") as f: f.write(line)
            
        write_log("--- INITIATING PRODUCT ANALYSIS ---")
        
        try:
            sources_dicts = get_sources_with_text(db_path_str, prod_id)
            if not sources_dicts:
                msg = "No sources provided."
                write_log(f"ERROR: {msg}")
                set_product_status(db_path_str, prod_id, "FAILED", msg)
                return
                
            sources = []
            write_log(f"Found {len(sources_dicts)} sources to extract.")
            
            for s in sources_dicts:
                st = s["source_type"].upper() if s["source_type"] else "TEXT"
                if st == "WEBSITE": st = "URL"
                try:
                    st_enum = SourceType(st)
                except ValueError:
                    st_enum = SourceType.TEXT
                    
                sources.append(ProductSourceContent(
                    source_type=st_enum,
                    source_name=s["source_name"] or "Unknown",
                    source_url=s["source_url"],
                    extracted_text=s["extracted_text"] or "",
                    content_hash=s["content_hash"] or ""
                ))
                write_log(f"Loaded source: {s['source_name']} (Type: {st})")
                
            write_log("Connecting to AI Provider...")
            provider = get_ai_provider(db_path_str)
            write_log(f"Provider selected: {provider.provider_name} ({provider.model_name})")
            
            agent = ProductIntelligenceAgent(provider)
            write_log("Synthesizing market intelligence and extracting features...")
            profile = agent.analyse(sources)
            
            write_log("Analysis successful! Saving profile...")
            save_product_analysis(db_path_str, prod_id, profile, provider.provider_name, provider.model_name)
            write_log("--- PRODUCT IS READY ---")
        except Exception as e:
            err_str = str(e)
            logging.error(f"Analysis failed: {err_str}")
            write_log(f"CRITICAL ERROR: {err_str}")
            set_product_status(db_path_str, prod_id, "FAILED", err_str)
            
    background_tasks.add_task(run_analysis, str(DB_PATH), id)
    return {"success": True, "status": "ANALYZING"}

@app.get("/api/system_logs")
def api_get_system_logs(user: dict = Depends(get_current_user)):
    from pathlib import Path
    log_path = DB_PATH.parent / "system_logs.log"
    if not log_path.exists():
        return {"logs": "System log is empty. Waiting for background tasks..."}
    with open(log_path, "r") as f:
        lines = f.readlines()
        return {"logs": "".join(lines[-200:])}

@app.get("/api/products/{id}/logs")
def api_get_product_logs(id: int, user: dict = Depends(get_current_user)):
    from pathlib import Path
    log_path = DB_PATH.parent / f"product_{id}_analysis.log"
    if not log_path.exists():
        raise HTTPException(404, "Log not found")
    with open(log_path, "r") as f:
        return {"logs": f.read()}

# END P5.1 ENDPOINTS

# ==============================================================================
# P5.3B: SALES CAMPAIGN & SEQUENCE ENDPOINTS
# ==============================================================================
from product_intelligence.sales_strategy_agent import SalesStrategyAgent, EmailSequenceAgent
from product_intelligence.sales_campaign_store import (
    upsert_strategy, upsert_product_campaign, save_sequence_messages,
    get_product_campaign, get_strategy_by_identity, list_product_campaigns
)
from pydantic import BaseModel
from typing import List, Optional

class StrategyGenerateRequest(BaseModel):
    product_id: int
    research_campaign_id: int
    market: str
    language: str
    target_segment: str
    buyer_role: str

class CampaignGenerateRequest(BaseModel):
    product_id: int
    research_campaign_id: int
    market: str
    language: str
    target_segment: str
    buyer_role: str
    sequence_length: int = 4

class SequenceMessageUpdate(BaseModel):
    id: Optional[int] = None
    sequence_order: int
    subject: str
    body: str
    delay_days: int

class UpdateMessagesRequest(BaseModel):
    messages: List[SequenceMessageUpdate]

@app.get("/api/research_campaigns/{id}/logs")
def api_get_campaign_logs(id: int, user: dict = Depends(get_current_user)):
    from pathlib import Path
    log_path = DB_PATH.parent / f"campaign_{id}_osint.log"
    if not log_path.exists():
        return {"logs": "Loading logs..."}
    with open(log_path, "r") as f:
        return {"logs": f.read()}

@app.get("/api/research_campaigns/{id}/contexts")
def get_research_campaign_contexts(id: int, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    camp = db.connection.execute("SELECT product_id, icp_id FROM research_campaigns WHERE id=?", (id,)).fetchone()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    icp = db.connection.execute("SELECT * FROM ideal_customer_profiles WHERE id=?", (camp["icp_id"],)).fetchone()
    if not icp:
        raise HTTPException(status_code=404, detail="ICP not found")
        
    def parse_list(val):
        if not val: return []
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return [x.strip() for x in val.split(',') if x.strip()]
            
    roles = parse_list(icp["roles"])
    industries = parse_list(icp["industries"])
    countries = parse_list(icp["countries"] if "countries" in icp.keys() else icp.get("locations", ""))
    languages = parse_list(icp["languages"])
    
    import itertools
    contexts = []
    
    # If any list is empty, we use a default list with one empty string element
    # so itertools.product still generates combinations
    _markets = countries if countries else ["Global"]
    _languages = languages if languages else ["English"]
    _segments = industries if industries else ["Any Segment"]
    _roles = roles if roles else ["Any Role"]
    
    for m, l, s, r in itertools.product(_markets, _languages, _segments, _roles):
        contexts.append({
            "market": m,
            "language": l,
            "target_segment": s,
            "buyer_role": r
        })
    
    return {
        "product_id": camp["product_id"],
        "contexts": contexts
    }

@app.post("/api/sales_strategy/generate")
def generate_sales_strategy(req: StrategyGenerateRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    
    # Validation 1: Product/RC consistency
    camp = db.connection.execute("SELECT product_id FROM research_campaigns WHERE id=?", (req.research_campaign_id,)).fetchone()
    if not camp:
        raise HTTPException(status_code=404, detail="Research Campaign not found")
    if camp["product_id"] != req.product_id:
        raise HTTPException(status_code=400, detail="Research Campaign does not belong to the given Product")
        
    # Get Product profile
    from product_intelligence.store import ProductIntelligenceStore
    pi_store = ProductIntelligenceStore()
    product = pi_store.get_product(str(DB_PATH), req.product_id)
    if not product or not product.get("profile"):
        raise HTTPException(status_code=400, detail="Product Profile not available")
        
    # Generate Strategy
    agent = SalesStrategyAgent(str(DB_PATH))
    strat = agent.generate(
        product_profile=product["profile"],
        market=req.market,
        language=req.language,
        target_segment=req.target_segment,
        buyer_role=req.buyer_role
    )
    
    if strat.get("status") == "FAILED":
        raise HTTPException(status_code=500, detail=strat.get("error", "Strategy generation failed"))
        
    # Inject identifiers and upsert
    strat["product_id"] = req.product_id
    strat["research_campaign_id"] = req.research_campaign_id
    sid = upsert_strategy(str(DB_PATH), strat)
    
    return {"success": True, "strategy_id": sid, "strategy": strat}

@app.get("/api/sales_strategy")
def get_sales_strategy(product_id: int, research_campaign_id: int, market: str, language: str, target_segment: str, buyer_role: str, user: dict = Depends(get_current_user)):
    strat = get_strategy_by_identity(str(DB_PATH), product_id, research_campaign_id, market, language, target_segment, buyer_role)
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strat

@app.get("/api/product_campaign_lookup")
def lookup_product_campaign(
    product_id: int,
    research_campaign_id: int,
    market: str,
    language: str,
    target_segment: str,
    buyer_role: str,
    user: dict = Depends(get_current_user)
):
    """Return the existing product campaign for an exact sales context, if any."""
    db = OutreachDatabase(DB_PATH)
    row = db.connection.execute("""
        SELECT id
        FROM product_campaigns
        WHERE product_id = ?
          AND research_campaign_id = ?
          AND market = ?
          AND language = ?
          AND target_segment = ?
          AND buyer_role = ?
        LIMIT 1
    """, (
        product_id,
        research_campaign_id,
        market,
        language,
        target_segment,
        buyer_role
    )).fetchone()
    return {"campaign_id": row["id"] if row else None}


@app.post("/api/product_campaigns/generate")
def generate_product_campaign(req: CampaignGenerateRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    
    # Validations
    camp = db.connection.execute("SELECT product_id FROM research_campaigns WHERE id=?", (req.research_campaign_id,)).fetchone()
    if not camp or camp["product_id"] != req.product_id:
        raise HTTPException(status_code=400, detail="Invalid Product / Research Campaign mismatch")
        
    strat = get_strategy_by_identity(str(DB_PATH), req.product_id, req.research_campaign_id, req.market, req.language, req.target_segment, req.buyer_role)
    if not strat:
        raise HTTPException(status_code=400, detail="Sales Strategy not found. Please generate it first.")
        
    from product_intelligence.store import ProductIntelligenceStore
    pi_store = ProductIntelligenceStore()
    product = pi_store.get_product(str(DB_PATH), req.product_id)
    
    # Save DRAFT campaign
    cid = upsert_product_campaign(str(DB_PATH), req.dict())
    
    # Generate Sequence
    agent = EmailSequenceAgent(str(DB_PATH))
    seq = agent.generate(strat, product["profile"], req.sequence_length)
    
    if seq.get("status") == "FAILED":
        # We allow re-generation on FAILED, so we don't abort, just bubble error
        raise HTTPException(status_code=500, detail=seq.get("error", "Sequence generation failed"))
        
    # Save Messages
    save_sequence_messages(str(DB_PATH), cid, seq["messages"])
    
    return {"success": True, "campaign_id": cid}

@app.get("/api/product_campaigns/{id}")
def get_product_campaign_by_id(id: int, user: dict = Depends(get_current_user)):
    camp = get_product_campaign(str(DB_PATH), id)
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return camp

@app.get("/api/product_campaigns")
def list_prod_campaigns(product_id: int = None, user: dict = Depends(get_current_user)):
    return list_product_campaigns(str(DB_PATH), product_id)

@app.put("/api/product_campaigns/{id}/messages")
def update_product_campaign_messages(id: int, req: UpdateMessagesRequest, user: dict = Depends(get_current_user)):
    camp = get_product_campaign(str(DB_PATH), id)
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp["status"] != "DRAFT":
        raise HTTPException(status_code=400, detail=f"Cannot edit messages because campaign is {camp['status']}")
        
    if len(req.messages) != camp["sequence_length"]:
        raise HTTPException(status_code=400, detail=f"Expected {camp['sequence_length']} messages, got {len(req.messages)}")
        
    for msg in req.messages:
        if not msg.subject.strip() or not msg.body.strip():
            raise HTTPException(status_code=400, detail="Subject and Body cannot be empty")
        
        # We could also validate placeholders here, but EmailSequenceAgent checks generation.
        # Strict user constraints say "placeholders validi". Let's do a basic check.
        import re
        placeholders = re.findall(r'\{\{([^}]+)\}\}', msg.body)
        allowed = {"first_name", "last_name", "company_name", "industry", "role", "matched_signal", "why_matched", "market"}
        for p in placeholders:
            if p not in allowed:
                raise HTTPException(status_code=400, detail=f"Invalid placeholder: {p}")
                
    save_sequence_messages(str(DB_PATH), id, [m.dict() for m in req.messages])
    return {"success": True}

@app.post("/api/product_campaigns/{id}/approve")
def approve_product_campaign(id: int, user: dict = Depends(get_current_user)):
    camp = get_product_campaign(str(DB_PATH), id)
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp["status"] != "DRAFT":
        raise HTTPException(status_code=400, detail=f"Campaign is already {camp['status']}")
        
    if not camp.get("strategy"):
        raise HTTPException(status_code=400, detail="Strategy is missing")
        
    msgs = camp.get("messages", [])
    if len(msgs) != camp["sequence_length"]:
        raise HTTPException(status_code=400, detail=f"Sequence length mismatch. Expected {camp['sequence_length']}, got {len(msgs)}")
        
    for msg in msgs:
        if not msg.get("subject", "").strip() or not msg.get("body", "").strip():
            raise HTTPException(status_code=400, detail="Found empty subject or body")
            
    db = OutreachDatabase(DB_PATH)
    db.connection.execute("UPDATE product_campaigns SET status='APPROVED', updated_at_utc=? WHERE id=?", (datetime.now(timezone.utc).isoformat(), id))
    db.connection.commit()
    
    return {"success": True, "status": "APPROVED"}




@app.post("/api/product_campaigns/{id}/export_to_outreach")
def export_product_campaign_to_outreach(id: int, payload: dict = None, user: dict = Depends(get_current_user)):
    """Export an approved product sequence into legacy Outreach campaigns/templates.

    One legacy campaign is created per sequence step so the existing sender remains
    fully compatible. Export never approves prospects and never sends email.
    Existing campaigns/templates with the same names are preserved.
    """
    camp = get_product_campaign(str(DB_PATH), id)
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp.get("status") not in {"APPROVED", "ACTIVE"}:
        raise HTTPException(status_code=400, detail="Only APPROVED or ACTIVE campaigns can be exported")

    messages = camp.get("messages") or []
    if len(messages) != camp.get("sequence_length"):
        raise HTTPException(
            status_code=400,
            detail=f"Sequence length mismatch. Expected {camp.get('sequence_length')}, got {len(messages)}"
        )

    db = OutreachDatabase(DB_PATH)
    created = []
    existing = []
    warnings = [
        "Each sequence step is exported as a separate legacy campaign/template.",
        "Export does not send email and does not modify prospect approval status."
    ]
    add_footer = True if payload is None else bool(payload.get("add_footer", True))

    for index, msg in enumerate(messages, start=1):
        step_name = f"{camp['name']} — Step {index}"
        template_name = f"{step_name}.txt"
        subject = (msg.get("subject") or "").strip()
        body = (msg.get("body") or "").strip()
        if not subject or not body:
            warnings.append(f"Step {index} skipped because subject or body is empty.")
            continue

        content = f"Subject: {subject}\n\n{body}"
        if add_footer:
            content += "\n\n---\nIf you prefer not to receive further messages, reply and let us know."

        template_row = db.connection.execute(
            "SELECT 1 FROM templates WHERE name = ? LIMIT 1",
            (template_name,)
        ).fetchone()
        campaign_row = db.connection.execute(
            "SELECT id FROM campaigns WHERE name = ? LIMIT 1",
            (step_name,)
        ).fetchone()

        if template_row or campaign_row:
            existing.append({
                "campaign": step_name,
                "template": template_name
            })
            continue

        now = datetime.now(timezone.utc).isoformat()
        db.connection.execute(
            "INSERT INTO templates (name, content, created_at_utc) VALUES (?, ?, ?)",
            (template_name, content, now)
        )
        db.connection.execute(
            "INSERT INTO campaigns (name, template, created_at_utc) VALUES (?, ?, ?)",
            (step_name, template_name, now)
        )
        created.append({
            "campaign": step_name,
            "template": template_name
        })

    db.connection.commit()
    return {
        "success": True,
        "created": created,
        "existing": existing,
        "warnings": warnings,
        "sent": False
    }


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(scheduler_loop())
