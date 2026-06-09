import argparse
from pathlib import Path
from urllib.parse import parse_qs, urlparse, unquote_plus

from config import (
    PARSED_DIR,
    PARSED_EXPORTS_DIR,
    PARSED_OUTPUT_FILE,
    PARSED_DEBUG_FILE,
)
from utils import ensure_directories, read_jsonl_file, write_json_file


def compact_line(line: str) -> str:
    return " ".join((line or "").strip().split())


def clean_lines(text: str | None) -> list[str]:
    if not text:
        return []

    skip_exact = {
        "home",
        "my network",
        "jobs",
        "messaging",
        "notifications",
        "me",
        "for business",
        "try premium for €0",
        "skip to search",
        "skip to main content",
        "skip to primary content",
        "skip to aside",
        "skip to footer",
        "apply",
        "save",
    }

    lines = [compact_line(line) for line in text.splitlines()]
    return [line for line in lines if line and line.lower() not in skip_exact]


def trim_description(text: str | None) -> str | None:
    if not text:
        return text

    start_markers = [
        "About the job",
        "Stellenbeschreibung",
        "Unternehmensbeschreibung",
        "Deine Aufgaben",
        "Ihre Aufgaben",
        "Tasks",
        "Aufgaben",
    ]
    stop_markers = [
        "People also viewed",
        "Jobs you may like",
        "Similar jobs",
        "Recommended for you",
        "Browse jobs",
        "Ähnliche Jobs",
        "Weitere Jobs",
    ]

    trimmed = text
    for marker in start_markers:
        index = trimmed.find(marker)
        if index >= 0:
            trimmed = trimmed[index:]
            break

    cut_points = [trimmed.find(marker) for marker in stop_markers if trimmed.find(marker) > 0]
    if cut_points:
        trimmed = trimmed[: min(cut_points)]

    return trimmed.strip() or text


def infer_workplace_and_employment(text: str | None) -> tuple[str | None, str | None]:
    first_chunk = " ".join(clean_lines(text)[:45]).lower()

    workplace = None
    employment = None

    if "remote" in first_chunk:
        workplace = "remote"
    elif "hybrid" in first_chunk:
        workplace = "hybrid"
    elif "on-site" in first_chunk or "onsite" in first_chunk or "vor ort" in first_chunk:
        workplace = "on-site"

    if "part-time" in first_chunk or "teilzeit" in first_chunk:
        employment = "part-time"
    elif "full-time" in first_chunk or "vollzeit" in first_chunk:
        employment = "full-time"
    elif "internship" in first_chunk or "praktikum" in first_chunk:
        employment = "internship"

    return workplace, employment


def repair_linkedin_fields(row: dict) -> dict:
    if (row.get("source") or row.get("parse_source")) != "linkedin":
        return row

    description = row.get("description_raw") or ""
    lines = clean_lines(description)

    location_index = None
    for index, line in enumerate(lines):
        lower = line.lower()
        if (" ago" in lower or "reposted" in lower or "clicked apply" in lower) and "·" in line:
            location_index = index
            break

    if location_index is not None and location_index >= 2:
        row["company"] = row.get("company") or lines[location_index - 2]
        row["title"] = row.get("title") or lines[location_index - 1]
        row["location_raw"] = row.get("location_raw") or lines[location_index]

    row["description_raw"] = trim_description(description)
    return row


def extract_search_keywords(row: dict) -> list[str]:
    keywords = []
    raw_queries = row.get("search_queries") or []
    if row.get("searchQuery"):
        raw_queries.append(row.get("searchQuery"))

    for query in raw_queries:
        normalized = compact_line(query)
        if normalized and normalized not in keywords:
            keywords.append(normalized)

    search_urls = row.get("search_urls") or []
    if row.get("searchUrl"):
        search_urls.append(row.get("searchUrl"))

    for url in search_urls:
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            for key in ("keywords", "q", "what", "was"):
                for value in params.get(key, []):
                    decoded = unquote_plus(value).strip()
                    if decoded and decoded not in keywords:
                        keywords.append(decoded)
        except Exception:
            continue

    return keywords


def find_input_file(explicit_path: str | None) -> Path:
    if explicit_path:
        path = Path(explicit_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(path)
        return path

    candidates = sorted(
        list(PARSED_EXPORTS_DIR.glob("*.jsonl"))
        + list(PARSED_EXPORTS_DIR.glob("*.ndjson"))
    )
    if not candidates:
        raise FileNotFoundError(f"No parsed export files found in {PARSED_EXPORTS_DIR}")

    return candidates[-1]


def normalize_row(row: dict) -> dict:
    row = repair_linkedin_fields(dict(row))
    source_job_url = row.get("source_job_url") or row.get("url")
    source = row.get("source") or row.get("parse_source")
    workplace_type, employment_type = infer_workplace_and_employment(row.get("description_raw"))

    normalized = {
        "url": row.get("url") or source_job_url,
        "source_job_url": source_job_url,
        "sources": row.get("sources") or ([source] if source else []),
        "search_keywords": extract_search_keywords(row),
        "title": row.get("title"),
        "company": row.get("company"),
        "location_raw": row.get("location_raw") or row.get("location"),
        "description_raw": trim_description(row.get("description_raw")),
        "workplace_type_raw": row.get("workplace_type_raw") or workplace_type,
        "employment_type_raw": row.get("employment_type_raw") or employment_type,
        "apply_url": row.get("apply_url"),
    }

    return normalized


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="Parsed extension export .jsonl/.ndjson path")
    args = parser.parse_args()

    ensure_directories([PARSED_EXPORTS_DIR, PARSED_DIR])

    input_file = find_input_file(args.input)
    rows = read_jsonl_file(input_file)
    normalized = [normalize_row(row) for row in rows]
    successful_count = sum(1 for row in rows if row.get("parse_success"))
    failed_count = len(rows) - successful_count

    write_json_file(PARSED_OUTPUT_FILE, normalized)
    write_json_file(
        PARSED_DEBUG_FILE,
        {
            "input_file": str(input_file),
            "parsed_count": len(normalized),
            "successful_count": successful_count,
            "failed_count": failed_count,
            "sample": normalized[:5],
        },
    )

    print(f"[INFO] Imported parsed export: {input_file}")
    print(f"[INFO] Parsed rows: {len(normalized)}")
    print(f"[INFO] Successful rows: {successful_count}")
    print(f"[INFO] Failed rows: {failed_count}")
    print(f"[INFO] Output written to: {PARSED_OUTPUT_FILE}")


if __name__ == "__main__":
    main()
