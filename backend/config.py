from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

RAW_EXPORTS_DIR = DATA_DIR / "raw_exports"
MERGED_DIR = DATA_DIR / "merged"
PARSED_DIR = DATA_DIR / "parsed"
FILTERED_DIR = DATA_DIR / "filtered"
LOGS_DIR = DATA_DIR / "logs"
SEARCH_DIR = DATA_DIR / "search"
DISCOVERED_DIR = DATA_DIR / "discovered"
PARSED_EXPORTS_DIR = DATA_DIR / "parsed_exports"

MERGED_OUTPUT_FILE = MERGED_DIR / "merged_jobs.json"
MERGED_DEBUG_FILE = MERGED_DIR / "merged_jobs_debug.json"

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

DISCOVERED_JOBS_JSONL_OUTPUT_FILE = DISCOVERED_DIR / "discovered_jobs.jsonl"
DISCOVERY_DEBUG_OUTPUT_FILE = DISCOVERED_DIR / "discovery_debug.json"

PLAYWRIGHT_USER_DATA_DIR = BASE_DIR / "playwright_user_data"

DEFAULT_PARSE_LIMIT = None

USE_CHROME_CHANNEL = True
HEADLESS = False

PAGE_LOAD_TIMEOUT_MS = 30000
AFTER_LOAD_WAIT_MS = 2500
BETWEEN_JOBS_WAIT_MS = 1200
