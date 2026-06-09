from dataclasses import asdict

from config import (
    RAW_EXPORTS_DIR,
    MERGED_DIR,
    PARSED_DIR,
    LOGS_DIR,
    MERGED_OUTPUT_FILE,
    PARSED_OUTPUT_FILE,
    PARSED_DEBUG_FILE,
    DEFAULT_PARSE_LIMIT,
)
from models import MergedJobRecord
from parse_jobs import parse_jobs
from utils import ensure_directories, read_json_file, write_json_file


def load_merged_jobs() -> list[MergedJobRecord]:
    rows = read_json_file(MERGED_OUTPUT_FILE)
    merged_jobs: list[MergedJobRecord] = []

    for row in rows:
        merged_jobs.append(
            MergedJobRecord(
                url=row["url"],
                first_seen_at=row["first_seen_at"],
                last_seen_at=row["last_seen_at"],
                run_ids=row.get("run_ids", []),
                search_urls=row.get("search_urls", []),
                sources=row.get("sources", []),
                search_queries=row.get("search_queries", []),
                search_locations=row.get("search_locations", []),
                result_page_numbers=row.get("result_page_numbers", []),
                title_hint=row.get("title_hint"),
                company_hint=row.get("company_hint"),
                location_hint=row.get("location_hint"),
                times_seen=row.get("times_seen", 0),
                simple_score=row.get("simple_score", 0),
                reasons=row.get("reasons", []),
            )
        )

    return merged_jobs


def main() -> None:
    ensure_directories([RAW_EXPORTS_DIR, MERGED_DIR, PARSED_DIR, LOGS_DIR])

    merged_jobs = load_merged_jobs()
    print(f"[INFO] Loaded {len(merged_jobs)} merged jobs")

    parsed_jobs = parse_jobs(merged_jobs, limit=DEFAULT_PARSE_LIMIT)

    output = [asdict(item) for item in parsed_jobs]

    write_json_file(PARSED_OUTPUT_FILE, output)
    write_json_file(
        PARSED_DEBUG_FILE,
        {
            "parsed_count": len(parsed_jobs),
            "successful_count": sum(1 for item in parsed_jobs if item.parse_success),
            "failed_count": sum(1 for item in parsed_jobs if not item.parse_success),
            "sample": output[:5],
        },
    )

    print(f"[INFO] Parsed jobs written to: {PARSED_OUTPUT_FILE}")
    print(f"[INFO] Parsed debug written to: {PARSED_DEBUG_FILE}")


if __name__ == "__main__":
    main()
