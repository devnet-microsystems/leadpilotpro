import json
import sqlite3
import db_connector
from pathlib import Path
from typing import List, Dict

class QueryGenerator:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        
    def generate_templates_for_campaign(self, campaign_id: int):
        """Populate query_templates table with default templates for a new campaign."""
        conn = db_connector.get_connection(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # Check if templates already exist
        existing = conn.execute("SELECT COUNT(*) FROM query_templates WHERE campaign_id=?", (campaign_id,)).fetchone()[0]
        if existing > 0:
            conn.close()
            return
            
        templates = [
            # PERSON_DISCOVERY
            ("PERSON_DISCOVERY", "\"{role}\" {industry} {location}"),
            ("PERSON_DISCOVERY", "{role} {industry} {location}"),
            ("PERSON_DISCOVERY", "\"Head of Engineering\" {industry} {location}"),
            ("PERSON_DISCOVERY", "\"VP Engineering\" {industry} {location}"),
            
            # COMPANY_DISCOVERY
            ("COMPANY_DISCOVERY", "{industry} companies {location}"),
            ("COMPANY_DISCOVERY", "{industry} startups {location}"),
            ("COMPANY_DISCOVERY", "B2B {industry} {location}"),
            ("COMPANY_DISCOVERY", "enterprise {industry} {location}"),
            
            # TARGET_PAGE_DISCOVERY
            ("TARGET_PAGE_DISCOVERY", "intitle:team {industry} {location}"),
            ("TARGET_PAGE_DISCOVERY", "inurl:leadership {industry} {location}"),
            ("TARGET_PAGE_DISCOVERY", "\"meet the team\" {industry} {location}"),
            ("TARGET_PAGE_DISCOVERY", "inurl:about {industry} {location}"),
            
            # GEOGRAPHIC_EXPANSION
            ("GEOGRAPHIC_EXPANSION", "{role} {industry} {country}")
        ]
        
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        
        for family, text in templates:
            # We store the raw template. The variables will be parsed from it.
            vars_used = []
            if "{role}" in text: vars_used.append("role")
            if "{industry}" in text: vars_used.append("industry")
            if "{location}" in text or "{country}" in text: vars_used.append("location") # Country/location mapping
            
            conn.execute(
                "INSERT INTO query_templates (campaign_id, family, template, variables, enabled, priority, base_score, created_at_utc) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (campaign_id, family, text, json.dumps(vars_used), 1, 0, 50.0, now)
            )
            
        conn.commit()
        conn.close()

    def get_concrete_queries(self, campaign_id: int) -> List[Dict]:
        """Returns a list of all expanded query strings ready for execution."""
        conn = db_connector.get_connection(self.db_path)
        conn.row_factory = sqlite3.Row
        
        camp = conn.execute("SELECT icp_id FROM research_campaigns WHERE id=?", (campaign_id,)).fetchone()
        if not camp: return []
        
        icp = conn.execute("SELECT * FROM ideal_customer_profiles WHERE id=?", (camp["icp_id"],)).fetchone()
        if not icp: return []
        
        def parse_list(val):
            if not val: return []
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return [x.strip() for x in val.split(',') if x.strip()]
                
        roles = parse_list(icp["roles"])
        industries = parse_list(icp["industries"])
        def get_col(row, col, default=""):
            return row[col] if col in row.keys() else default
            
        countries = parse_list(get_col(icp, "countries"))
        locations = parse_list(get_col(icp, "locations"))
        if not countries: countries = locations # Fallback for old schema
        
        templates = conn.execute("SELECT * FROM query_templates WHERE campaign_id=? AND enabled=1", (campaign_id,)).fetchall()
        
        results = []
        import itertools
        
        for t in templates:
            t_roles = roles if "{role}" in t["template"] else [""]
            t_ind = industries if "{industry}" in t["template"] else [""]
            
            # Combine country for location/country tags
            t_loc = countries if ("{location}" in t["template"] or "{country}" in t["template"]) else [""]
            
            combinations = list(itertools.product(t_roles, t_ind, t_loc))
            
            for r, i, l in combinations:
                q = t["template"]
                if r: q = q.replace("{role}", r)
                if i: q = q.replace("{industry}", i)
                if l: 
                    q = q.replace("{location}", l)
                    q = q.replace("{country}", l)
                    
                results.append({
                    "template_id": t["id"],
                    "family": t["family"],
                    "query": q.strip(),
                    "base_score": t["base_score"],
                    "target_key": f"{r}|{i}|{l}".upper()
                })
                
        conn.close()
        return results
