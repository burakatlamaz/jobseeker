from typing import Optional
import re
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from config import (
    PLAYWRIGHT_USER_DATA_DIR,
    USE_CHROME_CHANNEL,
    HEADLESS,
    PAGE_LOAD_TIMEOUT_MS,
    AFTER_LOAD_WAIT_MS,
    BETWEEN_JOBS_WAIT_MS,
)
from models import MergedJobRecord, ParsedJobRecord


def safe_text(locator) -> Optional[str]:
    try:
        if locator.count() == 0:
            return None

        text = locator.first.inner_text().strip()
        return text if text else None
    except Exception:
        return None


def safe_all_texts(locator) -> list[str]:
    values = []
    try:
        count = locator.count()
        for i in range(count):
            try:
                text = locator.nth(i).inner_text().strip()
                if text:
                    values.append(text)
            except Exception:
                continue
    except Exception:
        return []

    unique_values = []
    seen = set()
    for item in values:
        if item not in seen:
            unique_values.append(item)
            seen.add(item)

    return unique_values


def normalize_text_key(text: str | None) -> str:
    value = (text or "").lower()
    value = (
        value.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def detect_source_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""

        if "linkedin.com" in host:
            return "linkedin"
        if "indeed.com" in host:
            return "indeed"
        if "stepstone.de" in host:
            return "stepstone"
        if "xing.com" in host:
            return "xing"
        if "arbeitsagentur.de" in host:
            return "arbeitsagentur"
        if "stellenwerk.de" in host:
            return "stellenwerk"

        return "unknown"
    except Exception:
        return "unknown"


def get_domain(url: str | None) -> Optional[str]:
    if not url:
        return None

    try:
        host = urlparse(url).hostname or ""
        if host.startswith("www."):
            host = host[4:]
        return host or None
    except Exception:
        return None


def is_external_apply_candidate(href: str, source: str) -> bool:
    domain = get_domain(href)
    if not domain:
        return False

    source_domains = {
        "linkedin": ["linkedin.com"],
        "indeed": ["indeed.com"],
        "stepstone": ["stepstone.de"],
        "xing": ["xing.com"],
        "arbeitsagentur": ["arbeitsagentur.de"],
        "stellenwerk": ["stellenwerk.de"],
    }

    return not any(source_domain in domain for source_domain in source_domains.get(source, []))


def safe_attribute(locator, name: str) -> Optional[str]:
    try:
        if locator.count() == 0:
            return None
        value = locator.first.get_attribute(name)
        return value.strip() if value else None
    except Exception:
        return None


def absolutize_url(page, href: str | None) -> Optional[str]:
    if not href:
        return None

    try:
        return page.evaluate(
            """href => new URL(href, window.location.href).toString()""",
            href,
        )
    except Exception:
        return href


def extract_title(page) -> Optional[str]:
    selectors = [
        "h1",
        ".top-card-layout__title",
        ".job-details-jobs-unified-top-card__job-title h1",
        "[data-test-id='job-title']",
    ]

    for selector in selectors:
        value = safe_text(page.locator(selector))
        if value:
            return value

    return None


def extract_title_for_source(page, source: str) -> Optional[str]:
    source_selectors = {
        "indeed": [
            "h1[data-testid='jobsearch-JobInfoHeader-title']",
            "[data-testid='jobsearch-JobInfoHeader-title'] h1",
            "h1",
        ],
        "stepstone": [
            "[data-at='header-job-title']",
            "[data-testid='job-title']",
            "h1",
        ],
        "xing": [
            "h1",
            "[data-testid*='job-title']",
        ],
        "arbeitsagentur": [
            "h1",
            "[data-testid*='beruf']",
        ],
        "stellenwerk": [
            "h1",
            ".node-title",
        ],
    }

    for selector in source_selectors.get(source, []):
        value = safe_text(page.locator(selector))
        if value:
            return value

    return extract_title(page)


def extract_company(page) -> Optional[str]:
    selectors = [
        ".topcard__org-name-link",
        ".job-details-jobs-unified-top-card__company-name a",
        ".job-details-jobs-unified-top-card__company-name",
        "[data-test-id='job-details-company-name']",
    ]

    for selector in selectors:
        value = safe_text(page.locator(selector))
        if value:
            return value

    return None


def extract_company_for_source(page, source: str) -> Optional[str]:
    source_selectors = {
        "indeed": [
            "[data-testid='inlineHeader-companyName']",
            "[data-company-name='true']",
            ".jobsearch-CompanyInfoContainer a",
            ".jobsearch-CompanyInfoContainer",
        ],
        "stepstone": [
            "[data-at='header-company-name']",
            "[data-testid='company-name']",
            "a[href*='/cmp/']",
        ],
        "xing": [
            "[data-testid*='company']",
            "a[href*='/companies/']",
        ],
        "arbeitsagentur": [
            "[data-testid*='arbeitgeber']",
            "[data-testid*='company']",
        ],
        "stellenwerk": [
            ".field--name-field-company",
            "[class*='company']",
        ],
    }

    for selector in source_selectors.get(source, []):
        value = safe_text(page.locator(selector))
        if value:
            return value

    return extract_company(page)


def extract_location(page) -> Optional[str]:
    selectors = [
        ".topcard__flavor--bullet",
        ".job-details-jobs-unified-top-card__primary-description-container",
        "[data-test-id='job-location']",
    ]

    for selector in selectors:
        value = safe_text(page.locator(selector))
        if value:
            return value

    return None


def extract_location_for_source(page, source: str) -> Optional[str]:
    source_selectors = {
        "indeed": [
            "[data-testid='job-location']",
            "[data-testid='inlineHeader-companyLocation']",
            ".jobsearch-JobInfoHeader-subtitle div",
        ],
        "stepstone": [
            "[data-at='header-job-location']",
            "[data-testid='job-location']",
            "[class*='location']",
        ],
        "xing": [
            "[data-testid*='location']",
            "[class*='location']",
        ],
        "arbeitsagentur": [
            "[data-testid*='arbeitsort']",
            "[data-testid*='location']",
        ],
        "stellenwerk": [
            ".field--name-field-location",
            "[class*='location']",
        ],
    }

    for selector in source_selectors.get(source, []):
        value = safe_text(page.locator(selector))
        if value:
            return value

    return extract_location(page)


def extract_description(page) -> Optional[str]:
    selectors = [
        ".show-more-less-html__markup",
        ".jobs-description__content",
        ".jobs-box__html-content",
        ".jobs-description-content__text",
        "[data-test-id='job-details-description']",
    ]

    for selector in selectors:
        value = safe_text(page.locator(selector))
        if value and len(value) > 100:
            return value

    body_text = safe_text(page.locator("body"))
    return body_text


def extract_description_for_source(page, source: str) -> tuple[Optional[str], str]:
    source_selectors = {
        "linkedin": [
            ".jobs-description__content",
            ".jobs-box__html-content",
            ".jobs-description-content__text",
            ".show-more-less-html__markup",
        ],
        "indeed": [
            "#jobDescriptionText",
            "[data-testid='jobsearch-JobComponent-description']",
            ".jobsearch-jobDescriptionText",
        ],
        "stepstone": [
            "[data-at='job-ad-content']",
            "[data-testid='job-description']",
            "article",
            "main section",
        ],
        "xing": [
            "[data-testid*='description']",
            "article",
            "main",
        ],
        "arbeitsagentur": [
            "[data-testid*='stellenbeschreibung']",
            "[data-testid*='description']",
            "main",
        ],
        "stellenwerk": [
            ".field--name-body",
            "article",
            "main",
        ],
    }

    for selector in source_selectors.get(source, []):
        value = safe_text(page.locator(selector))
        if value and len(value) > 80:
            return trim_description_noise(value), selector

    value = extract_description(page)
    return trim_description_noise(value) if value else value, "fallback"


def extract_apply_url(page, source: str) -> Optional[str]:
    apply_selectors = [
        "a[href][aria-label*='Apply']",
        "a[href][aria-label*='Bewerben']",
        "a[href][data-control-name*='jobdetails_topcard']",
        "a[href][id*='apply']",
        "a[href][class*='apply']",
        "a[href*='/apply']",
        "a[href*='/bewerben']",
        "a[href*='/applystart']",
        "a[href*='indeedapply']",
    ]

    for selector in apply_selectors:
        href = safe_attribute(page.locator(selector), "href")
        absolute = absolutize_url(page, href)
        if absolute:
            return absolute

    try:
        anchors = page.locator("a[href]")
        count = min(anchors.count(), 200)
        for index in range(count):
            anchor = anchors.nth(index)
            text = (safe_text(anchor) or "").lower()
            aria = (anchor.get_attribute("aria-label") or "").lower()
            href = anchor.get_attribute("href")
            if not href:
                continue

            combined = f"{text} {aria}"
            if not any(word in combined for word in ["apply", "bewerben", "bewerbung"]):
                continue

            absolute = absolutize_url(page, href)
            if absolute:
                return absolute
    except Exception:
        pass

    return None


def build_duplicate_key(
    title: str | None,
    company: str | None,
    location: str | None,
    apply_url: str | None,
) -> Optional[str]:
    apply_domain = get_domain(apply_url)
    title_key = normalize_text_key(title)
    company_key = normalize_text_key(company)
    location_key = normalize_text_key(location)

    if apply_url:
        parsed = urlparse(apply_url)
        query = parse_qs(parsed.query)
        for key in ["jobId", "job_id", "jk", "gh_jid", "lever-origin", "source_id", "id"]:
            values = query.get(key)
            if values:
                return f"apply:{apply_domain}:{key}:{normalize_text_key(values[0])}"

        path_key = normalize_text_key(parsed.path)
        if apply_domain and path_key:
            return f"apply:{apply_domain}:{path_key}"

    if title_key and company_key:
        location_part = location_key if location_key else "unknown-location"
        return f"content:{company_key}:{title_key}:{location_part}"

    return None


def extract_job_insight_items(page) -> list[str]:
    selectors = [
        ".job-details-jobs-unified-top-card__job-insight span",
        ".job-details-jobs-unified-top-card__job-insight div",
        ".job-details-fit-level-preferences span",
        ".job-details-fit-level-preferences div",
        ".artdeco-inline-feedback__message",
    ]

    collected = []

    for selector in selectors:
        values = safe_all_texts(page.locator(selector))
        for value in values:
            if value and value not in collected:
                collected.append(value)

    return collected


def normalize_line(line: str) -> str:
    return " ".join((line or "").strip().split())


def get_clean_body_lines(body_text: str) -> list[str]:
    if not body_text:
        return []

    lines = [normalize_line(line) for line in body_text.splitlines()]
    lines = [line for line in lines if line]

    noise_patterns = [
        "skip to main content",
        "home",
        "my network",
        "jobs",
        "messaging",
        "notifications",
        "for business",
        "try premium",
        "0 notifications",
    ]

    cleaned = []
    for line in lines:
        lower = line.lower()
        if lower in noise_patterns:
            continue
        if line == "Me":
            continue
        cleaned.append(line)

    return cleaned


def fallback_extract_header_fields_from_body(body_text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    lines = get_clean_body_lines(body_text)

    location_index = None

    for i, line in enumerate(lines):
        lower = line.lower()

        if " ago" in lower or "reposted" in lower or "clicked apply" in lower or "clicked Bewerb".lower() in lower:
            location_index = i
            break

        if "germany" in lower and "·" in line:
            location_index = i
            break

    if location_index is None or location_index < 2:
        return None, None, None

    location_line = lines[location_index]
    title_line = lines[location_index - 1]
    company_line = lines[location_index - 2]

    return title_line, company_line, location_line


def fallback_extract_employment_and_workplace_from_body(body_text: str) -> tuple[Optional[str], Optional[str]]:
    lines = get_clean_body_lines(body_text)
    first_chunk = " ".join(lines[:40]).lower()

    workplace_type_raw = None
    employment_type_raw = None

    if "remote" in first_chunk:
        workplace_type_raw = "remote"
    elif "hybrid" in first_chunk:
        workplace_type_raw = "hybrid"
    elif "on-site" in first_chunk or "onsite" in first_chunk:
        workplace_type_raw = "on-site"

    if "full-time" in first_chunk:
        employment_type_raw = "full-time"
    elif "part-time" in first_chunk:
        employment_type_raw = "part-time"
    elif re.search(r"\binternship\b", first_chunk):
        employment_type_raw = "internship"
    elif "contract" in first_chunk:
        employment_type_raw = "contract"
    elif "temporary" in first_chunk:
        employment_type_raw = "temporary"

    return workplace_type_raw, employment_type_raw


def trim_description_noise(text: str) -> str:
    if not text:
        return text

    stop_markers = [
        "More jobs",
        "Company photos",
        "Show more",
        "People also viewed",
        "Jobs you may like",
        "Meet the hiring team",
        "About the company",
        "Browse jobs",
        "Similar jobs",
        "Recommended for you",
        "Get notified about new",
        "I’m interested",
        "I'm interested",
    ]

    cut_positions = []

    for marker in stop_markers:
        idx = text.find(marker)
        if idx != -1:
            cut_positions.append(idx)

    if cut_positions:
        text = text[:min(cut_positions)].strip()

    return text


def fallback_extract_clean_description(body_text: str) -> Optional[str]:
    if not body_text:
        return None

    lines = get_clean_body_lines(body_text)
    joined = "\n".join(lines)

    start_markers = [
        "About the job",
        "About The Role",
        "What You’ll Do",
        "What You'll Do",
        "What you’ll do",
        "What you'll do",
        "What You'll Need",
        "What You’ll Need",
        "Requirements",
        "Your tasks",
        "Unternehmensbeschreibung",
        "Stellenbeschreibung",
        "Qualifikationen",
        "Deine Aufgaben",
        "Was dich bei uns erwartet",
        "Was wir von dir erwarten",
    ]

    start_index = None
    for marker in start_markers:
        idx = joined.find(marker)
        if idx != -1:
            start_index = idx
            break

    if start_index is not None:
        joined = joined[start_index:].strip()

    joined = trim_description_noise(joined)
    return joined


def parse_single_job(page, merged_record: MergedJobRecord) -> ParsedJobRecord:
    source = merged_record.sources[0] if merged_record.sources else detect_source_from_url(merged_record.url)

    parsed = ParsedJobRecord(
        url=merged_record.url,
        source_job_url=merged_record.url,
        first_seen_at=merged_record.first_seen_at,
        last_seen_at=merged_record.last_seen_at,
        times_seen=merged_record.times_seen,
        run_ids=merged_record.run_ids,
        search_urls=merged_record.search_urls,
        sources=merged_record.sources or ([source] if source != "unknown" else []),
        search_queries=merged_record.search_queries,
        search_locations=merged_record.search_locations,
        title=merged_record.title_hint,
        company=merged_record.company_hint,
        location_raw=merged_record.location_hint,
        parse_source=source,
    )

    try:
        response = page.goto(
            merged_record.url,
            wait_until="domcontentloaded",
            timeout=PAGE_LOAD_TIMEOUT_MS,
        )

        if response is None:
            parsed.page_loaded = False
            parsed.parse_success = False
            parsed.parse_error = "No response returned by page.goto"
            return parsed

        parsed.page_loaded = True
        page.wait_for_timeout(AFTER_LOAD_WAIT_MS)

        parsed.title = extract_title_for_source(page, source) or parsed.title
        parsed.company = extract_company_for_source(page, source) or parsed.company
        parsed.location_raw = extract_location_for_source(page, source) or parsed.location_raw
        parsed.description_raw, description_selector = extract_description_for_source(page, source)
        parsed.job_insight_items = extract_job_insight_items(page)
        parsed.apply_url = extract_apply_url(page, source)
        parsed.apply_domain = get_domain(parsed.apply_url)

        body_text = safe_text(page.locator("body")) or ""

        if not parsed.title or not parsed.company or not parsed.location_raw:
            fb_title, fb_company, fb_location = fallback_extract_header_fields_from_body(body_text)

            if not parsed.title and fb_title:
                parsed.title = fb_title

            if not parsed.company and fb_company:
                parsed.company = fb_company

            if not parsed.location_raw and fb_location:
                parsed.location_raw = fb_location

        if not parsed.workplace_type_raw or not parsed.employment_type_raw:
            fb_workplace, fb_employment = fallback_extract_employment_and_workplace_from_body(body_text)

            if not parsed.workplace_type_raw and fb_workplace:
                parsed.workplace_type_raw = fb_workplace

            if not parsed.employment_type_raw and fb_employment:
                parsed.employment_type_raw = fb_employment

        clean_description = (
            fallback_extract_clean_description(body_text)
            if not parsed.description_raw or description_selector == "fallback"
            else None
        )

        if clean_description:
            parsed.description_raw = clean_description

        parsed.duplicate_key = build_duplicate_key(
            parsed.title,
            parsed.company,
            parsed.location_raw,
            parsed.apply_url,
        )
        parsed.parse_quality = "source_container" if description_selector != "fallback" else "fallback_body"
        parsed.parse_success = bool(parsed.title or parsed.company or parsed.location_raw or parsed.description_raw)

        if not parsed.parse_success:
            parsed.parse_error = "Could not extract enough fields"
            parsed.parse_quality = "failed"

        return parsed

    except PlaywrightTimeoutError:
        parsed.page_loaded = False
        parsed.parse_success = False
        parsed.parse_error = "Timeout while loading page"
        return parsed

    except Exception as error:
        parsed.page_loaded = False
        parsed.parse_success = False
        parsed.parse_error = str(error)
        return parsed


def parse_jobs(merged_records: list[MergedJobRecord], limit: Optional[int] = None) -> list[ParsedJobRecord]:
    records_to_parse = merged_records[:limit] if limit is not None else merged_records
    parsed_results: list[ParsedJobRecord] = []

    with sync_playwright() as p:
        launch_kwargs = {
            "user_data_dir": str(PLAYWRIGHT_USER_DATA_DIR),
            "headless": HEADLESS,
        }

        if USE_CHROME_CHANNEL:
            launch_kwargs["channel"] = "chrome"

        context = p.chromium.launch_persistent_context(**launch_kwargs)

        existing_pages = context.pages
        if existing_pages:
            page = existing_pages[0]
            for extra_page in existing_pages[1:]:
                try:
                    extra_page.close()
                except Exception:
                    pass
        else:
            page = context.new_page()

        print("[INFO] Chrome opened with persistent profile.")
        print("[INFO] Same single tab will be reused for all jobs.")
        print("[INFO] Parsing jobs...")

        for index, merged_record in enumerate(records_to_parse, start=1):
            print(f"[INFO] Parsing {index}/{len(records_to_parse)}: {merged_record.url}")

            parsed = parse_single_job(page, merged_record)
            parsed_results.append(parsed)

            try:
                page.wait_for_timeout(BETWEEN_JOBS_WAIT_MS)
            except Exception:
                pass

        try:
            page.close()
        except Exception:
            pass

        context.close()

    return parsed_results
