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


def source_description(data):
    """Accept either a scraper snapshot or a stored incident row.

    Call types are reports, not confirmed outcomes. Do not infer injuries,
    closures, arrests, severity, or resolution from a dispatch category/status.
    """
    def field(scraper_key, stored_key):
        return _text(data.get(scraper_key) or data.get(stored_key))

    source = field("Source", "source")
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
    if area.isupper():
        area = area.title()

    description = f"{source + ' report: ' if source else ''}{kind}"
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


def incident_description(data):
    """Preserve substantive summaries, otherwise describe the source facts."""
    description = data.get("description")
    return description.strip() if usable_description(description) else source_description(data)
