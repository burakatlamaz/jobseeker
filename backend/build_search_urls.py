import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, quote_plus

import yaml


BASE_DIR = Path(__file__).resolve().parent
CANDIDATE_PROFILE_FILE = BASE_DIR / "candidate_profile.yaml"
SEARCH_QUERIES_FILE = BASE_DIR / "search_queries.yaml"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML object")

    return data


def normalize_space(value: str) -> str:
    return " ".join((value or "").split())


def slugify(value: str) -> str:
    cleaned = normalize_space(value).lower()
    cleaned = cleaned.replace("+", "plus").replace("&", "and")
    return "-".join(part for part in cleaned.split(" ") if part)


def get_role_labels(candidate_profile: dict, mode: str) -> list[str]:
    role_types = candidate_profile["target_search"]["role_types"]
    labels: list[str] = []

    for role_type in role_types:
        role_labels = role_type.get("labels") or []
        if not role_labels:
            continue

        if mode == "first_label":
            labels.append(role_labels[0])
        else:
            labels.extend(role_labels)

    return unique_preserve_order(labels)


def unique_preserve_order(values: list[str]) -> list[str]:
    seen = set()
    unique_values = []

    for value in values:
        normalized = normalize_space(str(value))
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        unique_values.append(normalized)

    return unique_values


def build_query_texts(
    candidate_profile: dict,
    search_config: dict,
    query_group: str | None = None,
) -> list[str]:
    query_config = search_config["query_generation"]
    if query_group:
        query_groups = query_config.get("query_groups") or {}
        if query_group not in query_groups:
            available = ", ".join(sorted(query_groups)) or "none"
            raise ValueError(f"Unknown query group '{query_group}'. Available groups: {available}")
        return unique_preserve_order(query_groups[query_group])

    explicit_queries = query_config.get("explicit_queries") or []
    if explicit_queries:
        return unique_preserve_order(explicit_queries)

    role_labels = get_role_labels(candidate_profile, query_config.get("role_label_mode", "all_labels"))
    focus_terms = unique_preserve_order(query_config.get("focus_terms", []))
    templates = query_config.get("templates", ["{role}", "{role} {focus}"])

    queries: list[str] = []
    for role in role_labels:
        if query_config.get("include_role_only_queries", True):
            queries.append(role)

        for focus in focus_terms:
            for template in templates:
                if "{focus}" not in template:
                    continue
                queries.append(template.format(role=role, focus=focus))

    return unique_preserve_order(queries)


def build_page_url(source_id: str, base_url: str, page_number: int) -> str:
    if page_number <= 1:
        return base_url

    separator = "&" if "?" in base_url else "?"

    if source_id == "indeed":
        return f"{base_url}{separator}start={(page_number - 1) * 10}"
    if source_id == "stepstone":
        return f"{base_url}{separator}page={page_number}"
    if source_id == "linkedin":
        return f"{base_url}{separator}start={(page_number - 1) * 25}"
    if source_id == "xing":
        return f"{base_url}{separator}page={page_number}"
    if source_id == "stellenwerk":
        return f"{base_url}{separator}pagination%5Bstart%5D={(page_number - 1) * 10}"

    return base_url


def build_template_context(query: str, location: str, defaults: dict, source_config: dict | None = None) -> dict:
    source_config = source_config or {}
    location_slug_overrides = source_config.get("location_slug_overrides", {})
    location_slug = location_slug_overrides.get(location, slugify(location))

    return {
        "query": query,
        "query_plus": quote_plus(query),
        "query_quote": quote(query),
        "query_slug": slugify(query),
        "location": location,
        "location_plus": quote_plus(location),
        "location_quote": quote(location),
        "location_slug": location_slug,
        "recent_days": defaults.get("recent_days", 14),
        "radius_km": defaults.get("radius_km", 30),
        "sort": defaults.get("sort", "date"),
    }


def build_search_urls(
    candidate_profile: dict,
    search_config: dict,
    query_group: str | None = None,
    source_filter: list[str] | None = None,
    location_filter: list[str] | None = None,
    use_profile_locations: bool = False,
    max_pages_override: int | None = None,
    max_urls_per_source_override: int | None = None,
    max_total_urls_override: int | None = None,
) -> list[dict]:
    query_config = search_config["query_generation"]
    active_locations = query_config.get("active_locations")
    if use_profile_locations:
        active_locations = None
    locations = unique_preserve_order(
        location_filter
        or active_locations
        or candidate_profile["target_search"]["primary_locations"]
    )
    queries = build_query_texts(candidate_profile, search_config, query_group=query_group)
    defaults = search_config.get("defaults", {})
    safety = search_config.get("run_safety", {})
    max_urls_per_source = int(max_urls_per_source_override or safety.get("max_urls_per_source", 300))
    max_total_urls = int(max_total_urls_override or safety.get("max_total_urls", 1500))
    default_max_pages = int(max_pages_override or safety.get("max_pages_per_search", 1))

    generated_at = datetime.now(timezone.utc).isoformat()
    records: list[dict] = []

    configured_sources = search_config["sources"]
    source_order = search_config.get("discovery", {}).get("source_order") or list(configured_sources.keys())
    ordered_source_ids = [
        source_id for source_id in source_order if source_id in configured_sources
    ] + [
        source_id for source_id in configured_sources if source_id not in source_order
    ]
    if source_filter:
        allowed_sources = set(source_filter)
        ordered_source_ids = [source_id for source_id in ordered_source_ids if source_id in allowed_sources]

    for source_id in ordered_source_ids:
        source_config = configured_sources[source_id]
        if not source_config.get("enabled", False):
            continue

        source_records: list[dict] = []
        template = source_config["url_template"]
        supported_locations = source_config.get("supported_locations")
        source_locations = [
            location for location in locations
            if not supported_locations or location in supported_locations
        ]
        source_queries = ["all"] if source_config.get("query_independent") else queries

        for query in source_queries:
            for location in source_locations:
                context = build_template_context(query, location, defaults, source_config=source_config)
                base_url = template.format(**context)
                max_pages = int(max_pages_override or source_config.get("max_pages_per_search", default_max_pages))

                for page_number in range(1, max_pages + 1):
                    source_records.append(
                        {
                            "source": source_id,
                            "source_name": source_config.get("display_name", source_id),
                            "query": query,
                            "location": location,
                            "pageNumber": page_number,
                            "url": build_page_url(source_id, base_url, page_number),
                            "generated_at": generated_at,
                            "queryGroup": query_group or "all",
                            "roundRobinKey": f"{query} | {location}",
                        }
                    )

        for record in interleave_by_field(source_records, "roundRobinKey")[:max_urls_per_source]:
            record.pop("roundRobinKey", None)
            if len(records) >= max_total_urls:
                break
            records.append(record)

        if len(records) >= max_total_urls:
            break

    return interleave_by_source(records, source_order)


