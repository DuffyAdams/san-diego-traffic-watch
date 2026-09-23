"""Conservative source normalization; unknown narrative always remains evidence."""

import hashlib
import json
import re

from .config import DESCRIPTION_COMPACT, DESCRIPTION_INPUT_CHARS

POLICY_VERSION = "facts-v1"
_WRAPPER = re.compile(r"\[(?:\d+|Shared|Notification|CHP|FSP|Appended, [^\]]+)\]", re.I)
_TIME = re.compile(r"^\[(?:\d{4}-\d\d-\d\d[ T])?\d{1,2}:\d\d(?::\d\d)?(?:\s*[AP]M)?\]\s*", re.I)
_ADMIN = re.compile(
    r"(?:Unit (?:At Scene|Enroute|Assigned|Cleared)|"
    r"\[FSP\] has closed their incident \[[^\]]+\]|"
    r"(?:Service Area|Division|Neighborhood):.*)", re.I
)
_PHONE = re.compile(r"\b\d{3}[- .]\d{3}[- .]\d{4}\b")
_IMPACT = re.compile(r"\b(?:block\w*|clos\w*|reopen\w*|lanes? open|wrong.way|fire|injur\w*|extricat\w*|overturn\w*|roof|shoulder|RHS)\b", re.I)


def text(value):
    return " ".join(value.split()) if isinstance(value, str) else ""


def detail_list(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            value = [value]
    return [text(v) for v in value if text(v)] if isinstance(value, list) else []


def narrative_lines(value):
    """Inputs are oldest first. Remove only known bookkeeping, not unknown codes."""
    result = []
    for raw in detail_list(value):
        line = _TIME.sub("", raw)
        # Check before removing wrappers so FSP closure isn't mistaken for a road closure.
        check = re.sub(r"^(?:\[\d+\]\s*)+", "", line)
        if _ADMIN.fullmatch(check):
            continue
        if "[Rotation Request Comment]" in line and not _IMPACT.search(line):
            continue
        line = _WRAPPER.sub("", line)
        line = _PHONE.sub("", line)
        line = text(line)
        if not line or line.casefold() in {"details", "none", "n/a"}:
            continue
        # Last occurrence wins: A -> B -> A must not become A -> B.
        result = [old for old in result if old.casefold() != line.casefold()]
        result.append(line)
    return result


def incident_facts(data):
    def field(a, b):
        return text(data.get(a) or data.get(b))
    facts = {
        "source": field("Source", "source"),
        "type": field("RawType", "raw_type") or field("Type", "type"),
        "location": field("Location", "location"),
        "area": field("Neighborhood", "neighborhood") or field("Area", "area") or field("City", "city"),
    }
    facts["type"] = re.sub(r"^[A-Za-z0-9]+-", "", facts["type"])
    cross = field("Location Desc.", "location_desc")
    if cross and cross.casefold() != facts["location"].casefold():
        facts["cross_street"] = cross
    details = data.get("Details", data.get("details", []))
    facts["reports_oldest_first"] = narrative_lines(details) if DESCRIPTION_COMPACT else detail_list(details)
    return {key: value for key, value in facts.items() if value}


def fact_hash(facts):
    value = json.dumps(facts, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256((POLICY_VERSION + value.casefold()).encode()).hexdigest()


def compact_input(facts):
    """Bound narrative characters, favoring impact/corrections and recent reports.

    Keep chronological order and signal omissions. The budget is characters,
    not a tokenizer estimate; real token usage is recorded from the provider.
    """
    lines = facts.get("reports_oldest_first", [])
    available = DESCRIPTION_INPUT_CHARS
    selected = {}
    ranked = sorted(range(len(lines)), key=lambda i: (bool(_IMPACT.search(lines[i])), i), reverse=True)
    for i in ranked:
        line = lines[i]
        if len(line) <= available:
            selected[i] = line
            available -= len(line)
    result = {k: v for k, v in facts.items() if k != "reports_oldest_first"}
    result["reports_oldest_first"] = [selected[i] for i in sorted(selected)]
    if len(selected) < len(lines):
        result["omitted_reports"] = len(lines) - len(selected)
    return result


def urgent_change(previous, current):
    old_lines = set(previous.get("reports_oldest_first", []))
    new_lines = set(current.get("reports_oldest_first", [])) - old_lines
    return any(_IMPACT.search(line) for line in new_lines) or (
        previous.get("type") != current.get("type")
        and bool(_IMPACT.search(current.get("type", "")))
    )


def severity_for(facts):
    """Traffic-impact policy v1: score only explicit, narrow evidence.

    Dispatch injury categories, unit presence, and SIGALERT alone do not prove
    severity. Unknown is intentional. Ambiguous/negated clauses are not scored.
    """
    severity = None
    for line in facts.get("reports_oldest_first", []):
        value = line.upper()
        if re.search(r"\b(?:NO|NOT|NEG|POSS|POSSIBLE|UNK|UNKNOWN|IF|INQ|EXCEPT)\b|\?", value):
            if re.search(r"\b(?:LANES?|ROAD|BLOCK\w*|CLOS\w*|REOPEN\w*)\b", value):
                severity = None
            continue
        if re.search(r"\b(?:ALL LANES (?:ARE )?(?:OPEN|REOPENED)|ROAD (?:IS )?REOPENED|EVERYTHING ON RHS|ALL VEHS? ON (?:THE )?(?:RHS|SHOULDER))\b", value):
            severity = None if re.search(r"\b(?:BLOCKED|CLOSED)\b", value) else 1
            continue
        if re.search(r"\b(?:ALL LANES (?:ARE )?(?:BLOCKED|CLOSED)|ROAD (?:IS )?CLOSED|FULL (?:ROAD )?CLOSURE)\b", value):
            severity = 4
        elif re.search(r"\b(?:MULTIPLE LANES (?:ARE )?BLOCKED|[2-9] LANES (?:ARE )?BLOCKED)\b", value):
            severity = 3
        elif re.search(r"\b(?:BLOCKING #?\d+ (?:LN|LANE)|(?:#?\d+ (?:LN|LANE)|ONE LANE) (?:IS )?BLOCKED|1125 #\d+ LN)\b", value):
            severity = 2
    return severity


def template_description(facts):
    """Only category/location records qualify; narrative requires interpretation."""
    if facts.get("reports_oldest_first"):
        return None
    kind = re.sub(r"^\d+[A-Za-z]*\s*[-–]\s*", "", facts.get("type", "Incident"))
    # Templates are deliberately restricted to plain-language categories.
    kinds = {"traffic hazard": "Traffic hazard", "maintenance": "Maintenance",
             "assist ct with maintenance": "Road maintenance", "car fire": "Vehicle fire",
             "traffic collision": "Traffic collision", "wrong way driver": "Wrong-way driver",
             "road/weather conditions": "Road or weather conditions"}
    if kind.casefold() not in kinds:
        return None
    location = facts.get("location", "")
    result = f"{facts.get('source', 'Source')} reports {kinds[kind.casefold()].lower()}"
    if location:
        result += f" at {location}"
    result += "."
    return result if len(result) < 200 else None
