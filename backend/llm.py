"""
LLM integration for generating incident descriptions and severity scores.
Uses OpenRouter with the configured incident-summary model.
"""

import json

from .config import (
    IMMEDIATE_LLM_MODEL,
    LLM_API_CONFIGURED,
    TESTMODE,
    llm_client,
    print_lock,
)
from .logging_utils import safe_print
from .descriptions import source_description, usable_description

# Track total LLM calls (thread-safe via print_lock)
_call_count = 0


def generate_description(data, raise_on_error=False):
    """Generate a plain-English summary and 1–5 severity score for an incident.

    ``raise_on_error`` lets durable background jobs retain their pending marker
    when the provider is unavailable instead of treating fallback text as a
    completed enrichment.
    """
    global _call_count
    with print_lock:
        _call_count += 1
        count = _call_count
    safe_print(f"Immediate LLM calls: {count}")

    is_sig_alert = bool(data.get("Type")) and "SIG" in data.get("Type", "").upper()

    if TESTMODE:
        return (f"Mock incident summary for {data.get('Location')}.", 5 if is_sig_alert else 2)
    if not LLM_API_CONFIGURED:
        if raise_on_error:
            raise RuntimeError("LLM API is not configured")
        return (source_description(data), 5 if is_sig_alert else None)

    details = data.get("Details") or []
    if isinstance(details, str):
        details = [details]
    prompt = (
        f"Neighborhood: {data.get('Neighborhood')}\n"
        f"Location: {data.get('Location')} - {data.get('Location Desc.')}\n"
        f"Type: {data.get('Type')}\n"
        f"Details: {', '.join(str(detail) for detail in details)}"
    )
    system_prompt = (
        "You are a traffic incident analyst. Respond ONLY with a valid JSON "
        "object, no markdown or extra text.\n"
        "The JSON must have exactly two keys:\n"
        '  "summary": a factual, tweet-length summary (under 200 chars) with related emojis. '
        "Use only supplied facts; dispatch categories are reports, not confirmed outcomes. "
        "Do not invent injuries, arrests, closures, causes, or resolution. "
        "No warnings, advice, hashtags, or extra commentary.\n"
        '  "severity": an integer from 1 to 5 based on this scale:\n'
        "    1 = minor (very small delay, single vehicle stopped, should clear soon)\n"
        "    2 = low (some lane impact, slowdowns)\n"
        "    3 = moderate (multiple lanes impacted or prolonged delay)\n"
        "    4 = high (road closed, serious collision, emergency response on scene)\n"
        "    5 = critical (major incident, long-duration closure, multiple vehicles or injury)\n"
    )
    user_message = f"Analyze this traffic incident and return JSON.\n{prompt}"

    try:
        response = _call_llm(system_prompt, user_message)
        return _parse_response(response, is_sig_alert)
    except Exception as e:
        safe_print(f"Error generating description: {e}")
        if raise_on_error:
            raise
        return (source_description(data), 5 if is_sig_alert else None)


def _call_llm(system_prompt, user_message):
    """Call the configured incident-summary model."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    return llm_client.chat.completions.create(
        model=IMMEDIATE_LLM_MODEL, messages=messages
    )


def _parse_response(response, is_sig_alert):
    """Reject unusable output so failures retain their durable retry marker."""
    raw = response.choices[0].message.content
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Empty incident summary")
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    brace_start, brace_end = cleaned.find("{"), cleaned.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        cleaned = cleaned[brace_start : brace_end + 1]
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict) or not usable_description(parsed.get("summary")):
        raise ValueError("Missing incident summary")
    sev = parsed.get("severity")
    severity = sev if type(sev) is int and 1 <= sev <= 5 else None
    return parsed["summary"].strip(), 5 if is_sig_alert else severity
