from models import RawExportRecord, MergedJobRecord


def add_unique(values: list, value) -> None:
    if value is not None and value != "" and value not in values:
        values.append(value)


def first_non_empty(current: str | None, candidate: str | None) -> str | None:
    if current:
        return current
    if candidate:
        return candidate
    return current


def merge_records_by_url(records: list[RawExportRecord]) -> list[MergedJobRecord]:
    merged_map: dict[str, MergedJobRecord] = {}

    for record in records:
        existing = merged_map.get(record.url)

        if existing is None:
            merged_map[record.url] = MergedJobRecord(
                url=record.url,
                first_seen_at=record.collected_at,
                last_seen_at=record.collected_at,
                run_ids=[record.run_id],
                search_urls=[record.search_url],
                sources=[record.source] if record.source else [],
                search_queries=[record.search_query] if record.search_query else [],
                search_locations=[record.search_location] if record.search_location else [],
                result_page_numbers=[record.result_page_number]
                if record.result_page_number is not None
                else [],
                title_hint=record.title,
                company_hint=record.company,
                location_hint=record.location,
                times_seen=1,
                simple_score=0,
                reasons=[],
            )
            continue

        if record.collected_at < existing.first_seen_at:
            existing.first_seen_at = record.collected_at

        if record.collected_at > existing.last_seen_at:
            existing.last_seen_at = record.collected_at

        existing.times_seen += 1

        if record.run_id not in existing.run_ids:
            existing.run_ids.append(record.run_id)

        if record.search_url not in existing.search_urls:
            existing.search_urls.append(record.search_url)

        add_unique(existing.sources, record.source)
        add_unique(existing.search_queries, record.search_query)
        add_unique(existing.search_locations, record.search_location)
        add_unique(existing.result_page_numbers, record.result_page_number)

        existing.title_hint = first_non_empty(existing.title_hint, record.title)
        existing.company_hint = first_non_empty(existing.company_hint, record.company)
        existing.location_hint = first_non_empty(existing.location_hint, record.location)

    merged_records = list(merged_map.values())

    for item in merged_records:
        item.run_ids.sort()
        item.search_urls.sort()
        item.sources.sort()
        item.search_queries.sort()
        item.search_locations.sort()
        item.result_page_numbers.sort()

    return merged_records
