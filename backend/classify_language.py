import re
from typing import Optional


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


def contains_any(text: str, patterns: list[str]) -> Optional[str]:
    for pattern in patterns:
        if pattern in text:
            return pattern
    return None


def regex_match_any(text: str, patterns: list[str]) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return pattern
    return None


def detect_posting_language(text: str) -> str:
    normalized = normalize_text(text)

    german_markers = [
        "wir suchen",
        "deine aufgaben",
        "qualifikationen",
        "deutschkenntnisse",
        "was wir dir bieten",
        "werkstudent",
        "kenntnisse",
        "studium",
        "stellenbeschreibung",
        "unternehmensbeschreibung",
    ]

    english_markers = [
        "what you'll do",
        "what you will do",
        "what you'll need",
        "about the role",
        "requirements",
        "nice to have",
        "internship",
        "working student",
        "about the job",
        "bonus points",
    ]

    german_hits = sum(1 for item in german_markers if item in normalized)
    english_hits = sum(1 for item in english_markers if item in normalized)

    if german_hits > english_hits and german_hits >= 2:
        return "german"
    if english_hits > german_hits and english_hits >= 2:
        return "english"
    return "mixed_or_unknown"


def classify_language_requirement(text: str) -> dict:
    normalized = normalize_text(text)
    posting_language = detect_posting_language(text)

    no_german_needed_phrases = [
        "kein deutsch erforderlich",
        "deutschkenntnisse nicht erforderlich",
        "deutsch nicht notwendig",
        "english only",
        "working language is english",
        "international team",
        "english speaking environment",
        "arbeitssprache englisch",
        "englisch als arbeitssprache",
        "internationale teamsprache englisch",
        "no german required",
        "german not required",
        "english is sufficient",
        "german is not required",
    ]

    preferred_phrases = [
        "deutsch von vorteil",
        "deutschkenntnisse von vorteil",
        "gute deutschkenntnisse wuenschenswert",
        "gute deutschkenntnisse wünschenswert",
        "deutsch ist ein plus",
        "optional deutsch",
        "german is a plus",
        "german preferred",
        "german beneficial",
        "nice to have german",
        "deutschkenntnisse sind von vorteil",
        "wuenschenswert sind deutschkenntnisse",
        "wünschenswert sind deutschkenntnisse",
        "basic german is a plus",
    ]

    hard_reject_phrases = [
        "verhandlungssicher deutsch",
        "fliessend deutsch",
        "fließend deutsch",
        "deutsch in wort und schrift",
        "sehr gute deutschkenntnisse",
        "sehr gute kenntnisse der deutschen sprache",
        "deutschkenntnisse erforderlich",
        "deutschkenntnisse zwingend erforderlich",
        "deutsch erforderlich",
        "deutsch (erforderlich)",
        "sprache: deutsch",
        "sprache deutsch",
        "deutsch: erforderlich",
        "deutschkenntnisse: erforderlich",
        "sehr gute deutsch",
        "sehr gute sprachkenntnisse in deutsch",
        "sehr gute deutsche sprachkenntnisse",
        "business fluent german",
        "fluent german required",
        "very good german",
        "very good german skills",
        "german: required",
        "language: german",
        "german required",
        "must speak german",
        "professional proficiency in german required",
        "gute kommunikationsfaehigkeiten in deutsch",
        "gute kommunikationsfähigkeiten in deutsch",
        "sehr gut in wort und schrift",
        "gute deutschkenntnisse in wort und schrift",
        "sehr gute deutschkenntnisse in wort und schrift",
        "deutschkenntnisse: sehr gut in wort und schrift",
        "deutschkenntnisse sehr gut in wort und schrift",
        "deutschkenntnisse sehr gut",
        "native-level german",
        "excellent german",
        "excellent german language skills",
        "must communicate in german",
        "must be able to communicate in german",
        "you must speak german",
        "you need german",
        "german-speaking clients",
    ]

    hard_reject_regex = [
        r"\b(deutsch|german)\b.*\b(b2|c1|c2)\b",
        r"\b(b2|c1|c2)\b.*\b(deutsch|german)\b",
        r"\b(b2|c1|c2)\b.*\b(deutschkenntnisse|german skills|german language)\b",
        r"\bmind\.\s*b2\b",
        r"\bmindestens\s*b2\b",
        r"\bb2[\-\s]*niveau\b",
        r"\bc1[\-\s]*niveau\b",
        r"\bc2[\-\s]*niveau\b",
        r"\bdeutschkenntnisse.*b2\b",
        r"\bdeutschkenntnisse.*c1\b",
        r"\bdeutschkenntnisse.*c2\b",
        r"\b(b2|c1|c2)\s*deutschkenntnisse\b",
        r"\b(b2|c1|c2)\s*german\b",
        r"\bdeutsch.*wort und schrift\b",
        r"\bdeutsch\b\s*\(\s*erforderlich\s*\)",
        r"\bsprache\s*:\s*deutsch\b.*\b(erforderlich|required)\b",
        r"\bdeutsch\s*:\s*(erforderlich|required)\b",
        r"\bdeutschkenntnisse\s*:\s*(erforderlich|required)\b",
        r"\bsehr\s+gute[nr]?\s+(deutsch|deutschkenntnisse|sprachkenntnisse.*deutsch)\b",
        r"\bgute[nr]?\s+(deutsch|deutschkenntnisse)\b.*\b(erforderlich|required)\b",
        r"\b(erforderlich|required)\b.*\bgute[nr]?\s+(deutsch|deutschkenntnisse)\b",
        r"\bgerman.*required\b",
        r"\blanguage\s*:\s*german\b.*\b(required|mandatory)\b",
        r"\bgerman\s*:\s*(required|mandatory)\b",
        r"\bvery\s+good\s+german\b",
        r"\bdeutschkenntnisse\s*:\s*sehr gut\b",
        r"\bsehr gute kenntnisse.*deutsch\b",
        r"\bgute kenntnisse.*deutsch\b",
        r"\bdu sprichst\b.*\bdeutsch\b",
        r"\bdu beherrschst\b.*\bdeutsch\b",
        r"\byou speak\b.*\bgerman\b",
        r"\byou must\b.*\bgerman\b",
        r"\brequired\b.*\bgerman\b",
        r"\bexcellent\b.*\bgerman\b",
        r"\bfluent\b.*\bgerman\b",
        r"\bbusiness fluent\b.*\bgerman\b",
        r"\bconfidence? in german\b",
    ]

    english_positive_phrases = [
        "international team",
        "distributed international teams",
        "english speaking environment",
        "global team",
        "international environment",
        "english only",
        "working language is english",
        "arbeitssprache englisch",
        "english is sufficient",
    ]

    german_mention_patterns = [
        r"\bdeutsch\b",
        r"\bgerman\b",
        r"\bdeutschkenntnisse\b",
        r"\bgerman language\b",
        r"\bgerman skills\b",
        r"\bauf deutsch\b",
        r"\bin german\b",
        r"\bgerman-speaking\b",
        r"\bsprachkenntnisse.*deutsch\b",
        r"\bsprache.*deutsch\b",
    ]

    matched = contains_any(normalized, no_german_needed_phrases)
    if matched:
        return {
            "posting_language": posting_language,
            "language_decision": "no_german_needed",
            "language_reason": matched,
            "english_environment_signal": True,
            "language_reject": False,
        }

    matched = contains_any(normalized, preferred_phrases)
    if matched:
        return {
            "posting_language": posting_language,
            "language_decision": "german_preferred_only",
            "language_reason": matched,
            "english_environment_signal": False,
            "language_reject": False,
        }

    matched = contains_any(normalized, hard_reject_phrases)
    if matched:
        return {
            "posting_language": posting_language,
            "language_decision": "german_too_high_reject",
            "language_reason": matched,
            "english_environment_signal": False,
            "language_reject": True,
        }

    matched = regex_match_any(normalized, hard_reject_regex)
    if matched:
        return {
            "posting_language": posting_language,
            "language_decision": "german_too_high_reject",
            "language_reason": matched,
            "english_environment_signal": False,
            "language_reject": True,
        }

    matched = contains_any(normalized, english_positive_phrases)
    if matched:
        return {
            "posting_language": posting_language,
            "language_decision": "unknown_but_english_friendly",
            "language_reason": matched,
            "english_environment_signal": True,
            "language_reject": False,
        }

    matched = regex_match_any(normalized, german_mention_patterns)
    if matched:
        return {
            "posting_language": posting_language,
            "language_decision": "german_mentioned_unclear",
            "language_reason": matched,
            "english_environment_signal": False,
            "language_reject": False,
        }

    if posting_language == "english":
        return {
            "posting_language": posting_language,
            "language_decision": "unknown_but_english_posting",
            "language_reason": "posting_language_english",
            "english_environment_signal": True,
            "language_reject": False,
        }

    return {
        "posting_language": posting_language,
        "language_decision": "unknown",
        "language_reason": None,
        "english_environment_signal": False,
        "language_reject": False,
    }
