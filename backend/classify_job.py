from urllib.parse import urlparse, parse_qs, unquote_plus
import re

VERSION = "classify_job_2026_04_08_final_v2"


def normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = (
        text.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    text = " ".join(text.split())
    return text


def contains_any(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        if pattern in text:
            return pattern
    return None


def regex_match_any(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        if re.search(pattern, text):
            return pattern
    return None


def title_level_match(text: str) -> str | None:
    patterns = [
        r"\bsenior\b",
        r"\blead\b",
        r"\bprincipal\b",
        r"\bhead of\b",
        r"\bstaff\b",
    ]
    return regex_match_any(text, patterns)


def extract_query_keywords(search_urls: list[str]) -> list[str]:
    keywords = []

    for url in search_urls or []:
        try:
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            values = query.get("keywords", [])
            for value in values:
                decoded = unquote_plus(value).strip()
                if decoded and decoded not in keywords:
                    keywords.append(decoded)
        except Exception:
            continue

    return keywords


def build_compact_job_view(parsed_job: dict) -> dict:
    search_keywords = extract_query_keywords(parsed_job.get("search_urls", []))

    return {
        "url": parsed_job.get("url"),
        "source_job_url": parsed_job.get("source_job_url"),
        "apply_url": parsed_job.get("apply_url"),
        "apply_domain": parsed_job.get("apply_domain"),
        "duplicate_key": parsed_job.get("duplicate_key"),
        "sources": parsed_job.get("sources", []),
        "title": parsed_job.get("title"),
        "company": parsed_job.get("company"),
        "times_seen": parsed_job.get("times_seen", 0),
        "search_count": len(search_keywords),
        "search_keywords": search_keywords,
        "workplace_type_raw": parsed_job.get("workplace_type_raw"),
        "employment_type_raw": parsed_job.get("employment_type_raw"),
        "description_raw": parsed_job.get("description_raw"),
        "parse_quality": parsed_job.get("parse_quality"),
    }


def classify_employment(
    text: str,
    title: str,
    employment_type_raw: str | None = None,
) -> dict:
    title_text = normalize_text(title or "")
    body_text = normalize_text(text or "")
    metadata_text = normalize_text(employment_type_raw or "")

    strong_student_title_patterns = [
        "werkstudent",
        "working student",
        "student assistant",
        "studentische hilfskraft",
        "hiwi",
        "wissenschaftliche hilfskraft",
        "research assistant",
        "master thesis",
        "masterarbeit",
    ]

    strong_student_text_patterns = [
        "werkstudent",
        "working student",
        "student assistant",
        "studentische hilfskraft",
        "teilzeit",
        "part-time",
        "10 bis 20 stunden",
        "bis zu 20 stunden",
        "20 stunden pro woche",
        "20h / woche",
        "20h pro woche",
        "10 to 20 hours",
        "up to 20 hours",
        "20 hours per week",
        "hiwi",
        "wissenschaftliche hilfskraft",
        "research assistant",
        "master thesis",
        "masterarbeit",
    ]

    hard_reject_patterns = [
        "duales studium",
        "dual study",
        "dual student",
        "ausbildung",
        "apprenticeship",
        "trainee program",
        "traineeprogramm",
        "pflichtpraktikum",
        "mandatory internship",
        "compulsory internship",
        "obligatory internship",
        "required internship",
        "vorgeschriebenes praktikum",
        "schuelerpraktikum",
        "schülerpraktikum",
        "volunteer",
        "volunteers wanted",
        "ehrenamt",
    ]

    embedded_patterns = [
        "embedded systems",
        "embedded software",
        "embedded developer",
        "embedded engineer",
        "eingebettete systeme",
    ]

    full_time_patterns = [
        "vollzeit",
        "full-time",
        "40 stunden",
        "39 stunden",
        "38.5 stunden",
        "festanstellung vollzeit",
        "permanent full-time role",
        "40 hours/week",
    ]

    internship_patterns = [
        r"\binternship\b",
        r"\bintern\b",
    ]

    title_student_match = contains_any(title_text, strong_student_title_patterns)
    text_student_match = contains_any(body_text, strong_student_text_patterns)
    hard_reject_match = contains_any(title_text, hard_reject_patterns) or contains_any(body_text, hard_reject_patterns)
    senior_match = title_level_match(title_text)
    embedded_match = contains_any(title_text, embedded_patterns) or contains_any(body_text, embedded_patterns)

    if hard_reject_match:
        return {
            "employment_decision": "hard_role_type_reject",
            "employment_reason": hard_reject_match,
            "employment_reject": True,
        }

    if senior_match:
        return {
            "employment_decision": "senior_level_reject",
            "employment_reason": senior_match,
            "employment_reject": True,
        }

    if embedded_match:
        return {
            "employment_decision": "embedded_reject",
            "employment_reason": embedded_match,
            "employment_reject": True,
        }

    text_full_time_match = contains_any(body_text, full_time_patterns)
    metadata_full_time_match = contains_any(metadata_text, ["full-time"])
    metadata_part_time_match = contains_any(metadata_text, ["part-time"])

    title_internship_match = regex_match_any(title_text, internship_patterns)
    text_internship_match = regex_match_any(body_text, internship_patterns)
    metadata_internship_match = contains_any(metadata_text, ["internship"])

    # Strongest positive: title explicitly says working student / werkstudent
    if title_student_match:
        if text_full_time_match or metadata_full_time_match:
            return {
                "employment_decision": "employment_conflict_text_wins",
                "employment_reason": f"title:{title_student_match} vs full_time_signal",
                "employment_reject": False,
            }
        return {
            "employment_decision": "student_friendly",
            "employment_reason": title_student_match,
            "employment_reject": False,
        }

    # Strong text student-friendly signals
    if text_student_match:
        if text_full_time_match or metadata_full_time_match:
            return {
                "employment_decision": "employment_conflict_text_wins",
                "employment_reason": f"text:{text_student_match} vs full_time_signal",
                "employment_reject": False,
            }
        return {
            "employment_decision": "student_friendly",
            "employment_reason": text_student_match,
            "employment_reject": False,
        }

    # Full-time is not a hard reject anymore: internship/thesis may be 40h,
    # and ambiguous full-time roles should be decided by the LLM.
    if metadata_full_time_match or text_full_time_match:
        return {
            "employment_decision": "full_time_needs_llm",
            "employment_reason": f"metadata:{metadata_full_time_match}" if metadata_full_time_match else text_full_time_match,
            "employment_reject": False,
        }

    # Metadata-only part-time is okay
    if metadata_part_time_match:
        return {
            "employment_decision": "student_friendly",
            "employment_reason": f"metadata:{metadata_part_time_match}",
            "employment_reject": False,
        }

    # Internship alone -> maybe-friendly but not strong positive
    if title_internship_match or text_internship_match or metadata_internship_match:
        return {
            "employment_decision": "internship_only",
            "employment_reason": "internship_detected",
            "employment_reject": False,
        }

    return {
        "employment_decision": "unknown",
        "employment_reason": None,
        "employment_reject": False,
    }


def classify_workplace_and_location(
    text: str,
    title: str,
    company: str,
    location_raw: str | None = None,
    workplace_type_raw: str | None = None,
    search_urls: list[str] | None = None,
) -> dict:
    location_text = normalize_text(location_raw or "")
    metadata_text = normalize_text(workplace_type_raw or "")
    title_text = normalize_text(title or "")
    body_text = normalize_text(text or "")

    allowed_location_patterns = [
        "darmstadt",
        "frankfurt",
        "mainz",
        "wiesbaden",
        "offenbach",
        "hanau",
        "heidelberg",
        "mannheim",
        "rhein-main",
        "rhein main",
        "rhine-main",
        "rhine main",
        "neu-isenburg",
        "eschborn",
        "langen",
        "moerfelden",
        "mörfelden",
        "ruesselsheim",
        "rüsselsheim",
        "bensheim",
        "rossdorf",
        "roßdorf",
        "egelsbach",
        "gross-gerau",
        "groß-gerau",
        "gross gerau",
        "groß gerau",
        "64331",
        "64283",
        "64285",
        "64287",
        "64289",
    ]

    remote_patterns = [
        "remote",
        "100% remote",
        "fully remote",
        "remote moeglich",
        "remote möglich",
        "work from home",
    ]

    hybrid_patterns = [
        "hybrid",
        "hybrid oder remote",
        "office / homeoffice",
        "office/homeoffice",
    ]

    onsite_patterns = [
        "onsite",
        "on-site",
        "office-based",
        "vor ort",
        "praesenz",
        "präsenz",
    ]

    matched_allowed_location = (
        contains_any(location_text, allowed_location_patterns)
        or contains_any(title_text, allowed_location_patterns)
        or contains_any(body_text, allowed_location_patterns)
    )
    if matched_allowed_location:
        return {
            "workplace_decision": "allowed_target_city",
            "workplace_reason": matched_allowed_location,
            "workplace_reject": False,
        }

    if "remote" in metadata_text:
        return {
            "workplace_decision": "remote_allowed",
            "workplace_reason": "metadata:remote",
            "workplace_reject": False,
        }

    if "hybrid" in metadata_text:
        return {
            "workplace_decision": "hybrid_outside_target_reject",
            "workplace_reason": "metadata:hybrid",
            "workplace_reject": True,
        }

    if "on-site" in metadata_text or "onsite" in metadata_text:
        return {
            "workplace_decision": "onsite_outside_target_reject",
            "workplace_reason": "metadata:on-site",
            "workplace_reject": True,
        }

    matched_remote_title = contains_any(title_text, remote_patterns)
    if matched_remote_title:
        return {
            "workplace_decision": "remote_allowed",
            "workplace_reason": matched_remote_title,
            "workplace_reject": False,
        }

    matched_hybrid_title = contains_any(title_text, hybrid_patterns)
    if matched_hybrid_title:
        return {
            "workplace_decision": "hybrid_outside_target_reject",
            "workplace_reason": matched_hybrid_title,
            "workplace_reject": True,
        }

    matched_onsite_title = contains_any(title_text, onsite_patterns)
    if matched_onsite_title:
        return {
            "workplace_decision": "onsite_outside_target_reject",
            "workplace_reason": matched_onsite_title,
            "workplace_reject": True,
        }

    matched_remote_body = contains_any(body_text, remote_patterns)
    if matched_remote_body:
        return {
            "workplace_decision": "remote_allowed",
            "workplace_reason": matched_remote_body,
            "workplace_reject": False,
        }

    matched_hybrid_body = contains_any(body_text, hybrid_patterns)
    if matched_hybrid_body:
        return {
            "workplace_decision": "hybrid_outside_target_reject",
            "workplace_reason": matched_hybrid_body,
            "workplace_reject": True,
        }

    matched_onsite_body = contains_any(body_text, onsite_patterns)
    if matched_onsite_body:
        return {
            "workplace_decision": "onsite_outside_target_reject",
            "workplace_reason": matched_onsite_body,
            "workplace_reject": True,
        }

    return {
        "workplace_decision": "unknown",
        "workplace_reason": None,
        "workplace_reject": False,
    }
