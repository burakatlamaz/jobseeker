import hashlib
import json
import os
import time
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError

from config import (
    BASE_DIR,
    FILTERED_DIR,
    LLM_CACHE_DIR,
    LLM_CANDIDATES_JSONL_FILE,
    LLM_RESULTS_JSONL_FILE,
    LLM_RESULTS_DEBUG_FILE,
)
from utils import ensure_directories, read_jsonl_file, write_json_file


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-pro"
MAX_RETRIES = 3
LAST_ERROR_FILE = FILTERED_DIR / "last_llm_error.txt"


SYSTEM_PROMPT = """You are a pragmatic job-fit scorer for one candidate who urgently needs paid work.
Return only valid JSON with this exact schema:
{"score": 0-10, "category": "target|alternative|hard_reject", "reason": "max 160 chars", "fit_tags": ["max 5 short tags"]}

Decision rule:
- score 0 and category hard_reject only for clear blockers: mandatory German above A2, clearly unmet must-have requirements, unpaid/volunteer, not student-compatible, too senior, mostly embedded/low-level, impossible location.
- score 8-10 for strong software/data/AI/backend/ML/thesis/HiWi/student roles.
- score 5-7 for plausible paid roles that are not ideal but realistic.
- score 2-4 only for weak alternatives such as content, office, support, warehouse/minijob if paid, realistic, and the candidate appears to meet mandatory requirements.
- score 0 if the posting requires a different mandatory study field, certification, license, professional background, or experience that the candidate does not have.
- Regular full-time jobs are not target roles. If a full-time posting has no explicit student, internship, thesis, HiWi, part-time, freelance, or flexible-schedule signal, score 0 unless it is clearly realistic for the candidate.
- If a full-time/freelance/contract posting is flexible and paid but not a true student/internship/thesis/HiWi role, category must be alternative and score must be at most 6.
- Do not reject just because the domain is not ideal; use alternative with a low score if it can still be applied to.
- Do not invent facts.
"""


def load_candidate_profile() -> str:
    path = BASE_DIR / "candidate_profile.yaml"
    return path.read_text(encoding="utf-8")


def cache_key(model: str, candidate_profile: str, job: dict) -> str:
    payload = {
        "model": model,
        "candidate_profile": candidate_profile,
        "job": job,
        "prompt_version": 2,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def extract_json_object(text: str) -> dict:
    clean = (text or "").strip()
    if clean.startswith("```"):
        clean = clean.strip("`")
        clean = clean.removeprefix("json").strip()

    start = clean.find("{")
    end = clean.rfind("}")
    if start >= 0 and end >= start:
        clean = clean[start : end + 1]

    parsed = json.loads(clean)
    if not isinstance(parsed, dict):
        raise ValueError("LLM response is not a JSON object")

    score = parsed.get("score", 0)
    try:
        score = int(score)
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(10, score))

    category = str(parsed.get("category") or "").strip().lower()
    if category not in {"target", "alternative", "hard_reject"}:
        category = "hard_reject" if score == 0 else ("target" if score >= 7 else "alternative")

    return {
        "score": score,
        "category": category,
        "apply": score > 0 and category != "hard_reject",
        "reason": str(parsed.get("reason") or "")[:240],
        "fit_tags": [
            str(item)[:40]
            for item in (parsed.get("fit_tags") or [])
            if str(item).strip()
        ][:5],
    }


def build_user_prompt(candidate_profile: str, job: dict) -> str:
    return json.dumps(
        {
            "candidate_profile_yaml": candidate_profile,
            "job": job,
            "task": "Decide if this candidate should apply to this job.",
        },
        ensure_ascii=False,
    )


