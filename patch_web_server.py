import sys

with open('web_server.py', 'r') as f:
    content = f.read()

new_endpoints = """
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
    
    q_rejected = "SELECT count(distinct p.id) FROM prospects p WHERE p.qualification_status = 'REJECTED' OR p.qualification_status = 'UNQUALIFIED'"
    rejected = db.connection.execute(q_rejected).fetchone()[0] or 0
    
    q_approved = "SELECT count(*) FROM product_campaigns WHERE product_id = ? AND status = 'APPROVED'"
    approved = db.connection.execute(q_approved, (product_id,)).fetchone()[0] or 0
    
    # Non esiste un vero "exported", controlliamo se ci sono export in base alle data, o a legacy
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
    
    from product_intelligence.product_fit_agent import ProductFitAgent
    agent = ProductFitAgent(str(DB_PATH))
    # Esegue sincrono per i test, ma andrebbe messo in background per grandi volumi
    res = agent.evaluate_all(batch_size=50)
    
    return {"success": True, "stats": res}

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

"""

if "# ==============================================================================\n\n@app.on_event" in content:
    content = content.replace("# ==============================================================================\n\n@app.on_event", new_endpoints + "\n\n@app.on_event")
    with open('web_server.py', 'w') as f:
        f.write(content)
    print("Patched successfully")
else:
    print("Could not find patch target")

