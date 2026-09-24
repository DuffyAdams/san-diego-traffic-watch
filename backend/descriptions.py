"""Descriptions built only from supplied incident facts, without a network call."""

import json
import re


PLACEHOLDERS = frozenset({
    "", "no description available", "traffic incident reported.",
    "n/a", "none", "null", "unknown",
})


def usable_description(value):
    return isinstance(value, str) and value.strip().lower() not in PLACEHOLDERS


def _text(value):
    if not isinstance(value, str):
        return ""
    value = " ".join(value.split()).strip()
    return "" if value.lower() in PLACEHOLDERS else value


def _chp_description(data):
    """Conservative offline prose, not an attempted dispatch-code translator.

    Only whole, recognized factual statements are rendered. Unknown shorthand
    remains in Details and in the model input, never guessed or pasted publicly.
    """
    from .incident_facts import narrative_lines

    kind = _text(data.get("RawType") or data.get("raw_type") or data.get("Type") or data.get("type"))
    kind = re.sub(r"^[A-Za-z0-9]+-", "", kind)
    kinds = {
        "trfc collision-no inj": "Traffic collision with no injuries reported",
        "trfc collision-unkn inj": "Traffic collision with unknown injuries reported",
        "trfc collision-1141 enrt": "Traffic collision reported",
        "traffic collision": "Traffic collision reported",
        "traffic hazard": "Traffic hazard reported",
        "hit and run no injuries": "Hit-and-run with no injuries reported",
        "hit and run with injuries": "Hit-and-run with injuries reported",
        "hit and run unknown injuries": "Hit-and-run with unknown injuries reported",
        "car fire": "Vehicle fire reported",
        "wrong way driver": "Wrong-way driver reported",
        "road/weather conditions": "Road or weather conditions reported",
        "assist ct with maintenance": "Road maintenance reported",
        "disabled veh occupied": "Disabled vehicle reported",
        "disabled veh unoccupied": "Unoccupied disabled vehicle reported",
        "sigalert": "Traffic alert reported",
    }
    result = kinds.get(kind.casefold(), "Traffic incident reported")
    location = _text(data.get("Location") or data.get("location"))
    if location:
        result += f" at {location}"
    result = result.rstrip(". ") + "."
    statements = []
    # Full matches deliberately refuse mixed fact/admin lines and unknown codes.
    plain_fact = re.compile(
        r"(?:No injuries(?: reported)?|Injuries (?:unknown|reported)|"
        r"Road (?:is )?(?:not closed|closed|reopened)|"
        r"All lanes (?:are )?(?:open|blocked|closed|reopened)|"
        r"(?:One|[1-9]) lanes? (?:is |are )?(?:not blocked|blocked)|"
        r"Vehicle (?:is )?on (?:the )?shoulder)", re.I
    )
    for line in narrative_lines(data.get("Details", data.get("details"))):
        line = line.rstrip(". ")
        if plain_fact.fullmatch(line):
            statements.append(line.capitalize())
    if statements:
        result += " Reported details (oldest first): " + "; ".join(statements) + "."
    return result


def source_description(data):
    """Accept either a scraper snapshot or a stored incident row.

    Call types are reports, not confirmed outcomes. Do not infer injuries,
    closures, arrests, severity, or resolution from a dispatch category/status.
    """
    def field(scraper_key, stored_key):
        return _text(data.get(scraper_key) or data.get(stored_key))

    source = field("Source", "source")
    if source.upper() == "CHP":
        return _chp_description(data)
    kind = field("Type", "type")
    # SDSO supplies the definition after its code; never guess unknown codes.
    kind = re.sub(r"^\d+[A-Za-z]*\s*[-–]\s*(?=\S)", "", kind)
    if kind.isupper():
        kind = kind.capitalize()
        kind = re.sub(r"\b(dui|ems|cpr|chp)\b", lambda m: m[0].upper(), kind, flags=re.I)
    kind = kind or "Incident"
    location = field("Location", "location")
    neighborhood = field("Neighborhood", "neighborhood")
    city = field("City", "city")
    area = neighborhood or city
    if area.casefold() in {"san diego", "san diego county"}:
        area = ""
    if area.isupper():
        area = area.title()

    description = kind
    if location:
        description += f" at {location}"
    if area and area.casefold() != location.casefold():
        description += f", {area}" if location else f" in {area}"
    description = description.rstrip(". ") + "."

    details = data.get("Details", data.get("details")) or []
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except (ValueError, TypeError):
            pass
    if isinstance(details, str):
        details = [details]
    if not isinstance(details, list):
        details = []
    useful = []
    for detail in details:
        detail = _text(detail)
        # Administrative coverage areas are not an incident narrative.
        if not detail or re.match(r"^(Service Area|Division|Neighborhood):", detail, re.I):
            continue
        if detail not in useful:
            useful.append(detail)
    if useful:
        description += " Reported details: " + "; ".join(useful[-2:]).rstrip(". ") + "."
    return description


def dispatch_log_description(value):
    """Recognize dispatch formatting/bookkeeping, not ordinary road-status prose."""
    return isinstance(value, str) and bool(re.search(
        r"\[(?:\d|Shared\b|Notification\b|Appended\b|CHP\b|FSP\b|Rotation Request)|"
        r"\bUnit (?:At Scene|Enroute|Assigned|Cleared)\b|"
        r"\b(?:CHP|FSP) (?:has )?closed (?:their )?incident\b|"
        r"\b[A-Z]\d{2,3}-\d{2,3}\b", value, re.I
    ))


def incident_description(data):
    """Read repair is network-free; raw evidence remains untouched in Details."""
    description = data.get("description")
    if (data.get("Source") or data.get("source") or "").upper() == "CHP":
        if data.get("description_origin") == "source" or dispatch_log_description(description):
            return source_description(data)
    if not usable_description(description):
        return source_description(data)
    description = description.strip()
    cleaned = re.sub(r"^(?:CHP|SDPD|SDSO|SDFD)\s+(?:reports?[: ]|reported\s)\s*", "", description, flags=re.I)
    cleaned = re.sub(r"(?:\s+in|,)\s+San Diego(?: County)?(?=[,.;:!?]|$)", "", cleaned, flags=re.I)
    return cleaned[:1].upper() + cleaned[1:] if cleaned != description else description
