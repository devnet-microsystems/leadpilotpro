import json

def generate_sales_campaigns_api_code():
    code = """
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
    
    return {
        "product_id": camp["product_id"],
        "markets": countries,
        "languages": languages,
        "target_segments": industries,
        "buyer_roles": roles
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

"""
    return code

with open("web_server.py", "r") as f:
    content = f.read()

anchor = "# END P5.1 ENDPOINTS"
if anchor in content:
    new_code = generate_sales_campaigns_api_code()
    content = content.replace(anchor, anchor + "\n" + new_code)
    with open("web_server.py", "w") as f:
        f.write(content)
    print("Injected P5.3B endpoints.")
else:
    print("Could not find anchor.")
