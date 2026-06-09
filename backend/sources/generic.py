from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sources.base import SourceAdapter


def replace_query_params(url: str, updates: dict[str, str | int | None]) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)

    for key, value in updates.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = [str(value)]

    clean_query = urlencode(query, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, ""))


def strip_query_except(url: str, allowed_keys: set[str]) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    clean_query = {key: value for key, value in query.items() if key in allowed_keys}
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip("/"),
            parsed.params,
            urlencode(clean_query, doseq=True),
            "",
        )
    )


class IndeedAdapter(SourceAdapter):
    source_id = "indeed"
    job_url_patterns = ("de.indeed.com/viewjob", "de.indeed.com/rc/clk", "indeed.com/viewjob", "indeed.com/rc/clk")
    blocked_url_patterns = ("/cmp/", "/career/", "/companies/")

    def build_page_url(self, search_url: str, page_number: int) -> str:
        start = (page_number - 1) * 10
        return replace_query_params(search_url, {"start": start if start else None})

    def normalize_job_url(self, url: str) -> str | None:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        job_key = (query.get("jk") or [None])[0]
        if job_key:
            return f"https://de.indeed.com/viewjob?jk={job_key}"
        return strip_query_except(url, {"jk"})


class LinkedInAdapter(SourceAdapter):
    source_id = "linkedin"
    job_url_patterns = ("linkedin.com/jobs/view/",)
    blocked_url_patterns = ("/jobs/search/", "/jobs/collections/")

    def build_page_url(self, search_url: str, page_number: int) -> str:
        start = (page_number - 1) * 25
        return replace_query_params(search_url, {"start": start if start else None})

    def normalize_job_url(self, url: str) -> str | None:
        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]

        try:
            view_index = parts.index("view")
            job_id = parts[view_index + 1]
        except (ValueError, IndexError):
            return None

        return f"https://www.linkedin.com/jobs/view/{job_id}"


class StepStoneAdapter(SourceAdapter):
    source_id = "stepstone"
    job_url_patterns = ("stepstone.de/stellenangebote",)
    blocked_url_patterns = ("stepstone.de/jobs?what=", "stepstone.de/jobs/?what=")

    def build_page_url(self, search_url: str, page_number: int) -> str:
        return replace_query_params(search_url, {"page": page_number if page_number > 1 else None})

    def normalize_job_url(self, url: str) -> str | None:
        return strip_query_except(url, set())


class XingAdapter(SourceAdapter):
    source_id = "xing"
    job_url_patterns = ("xing.com/jobs/",)
    blocked_url_patterns = ("xing.com/jobs/search",)

    def build_page_url(self, search_url: str, page_number: int) -> str:
        return replace_query_params(search_url, {"page": page_number if page_number > 1 else None})

    def normalize_job_url(self, url: str) -> str | None:
        return strip_query_except(url, set())


class ArbeitsagenturAdapter(SourceAdapter):
    source_id = "arbeitsagentur"
    job_url_patterns = ("arbeitsagentur.de/jobsuche/jobdetail/",)
    blocked_url_patterns = ("arbeitsagentur.de/jobsuche/suche",)

    def build_page_url(self, search_url: str, page_number: int) -> str:
        return replace_query_params(search_url, {"seite": page_number if page_number > 1 else None})

    def normalize_job_url(self, url: str) -> str | None:
        return strip_query_except(url, set())


class StellenwerkAdapter(SourceAdapter):
    source_id = "stellenwerk"
    job_url_patterns = ("stellenwerk.de/",)
    blocked_url_patterns = (
        "/arbeitgeber",
        "/faq",
        "/job-ads",
        "/magazin",
        "/merkzettel",
        "/preis",
        "/standorte",
    )
    valid_location_slugs = {
        "darmstadt",
        "frankfurt",
        "heidelberg",
        "hamburg",
        "mainz",
        "wiesbaden",
    }

    def build_page_url(self, search_url: str, page_number: int) -> str:
        start = (page_number - 1) * 10
        return replace_query_params(search_url, {"pagination[start]": start if start else None})

    def normalize_job_url(self, url: str) -> str | None:
        return strip_query_except(url, set())

    def looks_like_job_url(self, url: str) -> bool:
        lower_url = url.lower()
        if any(pattern in lower_url for pattern in self.blocked_url_patterns):
            return False

        parsed = urlparse(lower_url)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            return False

        location_slug = parts[0]
        last_part = parts[-1]

        return location_slug in self.valid_location_slugs and any(char.isdigit() for char in last_part)


ADAPTERS = {
    "indeed": IndeedAdapter(),
    "linkedin": LinkedInAdapter(),
    "stepstone": StepStoneAdapter(),
    "xing": XingAdapter(),
    "arbeitsagentur": ArbeitsagenturAdapter(),
    "stellenwerk": StellenwerkAdapter(),
}


def get_adapter(source: str) -> SourceAdapter:
    return ADAPTERS.get(source, SourceAdapter())
