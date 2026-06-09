import json

from config import (
    FILTERED_DIR,
    SHORTLIST_OUTPUT_FILE,
    LLM_CANDIDATES_JSONL_FILE,
    LLM_CANDIDATES_DEBUG_FILE,
)
from utils import ensure_directories, read_json_file, write_json_file


MAX_DESCRIPTION_CHARS = 2800

KEEP_SECTION_MARKERS = [
    "your responsibilities",
    "responsibilities",
    "what you'll do",
    "what you will do",
    "tasks",
    "your tasks",
    "requirements",
    "your profile",
    "profile",
    "qualifications",
    "skills",
    "what you bring",
    "what you'll need",
    "what you will need",
    "about you",
    "aufgaben",
    "deine aufgaben",
    "ihre aufgaben",
    "tätigkeiten",
    "taetigkeiten",
    "anforderungen",
    "dein profil",
    "ihr profil",
    "profil",
    "qualifikation",
    "qualifikationen",
    "das bringst du mit",
    "das bringen sie mit",
    "was du mitbringst",
    "was sie mitbringen",
    "voraussetzungen",
    "kenntnisse",
    "skills",
]

SIGNAL_KEYWORDS = [
    "python",
    "java",
    "c++",
    "sql",
    "javascript",
    "typescript",
    "rust",
    "backend",
    "frontend",
    "fullstack",
    "data",
    "daten",
    "machine learning",
    "ki",
    "ai",
    "llm",
    "power bi",
    "excel",
    "cloud",
    "docker",
    "linux",
    "api",
    "database",
    "postgres",
    "werkstudent",
    "working student",
    "praktikum",
    "internship",
    "hiwi",
    "thesis",
    "masterarbeit",
    "20 stunden",
    "20 hours",
    "teilzeit",
    "part-time",
    "remote",
    "hybrid",
    "on-site",
    "vor ort",
    "deutsch",
    "german",
    "englisch",
    "english",
    "b1",
    "b2",
    "c1",
    "c2",
    "a2",
]

STOP_SECTION_MARKERS = [
    "benefits",
    "your value",
    "your benefits",
    "what we offer",
    "we offer",
    "about us",
    "about the company",
    "company",
    "diversity",
    "equal opportunity",
    "apply now",
    "how to apply",
    "contact",
    "deine vorteile",
    "ihre vorteile",
    "dein mehrwert",
    "ihr mehrwert",
    "mehrwert",
    "was wir bieten",
    "was bieten wir",
    "unser angebot",
    "über uns",
    "ueber uns",
    "unternehmen",
    "wer wir sind",
    "diversität",
    "diversitaet",
    "chancengleichheit",
    "bewirb dich",
    "bewerben sie sich",
    "bewerbung",
    "kontakt",
    "dein ansprechpartner",
    "ihr ansprechpartner",
]


def compact_description(text: str | None) -> str | None:
    if not text:
        return None

    lines = [" ".join(line.split()) for line in text.splitlines()]
    lines = [line for line in lines if line]
    compact = relevant_description_excerpt(lines)

    if len(compact) <= MAX_DESCRIPTION_CHARS:
        return compact

    return compact[:MAX_DESCRIPTION_CHARS].rsplit("\n", 1)[0]


def normalize_line(line: str) -> str:
    return (
        (line or "")
        .lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


def marker_in_line(line: str, markers: list[str]) -> bool:
    normalized = normalize_line(line)
    return any(marker in normalized for marker in markers)


def looks_like_section_heading(line: str) -> bool:
    clean = line.strip()
    if len(clean) > 90:
        return False
    if clean.endswith(":"):
        return True
    if marker_in_line(clean, KEEP_SECTION_MARKERS + STOP_SECTION_MARKERS):
        return True
    return False


def relevant_description_excerpt(lines: list[str]) -> str:
    kept: list[str] = []
    in_keep_section = False
    saw_keep_section = False

    for line in lines:
        is_keep_heading = looks_like_section_heading(line) and marker_in_line(line, KEEP_SECTION_MARKERS)
        is_stop_heading = looks_like_section_heading(line) and marker_in_line(line, STOP_SECTION_MARKERS)

        if is_keep_heading:
            in_keep_section = True
            saw_keep_section = True
            kept.append(line)
            continue

        if is_stop_heading and saw_keep_section:
            in_keep_section = False
            continue

        if in_keep_section:
            kept.append(line)
            continue

        if marker_in_line(line, SIGNAL_KEYWORDS):
            kept.append(line)

    compact = "\n".join(kept)

    # Conservative fallback: if section detection found too little, keep the
    # beginning of the original description rather than over-pruning.
    if len(compact) < 500:
        compact = "\n".join(lines)

    return compact


def build_candidate(job: dict, index: int) -> dict:
    return {
        "candidate_id": f"job_{index:04d}",
        "source_job_url": job.get("source_job_url") or job.get("url"),
        "apply_url": job.get("apply_url"),
        "apply_domain": job.get("apply_domain"),
        "sources": job.get("sources") or [],
        "title": job.get("title"),
        "company": job.get("company"),
        "location_raw": job.get("location_raw"),
        "workplace_type_raw": job.get("workplace_type_raw"),
        "employment_type_raw": job.get("employment_type_raw"),
        "rule_decision": job.get("final_decision"),
        "rule_reasons": job.get("reasons") or [],
        "language_decision": job.get("language_decision"),
        "employment_decision": job.get("employment_decision"),
        "workplace_decision": job.get("workplace_decision"),
        "search_keywords": job.get("search_keywords") or [],
        "description": compact_description(job.get("description_raw")),
    }


def main() -> None:
    ensure_directories([FILTERED_DIR])

    shortlist = read_json_file(SHORTLIST_OUTPUT_FILE)
    candidates = [build_candidate(job, index) for index, job in enumerate(shortlist, start=1)]

    with LLM_CANDIDATES_JSONL_FILE.open("w", encoding="utf-8") as file:
        for candidate in candidates:
            file.write(json.dumps(candidate, ensure_ascii=False) + "\n")

    write_json_file(
        LLM_CANDIDATES_DEBUG_FILE,
        {
            "shortlist_count": len(shortlist),
            "candidate_count": len(candidates),
            "max_description_chars": MAX_DESCRIPTION_CHARS,
            "sample": candidates[:10],
        },
    )

    print(f"[INFO] Shortlist count: {len(shortlist)}")
    print(f"[INFO] LLM candidate count: {len(candidates)}")
    print(f"[INFO] Output written to: {LLM_CANDIDATES_JSONL_FILE}")
    print(f"[INFO] Debug written to: {LLM_CANDIDATES_DEBUG_FILE}")


if __name__ == "__main__":
    main()
