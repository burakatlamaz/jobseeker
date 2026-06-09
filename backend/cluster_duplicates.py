from collections import defaultdict
from urllib.parse import parse_qs, urlencode, urlparse

from config import (
    PARSED_DIR,
    PARSED_OUTPUT_FILE,
    JOB_CLUSTERS_OUTPUT_FILE,
    JOB_CLUSTERS_DEBUG_FILE,
)
from utils import ensure_directories, read_json_file, write_json_file


def normalize_apply_url(url: str | None) -> str | None:
    if not url:
        return None

    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if host.startswith("www."):
            host = host[4:]

        path = parsed.path.rstrip("/")
        query = parse_qs(parsed.query)
        stable_query = {}
        for key in ["jobId", "job_id", "gh_jid", "lever-origin", "source_id", "id", "jk"]:
            if query.get(key):
                stable_query[key] = query[key][0]

        suffix = f"?{urlencode(stable_query)}" if stable_query else ""
        return f"{host}{path}{suffix}" if host else None
    except Exception:
        return None


def source_domain(source: str | None) -> str | None:
    domains = {
        "linkedin": "linkedin.com",
        "indeed": "indeed.com",
        "stepstone": "stepstone.de",
        "xing": "xing.com",
        "arbeitsagentur": "arbeitsagentur.de",
        "stellenwerk": "stellenwerk.de",
    }
    return domains.get(source or "")


def is_valid_external_apply_key(apply_key: str | None, source: str | None) -> bool:
    if not apply_key:
        return False

    if "safety/go" in apply_key or "safety go" in apply_key:
        return False

    domain = source_domain(source)
    if domain and apply_key.startswith(domain):
        return False

    return True


def duplicate_key_is_usable(job: dict) -> bool:
    duplicate_key = job.get("duplicate_key")
    if not duplicate_key:
        return False

    if duplicate_key.startswith("content:"):
        return True

    if not duplicate_key.startswith("apply:"):
        return True

    source = source_name(job)
    domain = source_domain(source)
    if "safety go" in duplicate_key:
        return False

    if domain and duplicate_key.startswith(f"apply:{domain}:"):
        return False

    return True


def cluster_key(job: dict) -> str:
    duplicate_key = job.get("duplicate_key")
    if duplicate_key and duplicate_key_is_usable(job):
        return duplicate_key

    apply_key = normalize_apply_url(job.get("apply_url"))
    if is_valid_external_apply_key(apply_key, source_name(job)):
        return f"apply:{apply_key}"

    return f"url:{job.get('url')}"


def source_name(job: dict) -> str:
    sources = job.get("sources") or []
    if sources:
        return sources[0]
    return job.get("parse_source") or "unknown"


def select_best_apply_url(jobs: list[dict]) -> str | None:
    external_apply_urls = [
        job.get("apply_url")
        for job in jobs
        if job.get("apply_url") and job.get("apply_domain")
    ]
    if external_apply_urls:
        return external_apply_urls[0]

    for job in jobs:
        if job.get("apply_url"):
            return job.get("apply_url")

    return jobs[0].get("url") if jobs else None


def build_cluster(key: str, jobs: list[dict]) -> dict:
    sources = sorted({source_name(job) for job in jobs})
    source_urls = sorted({job.get("url") for job in jobs if job.get("url")})
    search_queries = sorted(
        {
            query
            for job in jobs
            for query in (job.get("search_queries") or [])
            if query
        }
    )
    search_locations = sorted(
        {
            location
            for job in jobs
            for location in (job.get("search_locations") or [])
            if location
        }
    )

    best = sorted(
        jobs,
        key=lambda item: (
            item.get("parse_success") is not True,
            item.get("parse_quality") != "source_container",
            -(len(item.get("description_raw") or "")),
        ),
    )[0]

    return {
        "cluster_key": key,
        "source_count": len(sources),
        "sources": sources,
        "source_urls": source_urls,
        "best_apply_url": select_best_apply_url(jobs),
        "title": best.get("title"),
        "company": best.get("company"),
        "location_raw": best.get("location_raw"),
        "duplicate_key": best.get("duplicate_key"),
        "search_queries": search_queries,
        "search_locations": search_locations,
        "parse_success": any(job.get("parse_success") for job in jobs),
        "parse_quality": best.get("parse_quality"),
        "jobs": jobs,
    }


def build_job_clusters(parsed_jobs: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)

    for job in parsed_jobs:
        grouped[cluster_key(job)].append(job)

    clusters = [build_cluster(key, jobs) for key, jobs in grouped.items()]
    clusters.sort(
        key=lambda item: (
            -item["source_count"],
            item.get("company") or "",
            item.get("title") or "",
        )
    )
    return clusters


def main() -> None:
    ensure_directories([PARSED_DIR])

    parsed_jobs = read_json_file(PARSED_OUTPUT_FILE)
    clusters = build_job_clusters(parsed_jobs)
    duplicate_clusters = [item for item in clusters if item["source_count"] > 1]

    write_json_file(JOB_CLUSTERS_OUTPUT_FILE, clusters)
    write_json_file(
        JOB_CLUSTERS_DEBUG_FILE,
        {
            "parsed_input_count": len(parsed_jobs),
            "cluster_count": len(clusters),
            "duplicate_cluster_count": len(duplicate_clusters),
            "duplicate_samples": duplicate_clusters[:10],
            "sample": clusters[:10],
        },
    )

    print(f"[INFO] Parsed input count: {len(parsed_jobs)}")
    print(f"[INFO] Job cluster count: {len(clusters)}")
    print(f"[INFO] Duplicate cluster count: {len(duplicate_clusters)}")
    print(f"[INFO] Clusters written to: {JOB_CLUSTERS_OUTPUT_FILE}")
    print(f"[INFO] Debug written to: {JOB_CLUSTERS_DEBUG_FILE}")


if __name__ == "__main__":
    main()
