from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional

class ProviderState(Enum):
    SUCCESS = auto()
    ZERO_RESULTS = auto()
    RATE_LIMITED = auto()
    BLOCKED = auto()
    ERROR = auto()
    DEGRADED = auto()
    OFF = auto()

@dataclass
class ProviderResult:
    status: ProviderState
    results: List['UnifiedSearchResult']
    error: str = ""
    http_status: Optional[int] = None
    latency_ms: int = 0
    retry_after: Optional[int] = None

@dataclass(frozen=True)
class UnifiedSearchResult:
    title: str
    url: str
    domain: str
    snippet: str
    engine: str
    query: str
    rank: int = 0
    discovered_at: str = ""

@dataclass(frozen=True)
class DiscoveredLead:
    email: str
    domain: str
    source_url: str
    source_type: str
    engine: str
    confidence_type: str
    email_confidence: float
    query: str
    company_name: Optional[str] = None
    relevance_score: int = 0
    why_matched: str = ""

@dataclass(frozen=True)
class TargetContext:
    role: str
    industry: str
    location: str
    country: str
    
    @property
    def target_key(self) -> str:
        parts = [self.role, self.industry, self.location, self.country]
        clean_parts = [p.strip().upper() for p in parts if p and p.strip()]
        return "|".join(clean_parts) if clean_parts else "GENERIC"

@dataclass
class QuerySpec:
    text: str
    family: str
    round: int
    priority: float = 1.0
    template: str = ""
    provider_name: str = ""
    is_exploration: bool = False
    samples: int = 0
