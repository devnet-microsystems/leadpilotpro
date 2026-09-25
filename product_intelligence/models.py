"""
product_intelligence/models.py

Data models for the Product Intelligence system.
These are intentionally separate from the P1-P4 osint_engine models.
"""
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class ProductStatus(str, Enum):
    DRAFT = "DRAFT"
    INGESTING = "INGESTING"
    ANALYZING = "ANALYZING"
    READY = "READY"
    FAILED = "FAILED"


class SourceType(str, Enum):
    URL = "URL"
    PDF = "PDF"
    TEXT = "TEXT"


@dataclass
class ProductSourceContent:
    """
    Normalised in-memory representation of a source after extraction.
    This object is transient — it is created during ingestion and then
    persisted as a product_sources row.
    """
    source_type: SourceType
    source_name: str
    source_url: Optional[str]
    extracted_text: str
    content_hash: str
    language: Optional[str] = None
    word_count: int = 0
    char_count: int = 0
    metadata: dict = field(default_factory=dict)

    def is_empty(self) -> bool:
        return len(self.extracted_text.strip()) < 10
