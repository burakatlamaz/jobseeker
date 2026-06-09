# Jobseeker Automation Pipeline

This project is a browser-extension plus Python backend pipeline for collecting job postings, normalizing them, applying deterministic hard filters, scoring the remaining jobs with an OpenAI-compatible LLM API, and exporting a prioritized Excel application list.

The repository is intentionally sanitized. It does not contain API keys, browser profiles, cookies, scraped job descriptions, application results, or private candidate data.

## Why I Built It

Job search across multiple portals is repetitive and noisy. I built this tool to turn manual searches into a repeatable pipeline:

1. Generate search URLs for multiple job portals and role groups.
2. Visit search pages in a browser extension and collect visible job links.
3. Export parsed job detail records from the extension.
4. Import and normalize the records in the backend.
5. Keep only the compact fields needed for filtering and LLM scoring.
6. Reject clear mismatches with rule-based filters.
7. Score realistic candidates with an LLM.
8. Export a compact Excel list sorted by LLM fit score.

## Main Features

- Multi-source search support for Indeed, StepStone, LinkedIn, Xing, Arbeitsagentur, and Stellenwerk.
- Round-robin queue generation to spread requests across sources and pages.
- Browser extension UI for importing queues, collecting URLs, parsing detail pages, and exporting JSONL records.
- Python backend for normalization, hard filtering, LLM scoring, and Excel export.
- Configurable search groups for working student roles, internships, HiWi roles, and thesis opportunities.
- OpenAI-compatible LLM integration, with DeepSeek defaults configurable through environment variables.
- Local-only cache for LLM results to avoid paying twice for the same job/profile pair.

## Architecture

```text
search_queries.yaml + private candidate profile
        |
        v
backend/build_search_urls.py
        |
        v
browser extension queue import
        |
        v
job URL collection + detail parsing
        |
        v
backend/import_extension_parsed.py
        |
        v
filter_main.py -> prepare_llm_candidates.py -> llm_match_jobs.py
        |
        v
export_llm_excel.py
        |
        v
prioritized Excel application queue
```

## Tech Stack

- Python 3
- JavaScript browser extension
- YAML configuration
- Rule-based hard filtering
- OpenAI-compatible chat completions API
- Excel export with `openpyxl`

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.local.example .env.local
cp backend/candidate_profile.example.yaml backend/candidate_profile.yaml
```

Then edit `.env.local` with your API key and edit `backend/candidate_profile.yaml` with private candidate details.

## Example Commands

Generate a queue of search URLs:

```bash
PYTHONPATH=backend python3 backend/build_search_urls.py \
  --query-group expanded_today \
  --sources indeed,stepstone,linkedin,xing \
  --max-pages 3 \
  --max-per-source 400 \
  --max-total 1600 \
  --output-suffix expanded_today
```

Import the latest parsed-details export from the extension:

```bash
PYTHONPATH=backend python3 backend/import_extension_parsed.py
```

Run a small LLM scoring pilot:

```bash
./run_llm_pipeline.sh 20
```

Run all prepared LLM candidates:

```bash
./run_llm_pipeline.sh all
```

## Privacy Notes

Generated folders such as `backend/data/`, browser profiles, parsed exports, LLM caches, and local `.env` files are ignored by Git. The candidate profile in this public repository is only an example schema. Real resumes, contact details, visa information, cookies, and job-result exports should stay local.
