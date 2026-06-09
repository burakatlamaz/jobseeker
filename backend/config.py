from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

PARSED_DIR = DATA_DIR / "parsed"
FILTERED_DIR = DATA_DIR / "filtered"
SEARCH_DIR = DATA_DIR / "search"
PARSED_EXPORTS_DIR = DATA_DIR / "parsed_exports"

PARSED_OUTPUT_FILE = PARSED_DIR / "parsed_jobs.json"
PARSED_DEBUG_FILE = PARSED_DIR / "parsed_jobs_debug.json"
JOB_CLUSTERS_OUTPUT_FILE = PARSED_DIR / "job_clusters.json"
JOB_CLUSTERS_DEBUG_FILE = PARSED_DIR / "job_clusters_debug.json"

CLASSIFIED_OUTPUT_FILE = FILTERED_DIR / "classified_jobs_full.json"
SHORTLIST_OUTPUT_FILE = FILTERED_DIR / "shortlist.json"
FILTER_DEBUG_FILE = FILTERED_DIR / "filter_debug.json"
LLM_CANDIDATES_JSONL_FILE = FILTERED_DIR / "llm_candidates.jsonl"
LLM_CANDIDATES_DEBUG_FILE = FILTERED_DIR / "llm_candidates_debug.json"
LLM_RESULTS_JSONL_FILE = FILTERED_DIR / "llm_results.jsonl"
LLM_RESULTS_DEBUG_FILE = FILTERED_DIR / "llm_results_debug.json"
FINAL_EXCEL_FILE = FILTERED_DIR / "job_applications.xlsx"
LLM_CACHE_DIR = DATA_DIR / "llm_cache"

SEARCH_URLS_OUTPUT_FILE = SEARCH_DIR / "search_urls.json"
SEARCH_URLS_JSONL_OUTPUT_FILE = SEARCH_DIR / "search_urls.jsonl"
