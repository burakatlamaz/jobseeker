from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RawExportRecord:
    url: str
    collected_at: str
    search_url: str
    run_id: int
    source: Optional[str] = None
    search_query: Optional[str] = None
    search_location: Optional[str] = None
    result_page_number: Optional[int] = None
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None


@dataclass
class MergedJobRecord:
    url: str
    first_seen_at: str
    last_seen_at: str
    run_ids: List[int] = field(default_factory=list)
    search_urls: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    search_queries: List[str] = field(default_factory=list)
    search_locations: List[str] = field(default_factory=list)
    result_page_numbers: List[int] = field(default_factory=list)
    title_hint: Optional[str] = None
    company_hint: Optional[str] = None
    location_hint: Optional[str] = None
    times_seen: int = 0
    simple_score: int = 0
    reasons: List[str] = field(default_factory=list)


@dataclass
class ParsedJobRecord:
    url: str
    source_job_url: str
    first_seen_at: str
    last_seen_at: str
    times_seen: int
    run_ids: List[int]
    search_urls: List[str]
    sources: List[str] = field(default_factory=list)
    search_queries: List[str] = field(default_factory=list)
    search_locations: List[str] = field(default_factory=list)

    title: Optional[str] = None
    company: Optional[str] = None
    location_raw: Optional[str] = None
    description_raw: Optional[str] = None
    requirements_raw: Optional[str] = None

    workplace_type_raw: Optional[str] = None
    employment_type_raw: Optional[str] = None
    job_insight_items: List[str] = field(default_factory=list)

    apply_url: Optional[str] = None
    apply_domain: Optional[str] = None
    duplicate_key: Optional[str] = None
    parse_source: Optional[str] = None
    parse_quality: str = "unknown"
    page_loaded: bool = False
    parse_success: bool = False
    parse_error: Optional[str] = None


@dataclass
class DiscoveredJobRecord:
    source: str
    source_name: str
    search_query: str
    search_location: str
    search_url: str
    result_page_url: str
    result_page_number: int
    job_url: str
    collected_at: str

    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    discovery_method: str = "search_result_page"
