import os

content = """
# ==============================================================================
# P5.1: Product Endpoints
# ==============================================================================

from pydantic import BaseModel

class ProductCreateRequest(BaseModel):
    name: str

class ProductSourceRequest(BaseModel):
    url: str

@app.post("/api/products")
def api_create_product(req: ProductCreateRequest, user: dict = Depends(get_current_user)):
    from product_intelligence.store import create_product
    return create_product(str(DB_PATH), req.name)

@app.get("/api/products")
def api_list_products(user: dict = Depends(get_current_user)):
    import sqlite3
import db_connector
    conn = db_connector.get_connection(DB_PATH)
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
    from product_intelligence.store import add_product_source
    from product_intelligence.extractor import scrape_website
    
    content = scrape_website(req.url)
    if not content:
        raise HTTPException(400, "Could not extract content from URL")
    
    src = add_product_source(
        str(DB_PATH), 
        product_id=id,
        source_type="website",
        source_name=req.url,
        source_url=req.url,
        extracted_text=content
    )
    return {"success": True, "source_id": src}

@app.get("/api/products/{id}/sources")
def api_get_product_sources(id: int, user: dict = Depends(get_current_user)):
    from product_intelligence.store import get_product_sources
    return get_product_sources(str(DB_PATH), id)

@app.post("/api/products/{id}/analyze")
def api_analyze_product(id: int, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    from product_intelligence.store import get_product, update_product_status
    p = get_product(str(DB_PATH), id)
    if not p:
        raise HTTPException(404, "Not found")
    
    update_product_status(str(DB_PATH), id, "ANALYZING")
    
    def run_analysis(db_path, prod_id):
        from product_intelligence.agent import ProductIntelligenceAgent
        agent = ProductIntelligenceAgent(db_path)
        agent.analyze_product(prod_id)
        
    background_tasks.add_task(run_analysis, str(DB_PATH), id)
    return {"success": True, "status": "ANALYZING"}
"""

with open("web_server.py", "r") as f:
    orig = f.read()

if "# P5.1: Product Endpoints" not in orig:
    # Inject it before @app.on_event("startup")
    orig = orig.replace('@app.on_event("startup")', content + '\n\n@app.on_event("startup")')
    with open("web_server.py", "w") as f:
        f.write(orig)
    print("Injected P5.1 endpoints!")
else:
    print("Already injected.")
