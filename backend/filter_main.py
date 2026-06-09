import classify_job
print("[DEBUG] classify_job file:", classify_job.__file__)
print("[DEBUG] classify_job version:", getattr(classify_job, "VERSION", "NO_VERSION"))

from utils import ensure_directories, read_json_file, write_json_file
from config import (
    RAW_EXPORTS_DIR,
    MERGED_DIR,
    PARSED_DIR,
    FILTERED_DIR,
    LOGS_DIR,
    PARSED_OUTPUT_FILE,
    CLASSIFIED_OUTPUT_FILE,
    SHORTLIST_OUTPUT_FILE,
    FILTER_DEBUG_FILE,
)
from classify_language import classify_language_requirement
from classify_job import (
    classify_employment,
    classify_workplace_and_location,
    build_compact_job_view,
)


def classify_single_job(job: dict) -> dict:
    title = job.get("title") or ""
    description = job.get("description_raw") or ""
    company = job.get("company") or ""
    search_urls = job.get("search_urls", []) or []
    employment_type_raw = job.get("employment_type_raw")
    workplace_type_raw = job.get("workplace_type_raw")
    location_raw = job.get("location_raw")

    unavailable_markers = [
        "diese seite konnte nicht gefunden werden",
        "page not found",
        "job no longer available",
        "stelle nicht gefunden",
    ]
    unavailable_text = f"{title} {description}".lower()
    if (not title and not company and not description) or any(
        marker in unavailable_text for marker in unavailable_markers
    ):
        compact = build_compact_job_view(job)
        return {
            **compact,
            "location_raw": job.get("location_raw"),
            "posting_language": "unknown",
            "english_environment_signal": False,
            "language_decision": "not_parsed",
            "language_reason": "page_unavailable_or_empty",
            "employment_decision": "not_parsed",
            "employment_reason": "page_unavailable_or_empty",
            "workplace_decision": "not_parsed",
            "workplace_reason": "page_unavailable_or_empty",
            "final_decision": "hard_reject",
            "reasons": ["page_unavailable_or_empty"],
        }

    language_result = classify_language_requirement(description)

    employment_result = classify_employment(
        description,
        title,
        employment_type_raw=employment_type_raw,
    )

    workplace_result = classify_workplace_and_location(
        description,
        title,
        company,
        location_raw=location_raw,
        workplace_type_raw=workplace_type_raw,
        search_urls=search_urls,
    )

    hard_reject_reasons = []
    if language_result["language_reject"]:
        hard_reject_reasons.append(language_result["language_decision"])
    if employment_result["employment_reject"]:
        hard_reject_reasons.append(employment_result["employment_decision"])
    if workplace_result["workplace_reject"]:
        hard_reject_reasons.append(workplace_result["workplace_decision"])

    final_decision = "hard_reject" if hard_reject_reasons else "llm_candidate"

    compact = build_compact_job_view(job)

    classified = {
        **compact,
        "location_raw": job.get("location_raw"),
        "posting_language": language_result["posting_language"],
        "english_environment_signal": language_result["english_environment_signal"],
        "language_decision": language_result["language_decision"],
        "language_reason": language_result["language_reason"],
        "employment_decision": employment_result["employment_decision"],
        "employment_reason": employment_result["employment_reason"],
        "workplace_decision": workplace_result["workplace_decision"],
        "workplace_reason": workplace_result["workplace_reason"],
        "final_decision": final_decision,
        "reasons": [
            value
            for value in [
                language_result["language_reason"],
                employment_result["employment_reason"],
                workplace_result["workplace_reason"],
            ]
            if value
        ],
    }

    return classified


def main() -> None:
    ensure_directories([RAW_EXPORTS_DIR, MERGED_DIR, PARSED_DIR, FILTERED_DIR, LOGS_DIR])

    parsed_jobs = read_json_file(PARSED_OUTPUT_FILE)
    classified_jobs = [classify_single_job(job) for job in parsed_jobs]

    shortlist = [job for job in classified_jobs if job["final_decision"] == "llm_candidate"]

    llm_candidates = [job for job in classified_jobs if job["final_decision"] == "llm_candidate"]
    hard_rejected = [job for job in classified_jobs if job["final_decision"] == "hard_reject"]

    write_json_file(CLASSIFIED_OUTPUT_FILE, classified_jobs)
    write_json_file(SHORTLIST_OUTPUT_FILE, shortlist)
    write_json_file(
        FILTER_DEBUG_FILE,
        {
            "parsed_input_count": len(parsed_jobs),
            "llm_candidate_count": len(llm_candidates),
            "hard_reject_count": len(hard_rejected),
            "llm_candidate_sample": llm_candidates[:5],
            "hard_reject_sample": hard_rejected[:5],
        },
    )

    print(f"[INFO] Parsed input count: {len(parsed_jobs)}")
    print(f"[INFO] LLM candidate count: {len(llm_candidates)}")
    print(f"[INFO] Hard reject count: {len(hard_rejected)}")
    print(f"[INFO] Classified output written to: {CLASSIFIED_OUTPUT_FILE}")
    print(f"[INFO] Shortlist written to: {SHORTLIST_OUTPUT_FILE}")
    print(f"[INFO] Filter debug written to: {FILTER_DEBUG_FILE}")


if __name__ == "__main__":
    main()
