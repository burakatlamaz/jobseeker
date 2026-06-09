import argparse
import json
import random
from collections import OrderedDict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

from config import (
    BASE_DIR,
    DISCOVERED_DIR,
    DISCOVERED_JOBS_JSONL_OUTPUT_FILE,
    DISCOVERY_DEBUG_OUTPUT_FILE,
    SEARCH_URLS_JSONL_OUTPUT_FILE,
)
from sources import get_adapter
from utils import ensure_directories, read_jsonl_file, write_json_file


SEARCH_QUERIES_FILE = BASE_DIR / "search_queries.yaml"
ANONYMOUS_PROFILE_DIR = BASE_DIR / "playwright_profiles" / "anonymous_discovery"


def load_search_config() -> dict:
    with SEARCH_QUERIES_FILE.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise ValueError(f"{SEARCH_QUERIES_FILE} must contain a YAML object")

    return data


def group_search_records(records: Iterable[dict]) -> OrderedDict[tuple[str, str], dict[str, dict]]:
    grouped: OrderedDict[tuple[str, str], dict[str, dict]] = OrderedDict()

    for record in records:
        key = (record["query"], record["location"])
        grouped.setdefault(key, {})
        grouped[key][record["source"]] = record

    return grouped


def build_round_robin_tasks(
    search_records: list[dict],
    search_config: dict,
    source_order: list[str],
    max_search_groups: int,
    max_pages_per_search: int,
    source_filter: str | None = None,
) -> list[dict]:
    query_independent_records = {
        (record["source"], record["location"]): record
        for record in search_records
        if record.get("query") == "all"
    }
    normal_records = [
        record for record in search_records
        if record.get("query") != "all"
    ]
    grouped = group_search_records(normal_records)
    used_query_independent_pages: set[tuple[str, str, int]] = set()
    tasks: list[dict] = []
    source_configs = search_config.get("sources", {})

    for group_index, ((query, location), records_by_source) in enumerate(grouped.items(), start=1):
        if group_index > max_search_groups:
            break

        for page_number in range(1, max_pages_per_search + 1):
            for source in source_order:
                source_max_pages = int(source_configs.get(source, {}).get("max_pages_per_search", max_pages_per_search))
                if page_number > source_max_pages:
                    continue

                if source_filter and source != source_filter:
                    continue

                search_record = records_by_source.get(source)
                if search_record is None:
                    independent_key = (source, location)
                    independent_page_key = (source, location, page_number)
                    if (
                        independent_key in query_independent_records
                        and independent_page_key not in used_query_independent_pages
                    ):
                        search_record = query_independent_records[independent_key]
                        used_query_independent_pages.add(independent_page_key)

                if not search_record:
                    continue

                adapter = get_adapter(source)
                tasks.append(
                    {
                        "source": source,
                        "query": query,
                        "location": location,
                        "page_number": page_number,
                        "search_record": search_record,
                        "result_page_url": adapter.build_page_url(search_record["url"], page_number),
                    }
                )

    return tasks


def wait_for_render(page, wait_config: dict) -> None:
    min_seconds = float(wait_config.get("min", 1.5))
    max_seconds = float(wait_config.get("max", 3.0))
    seconds = random.uniform(min_seconds, max_seconds)
    page.wait_for_timeout(int(seconds * 1000))


def scroll_results(page, scroll_config: dict, adapter) -> None:
    if not scroll_config.get("enabled", True):
        return

    steps = int(scroll_config.get("steps", 4))
    wait_seconds = float(scroll_config.get("wait_after_scroll_seconds", 0.4))
    patterns = list(getattr(adapter, "job_url_patterns", ()))
    stable_rounds = 0

    for _ in range(steps):
        info = page.evaluate(
            """
            (patterns) => {
              const matchesPattern = (href) => {
                const lower = (href || "").toLowerCase();
                return patterns.some((pattern) => lower.includes(pattern.toLowerCase()));
              };

              const isScrollable = (el) => {
                if (!el) return false;
                return el.scrollHeight > el.clientHeight + 80;
              };

              const candidates = [
                document.scrollingElement,
                document.documentElement,
                document.body,
                ...Array.from(document.querySelectorAll("main, section, div, ul, ol"))
              ].filter(Boolean);

              let best = null;
              let bestScore = -1;

              for (const el of candidates) {
                if (!isScrollable(el)) continue;
                const anchors = Array.from(el.querySelectorAll("a[href]"));
                const matchedLinks = anchors.filter((a) => matchesPattern(a.href)).length;
                const score = matchedLinks * 10000 + anchors.length * 10 + (el.scrollHeight - el.clientHeight);
                if (score > bestScore) {
                  best = el;
                  bestScore = score;
                }
              }

              const target = best || document.scrollingElement || document.documentElement;
              const isWindowTarget =
                target === document.scrollingElement ||
                target === document.documentElement ||
                target === document.body;

              const before = isWindowTarget ? window.scrollY : target.scrollTop;
              const maxTop = isWindowTarget
                ? document.documentElement.scrollHeight - window.innerHeight
                : target.scrollHeight - target.clientHeight;
              const step = isWindowTarget
                ? Math.max(window.innerHeight * 0.9, 700)
                : Math.max(target.clientHeight * 0.9, 500);

              if (isWindowTarget) {
                window.scrollBy(0, step);
              } else {
                target.scrollTop = target.scrollTop + step;
              }

              const after = isWindowTarget ? window.scrollY : target.scrollTop;
              return {
                before,
                after,
                maxTop,
                moved: Math.abs(after - before),
                score: bestScore
              };
            }
            """,
            patterns,
        )
        page.wait_for_timeout(int(wait_seconds * 1000))

        if info.get("moved", 0) < 5 or info.get("after", 0) >= info.get("maxTop", 0) - 20:
            stable_rounds += 1
        else:
            stable_rounds = 0

        if stable_rounds >= 2:
            break