def interleave_by_field(records: list[dict], field: str) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    field_order: list[str] = []
    for record in records:
        key = str(record.get(field) or "")
        if key not in buckets:
            buckets[key] = []
            field_order.append(key)
        buckets[key].append(record)

    interleaved: list[dict] = []
    while any(buckets.get(key) for key in field_order):
        for key in field_order:
            bucket = buckets.get(key) or []
            if bucket:
                interleaved.append(bucket.pop(0))

    return interleaved


def interleave_by_source(records: list[dict], source_order: list[str]) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    for record in records:
        buckets.setdefault(record["source"], []).append(record)

    ordered_sources = [
        source for source in source_order if source in buckets
    ] + [
        source for source in buckets if source not in source_order
    ]

    interleaved: list[dict] = []
    while any(buckets.get(source) for source in ordered_sources):
        for source in ordered_sources:
            bucket = buckets.get(source) or []
            if bucket:
                interleaved.append(bucket.pop(0))

    return interleaved


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def with_group_suffix(path: Path, output_suffix: str | None) -> Path:
    if not output_suffix:
        return path
    return path.with_name(f"{path.stem}_{slugify(output_suffix)}{path.suffix}")


def write_outputs(search_config: dict, records: list[dict], output_suffix: str | None = None) -> tuple[Path, Path]:
    output_config = search_config["run_safety"]["write_outputs"]
    json_path = with_group_suffix(BASE_DIR / output_config["json"], output_suffix)
    jsonl_path = with_group_suffix(BASE_DIR / output_config["jsonl"], output_suffix)

    json_path.parent.mkdir(parents=True, exist_ok=True)

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False, indent=2)

    write_jsonl(jsonl_path, records)
    return json_path, jsonl_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build job-search URLs from YAML configuration.")
    parser.add_argument("--dry-run", action="store_true", help="Print counts without writing output files.")
    parser.add_argument("--sample", type=int, default=10, help="Number of sample URLs to print.")
    parser.add_argument(
        "--query-group",
        choices=["working_student", "internship", "hiwi", "thesis", "expanded_today"],
        help="Generate URLs only for one query group and write group-specific output files.",
    )
    parser.add_argument(
        "--sources",
        help="Comma-separated source ids to include, e.g. indeed,stepstone,linkedin,xing.",
    )
    parser.add_argument(
        "--profile-locations",
        action="store_true",
        help="Use candidate_profile.yaml target_search.primary_locations instead of search_queries.yaml active_locations.",
    )
    parser.add_argument(
        "--locations",
        help="Pipe-separated explicit locations, e.g. 'Darmstadt|Frankfurt am Main|Deutschland'.",
    )
    parser.add_argument("--max-pages", type=int, help="Override max pages per search.")
    parser.add_argument("--max-per-source", type=int, help="Override max URLs per source.")
    parser.add_argument("--max-total", type=int, help="Override max total search URLs.")
    parser.add_argument(
        "--output-suffix",
        help="Suffix for output files, e.g. expanded_today -> search_urls_expanded_today.json.",
    )
    args = parser.parse_args()

    candidate_profile = load_yaml(CANDIDATE_PROFILE_FILE)
    search_config = load_yaml(SEARCH_QUERIES_FILE)
    source_filter = None
    if args.sources:
        source_filter = [
            source.strip()
            for source in args.sources.split(",")
            if source.strip()
        ]
    location_filter = None
    if args.locations:
        location_filter = [
            location.strip()
            for location in args.locations.split("|")
            if location.strip()
        ]
    records = build_search_urls(
        candidate_profile,
        search_config,
        query_group=args.query_group,
        source_filter=source_filter,
        location_filter=location_filter,
        use_profile_locations=args.profile_locations,
        max_pages_override=args.max_pages,
        max_urls_per_source_override=args.max_per_source,
        max_total_urls_override=args.max_total,
    )

    counts_by_source: dict[str, int] = {}
    for record in records:
        counts_by_source[record["source"]] = counts_by_source.get(record["source"], 0) + 1

    print(f"[INFO] Generated {len(records)} search URLs")
    for source, count in sorted(counts_by_source.items()):
        print(f"[INFO] {source}: {count}")

    for record in records[: args.sample]:
        print(f"[SAMPLE] {record['source']} | {record['query']} | {record['location']} | {record['url']}")

    if args.dry_run:
        return

    output_suffix = args.output_suffix or args.query_group
    json_path, jsonl_path = write_outputs(search_config, records, output_suffix=output_suffix)
    print(f"[INFO] Wrote JSON: {json_path}")
    print(f"[INFO] Wrote JSONL: {jsonl_path}")


if __name__ == "__main__":
    main()
