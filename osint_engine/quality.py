import re
from typing import Dict, Any, Tuple
from .models import QuerySpec
import sqlite3
import db_connector
import json
import urllib.request
from typing import Dict, Any, Tuple
from .normalization import DISPOSABLE_DOMAINS
from email_hygiene import junk_reason

class LeadScorer:
    """Computes a multi-dimensional relevance score for a discovered lead without using AI/ML."""

    @staticmethod
    def calculate_score(email: str, confidence_type: str, page_title: str, context_text: str, role: str = "", industry: str = "", location: str = "") -> Tuple[int, Dict[str, int]]:
        contact_type_score = 0
        role_relevance_score = 0
        industry_relevance_score = 0
        location_relevance_score = 0

        email_lower = email.lower()
        title_lower = page_title.lower() if page_title else ""
        context_lower = context_text.lower() if context_text else ""
        
        # 1. Contact Type Score
        if confidence_type == "PERSONAL":
            contact_type_score = 40
        elif confidence_type == "ROLE_BASED":
            contact_type_score = 10
            # Small penalty if we're looking for a person but found a generic role
            if role:
                contact_type_score -= 10
        elif confidence_type == "PERSONAL_EMAIL_PROVIDER":
            contact_type_score = 20
        elif confidence_type == "SYSTEM":
            contact_type_score = -50
            
        # 2. Role Relevance
        if role:
            role_lower = role.lower()
            role_words = role_lower.split()
            
            # Check context/title for the role
            if role_lower in title_lower:
                role_relevance_score += 40
            elif any(w in title_lower for w in role_words if len(w) > 2):
                role_relevance_score += 15
                
            if role_lower in context_lower:
                role_relevance_score += 20
                
            # If the email local-part matches the role, it's slightly suspicious but could be cto@company.com
            local_part = email_lower.split('@')[0]
            if role_lower in local_part:
                # E.g. cto-support@ implies not the CTO.
                if "-" in local_part or "support" in local_part or "info" in local_part:
                    role_relevance_score -= 10
                else:
                    role_relevance_score += 10
                    
        # 3. Industry Relevance
        if industry:
            ind_lower = industry.lower()
            if ind_lower in title_lower:
                industry_relevance_score += 20
            if ind_lower in context_lower:
                industry_relevance_score += 10
                
        # 4. Location Relevance
        if location:
            loc_lower = location.lower()
            if loc_lower in title_lower:
                location_relevance_score += 10
            if loc_lower in context_lower:
                location_relevance_score += 10

        total_score = max(0, min(100, contact_type_score + role_relevance_score + industry_relevance_score + location_relevance_score))
        
        breakdown = {
            "contact_type_score": contact_type_score,
            "role_relevance_score": role_relevance_score,
            "industry_relevance_score": industry_relevance_score,
            "location_relevance_score": location_relevance_score
        }
        
        return total_score, breakdown

class AIExtractor:
    """Uses LLM to evaluate why a lead matches a campaign offer and ICP."""
    
    @staticmethod
    def generate_why_matched(db_path: str, campaign_id: int, lead_email: str, page_title: str, context_text: str) -> str:
        if not campaign_id:
            return ""
            
        try:
            conn = db_connector.get_connection(db_path)
            conn.row_factory = sqlite3.Row
            
            # Fetch AI settings
            rows = conn.execute("SELECT key, value FROM settings WHERE key IN ('ai_api_key', 'ai_base_url', 'ai_model')").fetchall()
            settings = {r["key"]: r["value"] for r in rows}
            
            api_key = settings.get("ai_api_key", "")
            base_url = settings.get("ai_base_url", "https://api.openai.com/v1").rstrip("/")
            model = settings.get("ai_model", "gpt-4o")
            
            if not api_key:
                conn.close()
                return "AI non configurata"
                
            # Fetch Campaign Context
            camp = conn.execute("SELECT offer_id, icp_id FROM research_campaigns WHERE id=?", (campaign_id,)).fetchone()
            if not camp:
                conn.close()
                return ""
                
            offer = conn.execute("SELECT name, description FROM sales_offers WHERE id=?", (camp["offer_id"],)).fetchone()
            icp = conn.execute("SELECT name, roles, industries FROM ideal_customer_profiles WHERE id=?", (camp["icp_id"],)).fetchone()
            conn.close()
            
            if not offer or not icp:
                return ""
                
            # Trim context aggressively
            safe_context = (context_text or "")[:1500]
            
            prompt = f"""Sei un AI assistant B2B. Valuta questo prospect e spiega PERCHÈ è un buon match per la nostra campagna.
Sii BREVISSIMO (max 15-20 parole). Lingua: Inglese.

La nostra Offerta: {offer['name']} - {offer['description']}
Il nostro Target (ICP): {icp['name']}
Prospect Email: {lead_email}
Sito web Titolo: {page_title}
Estratto del sito: {safe_context}

Rispondi SOLO con il motivo (es: "CTO at a SaaS company matching our WebAuthn security offer.")
"""
            
            url = f"{base_url}/chat/completions"
            data = json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a concise B2B lead qualifier."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 50
            }).encode("utf-8")
            
            request = urllib.request.Request(url, data=data, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            })
            
            with urllib.request.urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"].strip()
                
        except Exception as e:
            return f"Errore LLM: {str(e)[:50]}"

class EmailValidator:
    """Classifies email addresses into quality buckets (VALID, LIKELY_VALID, ROLE_BASED, LOW_CONFIDENCE, INVALID, SUPPRESSED) without SMTP pings."""
    
    @staticmethod
    def classify(email: str, confidence: float, confidence_type: str) -> str:
        if not email or "@" not in email:
            return "INVALID"
            
        local_part, domain = email.rsplit('@', 1)
        domain = domain.lower()
        
        # 1. Invalid checks
        if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email):
            return "INVALID"
            
        # 1b. Indirizzi strutturalmente inutilizzabili: chiavi Sentry, domini segnaposto/riservati, noreply...
        if junk_reason(email):
            return "INVALID"

        # 2. Suppressed / Disposable
        if domain in DISPOSABLE_DOMAINS:
            return "SUPPRESSED"
            
        # 3. Low Confidence (strict rule: even if role-based, low score is bad)
        if confidence < 0.60:
            return "LOW_CONFIDENCE"
            
        # 4. Role Based
        if confidence_type == "ROLE_BASED":
            return "ROLE_BASED"
            
        # 5. Valid / Likely Valid
        if confidence >= 0.90:
            return "VALID"
        else:
            return "LIKELY_VALID"