def page_contains_manual_verification(page, source: str, search_config: dict) -> bool:
    source_config = search_config.get("sources", {}).get(source, {})
    verification_config = search_config.get("discovery", {}).get("manual_verification", {})

    if not verification_config.get("enabled", False):
        return False

    if not source_config.get("manual_verification", False):
        return False

    indicators = [str(item).lower() for item in verification_config.get("indicators", [])]
    if not indicators:
        return False

    try:
        current_url = (page.url or "").lower()
        title = (page.title() or "").lower()
        body_text = (page.locator("body").inner_text(timeout=3000) or "").lower()
    except Exception:
        return False

    haystack = "\n".join([current_url, title, body_text])
    return any(indicator in haystack for indicator in indicators)


def pause_for_manual_verification(page, source: str, args: argparse.Namespace, search_config: dict) -> bool:
    verification_config = search_config.get("discovery", {}).get("manual_verification", {})

    if not page_contains_manual_verification(page, source, search_config):
        return False

    if not args.headed or not args.pause_on_verification:
        return True

    print()
    print(f"[ACTION] Manual verification/login needed for {source}.")
    print(f"[ACTION] Complete it in the open browser tab: {page.url}")
    print("[ACTION] Press Enter here when the page shows search results again.")
    input()
    page.wait_for_load_state("domcontentloaded", timeout=args.timeout_ms)
    page.wait_for_timeout(1000)
    return page_contains_manual_verification(page, source, search_config)