def call_openai_compatible(
    *,
    api_key: str,
    base_url: str,
    model: str,
    candidate_profile: str,
    job: dict,
) -> dict:
    endpoint = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(candidate_profile, job)},
        ],
        "temperature": 0.1,
        "max_tokens": int(os.environ.get("LLM_MAX_TOKENS", "320")),
        "thinking": {"type": os.environ.get("LLM_THINKING", "disabled")},
    }

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        endpoint,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=90) as response:
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        LAST_ERROR_FILE.write_text(f"HTTP {error.code}\n{error_body}", encoding="utf-8")
        raise RuntimeError(f"HTTP {error.code}: {error_body[:800]}") from error

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as error:
        LAST_ERROR_FILE.write_text(body, encoding="utf-8")
        raise ValueError(f"API returned non-JSON body: {body[:800]}") from error

    message = parsed["choices"][0]["message"]
    content = message.get("content") or ""
    reasoning_content = message.get("reasoning_content") or ""
    finish_reason = parsed["choices"][0].get("finish_reason")

    if not content.strip() and reasoning_content:
        LAST_ERROR_FILE.write_text(
            "Assistant content was empty while reasoning_content was present.\n"
            "This means DeepSeek thinking mode is still active or max_tokens was spent on reasoning.\n"
            "Expected request setting: thinking={\"type\":\"disabled\"}.\n\n"
            f"FINISH_REASON:\n{finish_reason}\n\n"
            f"REASONING_CONTENT:\n{reasoning_content}\n\n"
            f"BODY:\n{body}",
            encoding="utf-8",
        )
        raise ValueError(
            "Assistant content was empty; reasoning_content was present. "
            "DeepSeek thinking mode is still active or output tokens were spent on reasoning."
        )

    try:
        result = extract_json_object(content)
    except (json.JSONDecodeError, ValueError) as error:
        LAST_ERROR_FILE.write_text(
            "API JSON body was valid, but assistant content was not parseable JSON.\n\n"
            f"CONTENT:\n{content}\n\nBODY:\n{body}",
            encoding="utf-8",
        )
        raise ValueError(f"Assistant content was not parseable JSON: {content[:800]}") from error
    result["usage"] = parsed.get("usage") or {}
    return result


def evaluate_job(job: dict, candidate_profile: str, api_key: str, base_url: str, model: str) -> dict:
    key = cache_key(model, candidate_profile, job)
    cache_file = LLM_CACHE_DIR / f"{key}.json"

    if cache_file.exists():
      cached = json.loads(cache_file.read_text(encoding="utf-8"))
      return {**cached, "cache_hit": True}

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = call_openai_compatible(
                api_key=api_key,
                base_url=base_url,
                model=model,
                candidate_profile=candidate_profile,
                job=job,
            )
            result["cache_hit"] = False
            cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return result
        except (RuntimeError, URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError) as error:
            last_error = str(error)
            time.sleep(min(2**attempt, 10))

    return {
        "apply": None,
        "score": None,
        "category": "llm_error",
        "reason": f"llm_error: {last_error}",
        "fit_tags": [],
        "usage": {},
        "cache_hit": False,
        "error": last_error,
    }


def main() -> None:
    ensure_directories([FILTERED_DIR, LLM_CACHE_DIR])

    if LAST_ERROR_FILE.exists():
        LAST_ERROR_FILE.unlink()

    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        raise SystemExit("Set DEEPSEEK_API_KEY or LLM_API_KEY before running.")

    base_url = os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL)
    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL)
    limit = int(os.environ.get("LLM_LIMIT", "0") or "0")

    candidate_profile = load_candidate_profile()
    candidates = read_jsonl_file(LLM_CANDIDATES_JSONL_FILE)
    if limit > 0:
        candidates = candidates[:limit]

    results = []
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    with LLM_RESULTS_JSONL_FILE.open("w", encoding="utf-8") as output:
        for index, job in enumerate(candidates, start=1):
            print(f"[INFO] LLM match {index}/{len(candidates)}: {job.get('title')}", flush=True)
            llm = evaluate_job(job, candidate_profile, api_key, base_url, model)
            usage = llm.get("usage") or {}
            for key in total_usage:
                total_usage[key] += int(usage.get(key) or 0)

            row = {
                **job,
                "llm_model": model,
                "llm_apply": llm.get("apply"),
                "llm_score": llm.get("score"),
                "llm_category": llm.get("category") or "llm_error",
                "llm_reason": llm.get("reason"),
                "llm_fit_tags": llm.get("fit_tags") or [],
                "llm_cache_hit": bool(llm.get("cache_hit")),
                "llm_error": llm.get("error"),
                "llm_usage": usage,
            }
            results.append(row)
            output.write(json.dumps(row, ensure_ascii=False) + "\n")

    accepted = [row for row in results if row.get("llm_apply")]
    rejected = [row for row in results if not row.get("llm_apply")]

    write_json_file(
        LLM_RESULTS_DEBUG_FILE,
        {
            "model": model,
            "base_url": base_url,
            "candidate_count": len(candidates),
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "total_usage": total_usage,
            "accepted_sample": accepted[:10],
            "rejected_sample": rejected[:10],
        },
    )

    print(f"[INFO] Accepted by LLM: {len(accepted)}")
    print(f"[INFO] Rejected by LLM: {len(rejected)}")
    print(f"[INFO] Results written to: {LLM_RESULTS_JSONL_FILE}")
    print(f"[INFO] Debug written to: {LLM_RESULTS_DEBUG_FILE}")


if __name__ == "__main__":
    main()
