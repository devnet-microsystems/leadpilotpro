"""
product_intelligence/agent.py

ProductIntelligenceAgent — analyses one or more ProductSourceContent objects
and produces a structured, schema-conformant JSON profile of the product.

Rules:
 - FACT: information explicitly stated in the sources
 - INFERENCE: deduction by the agent (confidence < 1.0, evidence_source_ids)
 - UNKNOWN: value not determinable — never hallucinate
 - Conflicts between sources are recorded, NOT resolved by invention
"""
import json
import logging
import textwrap
from typing import List, Optional

from .models import ProductSourceContent
from .provider import AIProvider

logger = logging.getLogger(__name__)

# ── JSON schema (used both as prompt instruction and output validation) ──────

PRODUCT_PROFILE_SCHEMA_DESC = """
Return ONLY a valid JSON object matching EXACTLY this schema (no markdown, no fences):

{
  "product_name": "string | UNKNOWN",
  "short_description": "string | UNKNOWN",
  "category": "string | UNKNOWN",
  "subcategories": ["string"],
  "value_proposition": "string | UNKNOWN",
  "problems_solved": [
    { "value": "string", "confidence": 0.0-1.0, "kind": "FACT|INFERENCE", "evidence_source_ids": [int] }
  ],
  "key_features": [
    { "value": "string", "confidence": 0.0-1.0, "kind": "FACT|INFERENCE", "evidence_source_ids": [int] }
  ],
  "key_benefits": [
    { "value": "string", "confidence": 0.0-1.0, "kind": "FACT|INFERENCE", "evidence_source_ids": [int] }
  ],
  "target_company_types": [
    { "value": "string", "confidence": 0.0-1.0, "kind": "FACT|INFERENCE", "evidence_source_ids": [int] }
  ],
  "target_industries": [
    { "value": "string", "confidence": 0.0-1.0, "kind": "FACT|INFERENCE", "evidence_source_ids": [int] }
  ],
  "potential_buyer_roles": [
    { "value": "string", "confidence": 0.0-1.0, "kind": "FACT|INFERENCE", "evidence_source_ids": [int] }
  ],
  "use_cases": [
    { "value": "string", "confidence": 0.0-1.0, "kind": "FACT|INFERENCE", "evidence_source_ids": [int] }
  ],
  "keywords": ["string"],
  "negative_keywords": ["string"],
  "geographic_markets": [
    { "value": "string", "confidence": 0.0-1.0, "kind": "FACT|INFERENCE", "evidence_source_ids": [int] }
  ],
  "supported_languages": ["string"],
  "pricing_information": { "status": "UNKNOWN" } | { "status": "KNOWN", "summary": "string", "kind": "FACT|INFERENCE", "evidence_source_ids": [int] },
  "business_model": "string | UNKNOWN",
  "conflicts": [
    { "field": "string", "source_a_id": int, "source_b_id": int, "description": "string" }
  ],
  "analysis_confidence": 0.0-1.0,
  "analysis_notes": "string"
}

MANDATORY RULES:
1. Use UNKNOWN (not empty string, not null, not invented text) when data is absent.
2. FACT = explicitly present in the provided source text.
3. INFERENCE = reasonable deduction, must have confidence < 1.0.
4. evidence_source_ids refers to the 1-based index of the source in the source list provided.
5. Record conflicts — do not silently choose one version.
6. Do NOT invent company names, prices, features, or markets not evidenced by the source.
"""

SYSTEM_PROMPT = textwrap.dedent("""
    You are a Product Intelligence specialist for a B2B sales platform.
    Your task is to produce a precise, schema-conformant JSON product profile.
    You MUST distinguish between FACT (evidence in source text) and INFERENCE (your deduction).
    You MUST use the token UNKNOWN for missing information — never hallucinate.
    You MUST record conflicts between sources rather than silently resolving them.
    Output ONLY valid JSON. No preamble, no markdown code fences.
""").strip()


class ProductIntelligenceAgent:
    """
    Receives one or more ProductSourceContent objects, synthesises their text,
    and calls the configured AI provider to produce a structured product profile.
    """

    def __init__(self, provider: AIProvider):
        self._provider = provider

    def analyse(
        self,
        sources: List[ProductSourceContent],
        user_supplied_name: Optional[str] = None,
    ) -> dict:
        """
        Analyse sources and return the structured product profile as a dict.
        Raises RuntimeError if the provider is unavailable or returns unparseable JSON.
        """
        if not sources:
            raise ValueError("At least one source is required for analysis.")

        if not self._provider.available():
            raise RuntimeError(
                f"AI provider is not available: {self._provider.last_error}"
            )

        user_prompt = self._build_prompt(sources, user_supplied_name)

        raw = self._provider.generate_structured(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=3500,
            temperature=0.1,
        )

        if raw is None:
            raise RuntimeError(
                f"AI provider returned no response: {self._provider.last_error}"
            )

        return self._parse_and_validate(raw, sources)

    # ── Private helpers ─────────────────────────────────────────────────────

    def _build_prompt(
        self, sources: List[ProductSourceContent], user_name: Optional[str]
    ) -> str:
        parts = []

        if user_name:
            parts.append(f"The user says this product is called: \"{user_name}\".\n")

        parts.append(
            f"You have {len(sources)} source(s). "
            "Synthesise all of them to produce a single unified product profile.\n"
        )
        parts.append("Do NOT treat any source as the definitive final word — evaluate all.\n\n")

        for i, src in enumerate(sources, start=1):
            header = f"=== SOURCE {i}: [{src.source_type.value}] {src.source_name} ==="
            if src.source_url:
                header += f" ({src.source_url})"
            # Truncate very long sources to avoid prompt overflow
            text_snippet = src.extracted_text[:8000]
            if len(src.extracted_text) > 8000:
                text_snippet += "\n[... text truncated for analysis ...]"
            parts.append(f"{header}\n{text_snippet}\n")

        parts.append("\n" + PRODUCT_PROFILE_SCHEMA_DESC)
        parts.append("\nNow produce the JSON:")

        return "\n".join(parts)

    def _parse_and_validate(self, raw: str, sources: List[ProductSourceContent]) -> dict:
        """Parse JSON from model output, strip any accidental markdown fences."""
        raw = raw.strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        elif raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        try:
            profile = json.loads(raw)
        except json.JSONDecodeError as e:
            # Attempt to extract first {...} block
            import re as _re
            match = _re.search(r"\{.*\}", raw, _re.DOTALL)
            if match:
                try:
                    profile = json.loads(match.group())
                except json.JSONDecodeError:
                    raise RuntimeError(
                        f"AI response could not be parsed as JSON: {e}. "
                        f"Raw (first 500 chars): {raw[:500]}"
                    ) from e
            else:
                raise RuntimeError(
                    f"AI response could not be parsed as JSON: {e}. "
                    f"Raw (first 500 chars): {raw[:500]}"
                ) from e

        # Basic required-field presence check (non-exhaustive)
        required = ["product_name", "short_description", "key_features", "problems_solved"]
        missing = [k for k in required if k not in profile]
        if missing:
            logger.warning("Product profile missing keys: %s", missing)

        # Attach meta-information
        profile["_meta"] = {
            "source_count": len(sources),
            "provider": self._provider.provider_name,
            "model": self._provider.model_name,
        }

        return profile


# ── Lazy import to avoid circular deps at module load ────────────────────────
import re
