from models import MergedJobRecord


def score_merged_record(record: MergedJobRecord) -> MergedJobRecord:
    score = 0
    reasons: list[str] = []

    if record.times_seen >= 2:
        score += 2
        reasons.append("seen_multiple_times")

    if len(record.run_ids) >= 2:
        score += 3
        reasons.append("seen_in_multiple_runs")

    if len(record.search_urls) >= 2:
        score += 3
        reasons.append("seen_in_multiple_searches")

    joined_search_text = " ".join(
        record.search_urls + record.search_queries + record.search_locations
    ).lower()

    if "frankfurt" in joined_search_text:
        score += 2
        reasons.append("matched_frankfurt_search")

    if "darmstadt" in joined_search_text:
        score += 2
        reasons.append("matched_darmstadt_search")

    if "remote" in joined_search_text:
        score += 1
        reasons.append("matched_remote_search")

    if "werkstudent" in joined_search_text:
        score += 2
        reasons.append("matched_werkstudent_search")

    if "working%20student" in joined_search_text or "working+student" in joined_search_text:
        score += 2
        reasons.append("matched_working_student_search")

    if "working student" in joined_search_text:
        score += 2
        reasons.append("matched_working_student_search")

    if "internship" in joined_search_text or "praktikum" in joined_search_text:
        score += 1
        reasons.append("matched_internship_search")

    if "hiwi" in joined_search_text or "thesis" in joined_search_text or "masterarbeit" in joined_search_text:
        score += 1
        reasons.append("matched_hiwi_or_thesis_search")

    record.simple_score = score
    record.reasons = reasons
    return record


def score_all_records(records: list[MergedJobRecord]) -> list[MergedJobRecord]:
    scored = [score_merged_record(record) for record in records]
    scored.sort(key=lambda item: (-item.simple_score, -item.times_seen, item.url))
    return scored
