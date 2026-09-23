"""Map native CHP identities onto existing public IDs without moving interactions."""

import sqlite3

from .sqlite_utils import sqlite_connection
from .scrapers import ScraperError
from .incident_facts import incident_facts


def resolve_chp_identities(incidents, db_file):
    result = []
    reserved = set()
    with sqlite_connection(db_file, row_factory=sqlite3.Row) as conn:
        for original in incidents:
            incident = dict(original)
            native = incident.get("NativeID")
            date = incident.get("Date")
            legacy = str(incident.get("No.", ""))
            if not native:
                # HTML fallback retains existing short IDs. Refuse ambiguity if a
                # previous collision caused multiple native records with that suffix.
                matches = conn.execute("SELECT incident_no FROM incidents WHERE source='CHP' AND date=? AND (incident_no=? OR native_id LIKE ?)",
                                       (date, legacy, '%' + legacy)).fetchall()
                if len(matches) > 1:
                    raise ScraperError("Ambiguous CHP HTML identity; keeping last valid source state")
                if matches:
                    incident["No."] = matches[0]["incident_no"]
            else:
                mapped = conn.execute("SELECT incident_no, date FROM incidents WHERE source='CHP' AND native_id=?", (native,)).fetchone()
                if mapped:
                    incident["No."] = mapped["incident_no"]
                    incident["Date"] = mapped["date"]
                else:
                    existing = conn.execute("SELECT * FROM incidents WHERE incident_no=? AND date=?", (legacy, date)).fetchone()
                    if existing and existing["native_id"] == native:
                        incident["No."] = legacy
                    elif existing and existing["native_id"] is None and existing["source"] == "CHP":
                        # Legacy row indexes/short numbers are not enough evidence.
                        same_location = (existing["location"] or "").casefold().split() == (incident.get("Location") or "").casefold().split()
                        same_time = (existing["timestamp"] or "")[:16] == (incident.get("Timestamp") or "")[:16]
                        if not (same_location and same_time):
                            raise ScraperError("Ambiguous legacy CHP mapping; keeping last valid source state")
                        incident["No."] = legacy
                    elif existing or (legacy, date) in reserved:
                        incident["No."] = native
                    else:
                        # New public IDs retain the native date and FSP namespace.
                        incident["No."] = native
            key = str(incident["No."]), incident["Date"]
            if key in reserved:
                raise ScraperError("Duplicate CHP public identity")
            reserved.add(key)
            result.append(incident)
    # Correlate only a present FSP record with strong source evidence. Preserve
    # its row/interactions, but hide it from the main feed while its parent exists.
    native_records = {r.get("NativeID"): r for r in result if r.get("NativeID")}
    for native, child in native_records.items():
        child["RelatedIncidentID"] = None
        if "FSP" not in native:
            continue
        matches = []
        child_facts = incident_facts(child)
        child_lines = set(child_facts.get("reports_oldest_first", []))
        for parent_native, parent in native_records.items():
            if "FSP" in parent_native:
                continue
            if parent.get("Location", "").casefold() != child.get("Location", "").casefold():
                continue
            parent_facts = incident_facts(parent)
            explicit = any(native in line for line in parent.get("Details", []))
            same_details = len(child_lines) >= 2 and child_lines == set(parent_facts.get("reports_oldest_first", []))
            same_coords = child.get("Latitude") is not None and child.get("Longitude") is not None and all(child.get(k) == parent.get(k) for k in ("Latitude", "Longitude"))
            if explicit or (same_details and same_coords and child_facts.get("type") == parent_facts.get("type")):
                matches.append(parent)
        if len(matches) == 1:
            child["RelatedIncidentID"] = matches[0]["No."]
    return result
