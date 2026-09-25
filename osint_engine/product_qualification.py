import json
import sqlite3
import datetime
from typing import Dict, Any, Tuple
from product_intelligence.provider import get_ai_provider

class ProductQualificationAgent:
    """
    Evaluates whether an OSINT-discovered prospect matches a specific Product Profile.
    Returns structured output indicating FIT, NO_FIT, or REVIEW_REQUIRED.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.provider = get_ai_provider(db_path)
        
    def evaluate(self, product_profile: Dict[str, Any], prospect: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates the prospect against the product profile.
        Returns a dict matching the structured schema.
        """
        system_prompt = (
            "You are an expert B2B Sales Qualification Agent.\n"
            "Your job is to read a Product Profile and a Prospect's evidence, and determine if the Prospect is a good fit for the Product.\n"
            "Rules:\n"
            "1. You MUST distinguish between FACT (explicit in evidence) and INFERENCE (deduced).\n"
            "2. If you cannot find sufficient evidence to prove FIT or NO_FIT, you must return REVIEW_REQUIRED.\n"
            "3. If evidence contradicts the product's negative_keywords, return NO_FIT or REVIEW_REQUIRED.\n"
            "4. You must output exactly valid JSON matching this schema:\n"
            "{\n"
            "  \"fit_status\": \"FIT|NO_FIT|REVIEW_REQUIRED\",\n"
            "  \"fit_score\": <integer 0-100>,\n"
            "  \"reason\": \"<string explaining why, distinguishing facts from inference>\",\n"
            "  \"matched_signals\": [\"<string of matched product signal>\"],\n"
            "  \"missing_signals\": [\"<string of missing product signal>\"],\n"
            "  \"negative_signals\": [\"<string of contradictory signal>\"],\n"
            "  \"evidence_source_ids\": [\"<string identifying the source>\", ...]\n"
            "}\n"
            "If evidence is empty or missing, you must return REVIEW_REQUIRED."
        )
        
        user_prompt = f"""
PRODUCT PROFILE:
{json.dumps(product_profile, indent=2)}

PROSPECT EVIDENCE:
{json.dumps(prospect, indent=2)}
"""

        try:
            print(f"DEBUG: provider.available() = {self.provider.available()}")
            print(f"DEBUG: api_key={'set' if getattr(self.provider, '_api_key', '') else 'empty'}, base_url={getattr(self.provider, '_base_url', '')}, model={getattr(self.provider, '_model', '')}")
            # We enforce JSON structure using the provider's capabilities.
            # Assuming provider has a way to enforce JSON (already handled in get_ai_provider for some, or just via prompt).
            response_text = self.provider.generate_structured(system_prompt, user_prompt)
            if response_text is None:
                raise ValueError(self.provider.last_error or "generate_structured returned None")
            
            # Extract JSON from markdown if necessary
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].strip()
            else:
                json_str = response_text.strip()
                
            result = json.loads(json_str)
            
            # Validate output
            if "fit_status" not in result or result["fit_status"] not in ["FIT", "NO_FIT", "REVIEW_REQUIRED"]:
                result["fit_status"] = "REVIEW_REQUIRED"
            if not result.get("evidence_source_ids"):
                result["fit_status"] = "REVIEW_REQUIRED"
                
            return result
        except Exception as e:
            # FAIL-SAFE: If provider fails or output is unparseable
            return {
                "fit_status": "REVIEW_REQUIRED",
                "fit_score": 0,
                "reason": f"Provider or parsing failure: {str(e)}",
                "matched_signals": [],
                "missing_signals": [],
                "negative_signals": [],
                "evidence_source_ids": []
            }
