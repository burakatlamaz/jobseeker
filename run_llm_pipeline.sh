#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ -f ".env.local" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env.local"
  set +a
fi

if [[ "${1:-}" =~ ^[0-9]+$ ]]; then
  export LLM_LIMIT="$1"
elif [[ "${1:-}" == "all" ]]; then
  unset LLM_LIMIT
fi

if [[ -z "${DEEPSEEK_API_KEY:-${LLM_API_KEY:-}}" ]]; then
  echo "Missing DEEPSEEK_API_KEY or LLM_API_KEY."
  echo "Create .env.local from .env.local.example and put your key there."
  exit 1
fi

export LLM_MODEL="${LLM_MODEL:-deepseek-v4-pro}"
export LLM_BASE_URL="${LLM_BASE_URL:-https://api.deepseek.com}"
export LLM_THINKING="${LLM_THINKING:-disabled}"
export PYTHONUNBUFFERED=1

echo "Model: $LLM_MODEL"
echo "Base URL: $LLM_BASE_URL"
echo "Limit: ${LLM_LIMIT:-all}"
echo "Thinking: $LLM_THINKING"
echo

PYTHONPATH=backend python3 backend/filter_main.py
PYTHONPATH=backend python3 backend/prepare_llm_candidates.py
PYTHONPATH=backend python3 backend/llm_match_jobs.py
PYTHONPATH=backend python3 backend/export_llm_excel.py

echo
echo "Done."
if [[ -n "${JOB_RUN_LABEL:-}" ]]; then
  echo "Excel: backend/data/filtered/job_applications_${JOB_RUN_LABEL}.xlsx"
else
  echo "Excel: backend/data/filtered/job_applications.xlsx"
fi
