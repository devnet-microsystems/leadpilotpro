"""
product_intelligence/provider.py

Abstract AI provider for structured generation.
Deliberately does NOT reference Gemini, OpenAI, Anthropic directly —
the concrete implementation reads config from the DB `settings` table.
"""
import json
import sqlite3
import db_connector
import urllib.request
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    """Abstract base — all AI providers must implement this interface."""

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 3000,
        temperature: float = 0.1,
    ) -> Optional[str]:
        """
        Returns the raw text response from the model, or None on failure.
        The caller is responsible for JSON parsing.
        """
        ...

    @property
    def last_error(self) -> Optional[str]:
        return getattr(self, "_last_error", None)

    @property
    def last_meta(self) -> dict:
        return getattr(self, "_last_meta", {})


class OpenAICompatibleProvider(AIProvider):
    """
    Concrete provider that calls any OpenAI-compatible REST endpoint
    (Gemini via /v1beta, OpenRouter, local LLMs, etc.).
    Configuration is read from the DB `settings` table at construction time.
    """

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._api_key: str = ""
        self._base_url: str = ""
        self._model: str = ""
        self._last_error: Optional[str] = None
        self._load_config()

    def _load_config(self) -> None:
        try:
            conn = db_connector.get_connection(self._db_path)
            rows = conn.execute(
                "SELECT key, value FROM settings WHERE key IN ('ai_api_key','ai_base_url','ai_model')"
            ).fetchall()
            conn.close()
            settings = {r[0]: r[1] for r in rows}
            self._api_key = settings.get("ai_api_key", "")
            self._base_url = settings.get("ai_base_url", "https://api.openai.com/v1").rstrip("/")
            self._model = settings.get("ai_model", "gpt-4o")
        except Exception as e:
            logger.warning("AIProvider: failed to load config from DB: %s", e)
            self._last_error = str(e)

        # Environment variable overrides — checked AFTER DB load.
        # DB value wins if it is non-empty and not the placeholder.
        # Priority: OPENROUTER_API_KEY → GEMINI_API_KEY → OPENAI_API_KEY → AI_API_KEY → DB value
        import os as _os
        env_key = (
            _os.environ.get("GROQ_API_KEY", "") or
            _os.environ.get("OPENROUTER_API_KEY", "") or
            _os.environ.get("GEMINI_API_KEY", "") or
            _os.environ.get("OPENAI_API_KEY", "") or
            _os.environ.get("AI_API_KEY", "")
        )
        if env_key and (not self._api_key or self._api_key in ("dummy_key", "placeholder", "")):
            self._api_key = env_key
            logger.debug("AIProvider: using API key from environment variable")

        env_url = _os.environ.get("AI_BASE_URL", "")
        if env_url and (not self._base_url or self._base_url == "https://api.openai.com/v1"):
            self._base_url = env_url.rstrip("/")

        env_model = _os.environ.get("AI_MODEL", "")
        if env_model and self._model in ("gpt-4o", "", "placeholder"):
            self._model = env_model


    @property
    def provider_name(self) -> str:
        # Derive a human-readable name from the base URL, keeping it provider-agnostic.
        if "googleapis" in self._base_url or "generativelanguage" in self._base_url:
            return "Google AI"
        if "openai.com" in self._base_url:
            return "OpenAI"
        if "openrouter" in self._base_url:
            return "OpenRouter"
        return "Custom AI"

    @property
    def model_name(self) -> str:
        return self._model

    def available(self) -> bool:
        return bool(self._api_key and self._base_url and self._model)

    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 3000,
        temperature: float = 0.1,
    ) -> Optional[str]:
        if not self.available():
            self._last_error = "AI provider not configured (missing api_key / base_url / model)"
            return None

        url = f"{self._base_url}/chat/completions"
        # If openrouter, we can specify response_format if the model supports it.
        # But we'll rely on the prompt to ask for JSON to ensure compatibility with all models.
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        # OpenRouter and Groq support response_format={"type": "json_object"} if we want JSON.
        if "openrouter" in self._base_url.lower() or "groq" in self._base_url.lower():
            payload["response_format"] = {"type": "json_object"}

        try:
            self._last_meta = {}
            data = json.dumps(payload).encode("utf-8")
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "User-Agent": "LeadPilot/1.0",
            }
            if "openrouter" in self._base_url.lower():
                headers["HTTP-Referer"] = "http://localhost:8000"
                headers["X-Title"] = "LeadPilot Pro"
            
            req = urllib.request.Request(
                url,
                data=data,
                headers=headers,
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                # Capture headers for rate limits
                for k, v in resp.headers.items():
                    kl = k.lower()
                    if "ratelimit" in kl or "retry" in kl:
                        self._last_meta[kl] = v
                
                result = json.loads(resp.read().decode("utf-8"))
                
                # Capture actual model used (important for openrouter/free)
                if "model" in result:
                    self._last_meta["actual_model"] = result["model"]
                    
                content = result["choices"][0]["message"].get("content")
                if content is None:
                    reasoning = result["choices"][0]["message"].get("reasoning")
                    if reasoning is not None:
                        content = reasoning
                    else:
                        self._last_error = f"Model returned empty content and reasoning: {result}"
                        return None
                        
                return content.strip()
        except Exception as e:
            self._last_error = str(e)
            
            # Try to parse HTTP errors to extract rate limit headers
            if hasattr(e, "headers"):
                for k, v in e.headers.items():
                    kl = k.lower()
                    if "ratelimit" in kl or "retry" in kl:
                        self._last_meta[kl] = v
                        
            logger.error("AIProvider.generate_structured failed: %s", e)
            return None

class MockAIProvider(AIProvider):
    def __init__(self):
        self._last_error = None
        self._last_meta = {}

    @property
    def provider_name(self) -> str:
        return "Mock Provider (Free)"

    @property
    def model_name(self) -> str:
        return "mock-model"

    def available(self) -> bool:
        return True

    def generate_structured(self, system_prompt: str, user_prompt: str, max_tokens: int = 3000, temperature: float = 0.1) -> Optional[str]:
        # Return a simple generic valid JSON for testing
        if "PRODUCT PROFILE:" in user_prompt and "PROSPECT EVIDENCE:" in user_prompt:
            # It's an evaluate_fit call
            return '''{
              "fit_status": "FIT",
              "fit_score": 85,
              "reason": "Mocked AI evaluation: the prospect seems like a good fit.",
              "matched_signals": ["Mocked positive signal"],
              "missing_signals": [],
              "negative_signals": [],
              "evidence_source_ids": []
            }'''
        else:
            # It's a product analysis call
            return '''{
              "product_name": "Mocked Product",
              "short_description": "A mocked description for testing without API costs.",
              "category": "Software",
              "subcategories": ["Testing"],
              "value_proposition": "Helps test the system for free.",
              "problems_solved": [{"value": "API costs", "confidence": 1.0, "kind": "FACT", "evidence_source_ids": []}],
              "key_features": [{"value": "Mock generation", "confidence": 1.0, "kind": "FACT", "evidence_source_ids": []}],
              "key_benefits": [{"value": "Save money", "confidence": 1.0, "kind": "FACT", "evidence_source_ids": []}],
              "target_company_types": [{"value": "Any", "confidence": 1.0, "kind": "FACT", "evidence_source_ids": []}],
              "target_industries": [{"value": "Any", "confidence": 1.0, "kind": "FACT", "evidence_source_ids": []}],
              "potential_buyer_roles": [{"value": "Tester", "confidence": 1.0, "kind": "FACT", "evidence_source_ids": []}],
              "competitors": [],
              "negative_keywords": ["paid"]
            }'''


def get_ai_provider(db_path: str) -> AIProvider:
    """Factory to return the appropriate AI provider based on settings."""
    return OpenAICompatibleProvider(db_path)
