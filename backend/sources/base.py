from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from models import DiscoveredJobRecord


class SourceAdapter:
    source_id = "generic"
    job_url_patterns: tuple[str, ...] = ()
    blocked_url_patterns: tuple[str, ...] = ()

    def build_page_url(self, search_url: str, page_number: int) -> str:
        return search_url

    def normalize_job_url(self, url: str) -> Optional[str]:
        return url

    def extract_jobs(self, page, search_record: dict, page_number: int, collected_at: str) -> list[DiscoveredJobRecord]:
        raw_items = page.evaluate(
            """
            () => {
              const anchors = Array.from(document.querySelectorAll("a[href]"));
              return anchors.map((anchor) => {
                const container = anchor.closest("article, li, div");
                const textFrom = (el, selectors) => {
                  if (!el) return null;
                  for (const selector of selectors) {
                    const match = el.querySelector(selector);
                    const text = match && match.innerText ? match.innerText.trim() : "";
                    if (text) return text;
                  }
                  return null;
                };

                return {
                  href: anchor.href,
                  anchorText: anchor.innerText ? anchor.innerText.trim() : "",
                  title: textFrom(container, [
                    "h1", "h2", "h3",
                    "[data-testid*='title']",
                    "[class*='title']",
                    "[class*='jobTitle']"
                  ]),
                  company: textFrom(container, [
                    "[data-testid*='company']",
                    "[class*='company']",
                    "[class*='Company']"
                  ]),
                  location: textFrom(container, [
                    "[data-testid*='location']",
                    "[class*='location']",
                    "[class*='Location']"
                  ])
                };
              });
            }
            """
        )

        jobs: list[DiscoveredJobRecord] = []
        seen_urls = set()

        for item in raw_items:
            href = item.get("href")
            if not href or not self.looks_like_job_url(href):
                continue

            normalized_url = self.normalize_job_url(href)
            if not normalized_url or normalized_url in seen_urls:
                continue

            seen_urls.add(normalized_url)
            jobs.append(
                DiscoveredJobRecord(
                    source=search_record["source"],
                    source_name=search_record.get("source_name", search_record["source"]),
                    search_query=search_record["query"],
                    search_location=search_record["location"],
                    search_url=search_record["url"],
                    result_page_url=self.build_page_url(search_record["url"], page_number),
                    result_page_number=page_number,
                    job_url=normalized_url,
                    title=item.get("title") or item.get("anchorText") or None,
                    company=item.get("company") or None,
                    location=item.get("location") or None,
                    collected_at=collected_at,
                )
            )

        return jobs

    def looks_like_job_url(self, url: str) -> bool:
        lower_url = url.lower()

        if any(pattern in lower_url for pattern in self.blocked_url_patterns):
            return False

        return any(pattern in lower_url for pattern in self.job_url_patterns)

    @staticmethod
    def to_dict(record: DiscoveredJobRecord) -> dict:
        return asdict(record)
