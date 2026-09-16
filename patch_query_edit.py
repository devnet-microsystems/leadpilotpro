import re

with open('web_server.py', 'r') as f:
    content = f.read()

endpoint = """class UpdateCampaignQueryRequest(BaseModel):
    query: str

@app.put("/api/campaign_queries/{query_id}")
def update_campaign_query(query_id: int, req: UpdateCampaignQueryRequest, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    db.connection.execute("UPDATE campaign_queries SET query = ? WHERE id = ?", (req.query, query_id))
    db.connection.commit()
    return {"status": "success"}

@app.post("/api/campaigns/{campaign_id}/launch")
def launch_campaign(campaign_id: int, user: dict = Depends(get_current_user)):
    db = OutreachDatabase(DB_PATH)
    db.connection.execute("UPDATE research_campaigns SET status = 'RUNNING' WHERE id = ?", (campaign_id,))
    db.connection.commit()
    return {"status": "success"}
"""

if "UpdateCampaignQueryRequest" not in content:
    content = content.replace('class QueryRequest(BaseModel):', endpoint + '\nclass QueryRequest(BaseModel):')
    with open('web_server.py', 'w') as f:
        f.write(content)