def append_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("a", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_existing_job_urls(path: Path) -> set[str]:
    if not path.exists():
        return set()

    urls = set()
    for row in read_jsonl_file(path):
        url = row.get("job_url")
        if url:
            urls.add(url)
    return urls


def discover(args: argparse.Namespace) -> None:
    search_config = load_search_config()
    discovery_config = search_config["discovery"]

    search_records = read_jsonl_file(SEARCH_URLS_JSONL_OUTPUT_FILE)
    if not search_records:
        raise RuntimeError(f"No search records found in {SEARCH_URLS_JSONL_OUTPUT_FILE}")

    source_order = discovery_config["source_order"]
    max_groups = args.max_search_groups or int(discovery_config.get("max_search_groups_per_run", 20))
    max_pages = args.max_pages_per_search or int(discovery_config.get("max_pages_per_search", 2))
    max_jobs_per_page = int(discovery_config.get("max_jobs_per_search_page", 40))

    tasks = build_round_robin_tasks(
        search_records=search_records,
        search_config=search_config,
        source_order=source_order,
        max_search_groups=max_groups,
        max_pages_per_search=max_pages,
        source_filter=args.source,
    )

    if args.limit:
        tasks = tasks[: args.limit]

    print(f"[INFO] Built {len(tasks)} discovery tasks")
    for task in tasks[: args.sample]:
        print(
            "[TASK] "
            f"{task['source']} | page {task['page_number']} | "
            f"{task['query']} | {task['location']} | {task['result_page_url']}"
        )

    if args.dry_run:
        return

    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    ensure_directories([DISCOVERED_DIR, ANONYMOUS_PROFILE_DIR])

    if args.reset:
        for path in [DISCOVERED_JOBS_JSONL_OUTPUT_FILE, DISCOVERY_DEBUG_OUTPUT_FILE]:
            if path.exists():
                path.unlink()

    seen_job_urls = load_existing_job_urls(DISCOVERED_JOBS_JSONL_OUTPUT_FILE)

    debug = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "tasks_total": len(tasks),
        "tasks_succeeded": 0,
        "tasks_failed": 0,
        "jobs_new": 0,
        "jobs_duplicate": 0,
        "failures": [],
        "task_results": [],
    }

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(ANONYMOUS_PROFILE_DIR),
            headless=not args.headed,
            viewport={"width": 1365, "height": 900},
        )
        page = context.new_page()

        for index, task in enumerate(tasks, start=1):
            source = task["source"]
            adapter = get_adapter(source)
            result_page_url = task["result_page_url"]

            print(
                f"[INFO] {index}/{len(tasks)} "
                f"{source} page={task['page_number']} "
                f"query={task['query']} location={task['location']}"
            )

            try:
                page.goto(result_page_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
                wait_for_render(page, discovery_config["render_wait_seconds"])

                still_blocked = pause_for_manual_verification(page, source, args, search_config)
                if still_blocked:
                    debug["tasks_failed"] += 1
                    debug["failures"].append({**task, "error": "manual_verification_required", "final_url": page.url})
                    debug["task_results"].append(
                        {
                            "source": source,
                            "query": task["query"],
                            "location": task["location"],
                            "page_number": task["page_number"],
                            "result_page_url": result_page_url,
                            "found": 0,
                            "new": 0,
                            "duplicate": 0,
                            "final_url": page.url,
                            "error": "manual_verification_required",
                        }
                    )
                    print(f"[WARN] Manual verification still required: {page.url}")
                    continue

                scroll_results(page, discovery_config["scroll"], adapter)
                wait_for_render(page, discovery_config["render_wait_seconds"])

                collected_at = datetime.now(timezone.utc).isoformat()
                discovered = adapter.extract_jobs(
                    page=page,
                    search_record=task["search_record"],
                    page_number=task["page_number"],
                    collected_at=collected_at,
                )

                new_rows = []
                duplicate_count = 0

                for record in discovered[:max_jobs_per_page]:
                    if record.job_url in seen_job_urls:
                        duplicate_count += 1
                        continue

                    seen_job_urls.add(record.job_url)
                    new_rows.append(asdict(record))

                if new_rows:
                    append_jsonl(DISCOVERED_JOBS_JSONL_OUTPUT_FILE, new_rows)

                debug["tasks_succeeded"] += 1
                debug["jobs_new"] += len(new_rows)
                debug["jobs_duplicate"] += duplicate_count
                debug["task_results"].append(
                    {
                        "source": source,
                        "query": task["query"],
                        "location": task["location"],
                        "page_number": task["page_number"],
                        "result_page_url": result_page_url,
                        "found": len(discovered),
                        "new": len(new_rows),
                        "duplicate": duplicate_count,
                        "final_url": page.url,
                    }
                )
                print(f"[INFO] found={len(discovered)} new={len(new_rows)} duplicate={duplicate_count}")

            except PlaywrightTimeoutError:
                debug["tasks_failed"] += 1
                debug["failures"].append({**task, "error": "timeout"})
                print(f"[WARN] Timeout: {result_page_url}")
            except Exception as error:
                debug["tasks_failed"] += 1
                debug["failures"].append({**task, "error": str(error)})
                print(f"[WARN] Failed: {result_page_url} | {error}")

        context.close()

    debug["finished_at"] = datetime.now(timezone.utc).isoformat()
    write_json_file(DISCOVERY_DEBUG_OUTPUT_FILE, debug)

    print(f"[INFO] New jobs written to: {DISCOVERED_JOBS_JSONL_OUTPUT_FILE}")
    print(f"[INFO] Debug written to: {DISCOVERY_DEBUG_OUTPUT_FILE}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover job URLs using source-aware round-robin scheduling.")
    parser.add_argument("--dry-run", action="store_true", help="Build and print the scheduler queue without crawling.")
    parser.add_argument("--headed", action="store_true", help="Show the browser while crawling.")
    parser.add_argument("--source", choices=["indeed", "stepstone", "linkedin", "xing", "arbeitsagentur", "stellenwerk"])
    parser.add_argument("--limit", type=int, help="Maximum number of discovery tasks to execute.")
    parser.add_argument("--max-search-groups", type=int, help="Maximum query/location groups to include.")
    parser.add_argument("--max-pages-per-search", type=int, help="Maximum result pages per query/location/source.")
    parser.add_argument("--sample", type=int, default=12, help="Number of scheduled tasks to print.")
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--reset", action="store_true", help="Delete previous discovery output before crawling.")
    parser.add_argument(
        "--pause-on-verification",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="In headed mode, pause for manual login/captcha/human verification instead of skipping the task.",
    )
    args = parser.parse_args()

    discover(args)


if __name__ == "__main__":
    main()
