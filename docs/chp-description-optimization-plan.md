# CHP ingestion and description optimization plan

Reviewed September 23, 2026 against commit `8ba4970`. This records the original proposal. See [implementation and operations](chp-description-operations.md) for the resulting behavior and rollout controls.

## Recommendation

Use CHP's public XML feed for collection, maintain a compact set of source-backed incident facts, and generate descriptions only when those facts materially change. Measure and explicitly reduce the model's reasoning effort before considering a model replacement.

Keep the existing immediate factual fallback and asynchronous enrichment. Those already let incidents appear without waiting for AI.

## Verified findings

### CHP offers the data in one structured download

I retrieved [CHP's public XML feed](https://media.chp.ca.gov/sa_xml/sa.xml) and compared it with the [Border Communications Center page](https://cad.chp.ca.gov/traffic.aspx?__EVENTTARGET=ddlComCenter&ddlComCenter=BCCC).

The downloaded XML was 273,314 bytes, with 16 BCCC records matching the 16 table rows in the web snapshot. Both included a Media Log and a freeway-service-patrol record. This verifies a single snapshot's list coverage, not continuous availability or complete detail parity.

The XML supplies:

- `Dispatch ID="BCCC"` for regional selection.
- Full incident IDs, such as `260923BC0650`, and distinct FSP IDs.
- Full dates and times, avoiding inference from the current date.
- Raw incident codes and labels, location, location description, and area.
- `LATLON` values such as `32712902:117118422`.
- Dated narrative entries under `LogDetails/details` and separate unit entries under `LogDetails/units`.

The observed coordinate example corresponds to approximately 32.712902, -117.118422. Validate scale, longitude convention, geographic bounds, missing values, and comparison against known incident locations before using this conversion in production.

Caltrans documents the public MediaCAD website and XML feed in its [2026 Transportation Management Centers manual](https://dot.ca.gov/-/media/dot-media/programs/traffic-operations/documents/trafficops/202602-tom-ch-110-transportation-mgmt-centers-a11y.pdf).

### Current collection does unnecessary work and can lose facts

`backend/scrapers/chp.py:26` fetches a list and then a separate detail POST for every non-Media-Log row, with five workers. The monitor sleeps 15 seconds after each completed cycle, so the actual interval is processing time plus 15 seconds.

In this snapshot, that means 16 HTTP requests per cycle: one list plus 15 detail requests. XML could supply those records in one request, a 93.75% request-count reduction for this example. This is not a measured bandwidth, latency, or AI-token saving.

Other issues:

- Detail requests rely on row indexes and ASP.NET form state, including a hardcoded viewstate generator.
- A failed detail request returns an empty dictionary. The table's `Details` label can then remain as the incident's detail content; a missing detail table produces an empty list. Persistence can replace previously useful details with either result and request another summary.
- Coordinate extraction scans the whole HTML response and only accepts exactly six decimal places.
- BCCC includes Temecula records. Preserve existing coverage during migration; a San Diego County-only filter would be a separate product decision.
- CHP and FSP records can describe the same location/event. Do not merge solely by location or remove all FSP records: some may carry unique information.

### Most avoidable AI work comes from refresh policy

`backend/monitor.py:46`, `:147`, `:225`, and `:390` show that:

- New active incidents schedule enrichment.
- Any change in serialized details schedules another call with the entire timeline.
- Different versions of the same incident can queue independently. A stale result is rejected at database write time, after tokens have already been spent.
- Type or location changes without changed details do not independently trigger enrichment, allowing stale descriptions.
- Disappearing incidents with details receive a final call using stored facts, often the same facts already summarized. This path also waits in the monitor cycle.
- Pending failures are retried on subsequent monitor cycles without application-level backoff or a next-attempt timestamp.

### The model defaults are consequential

`backend/llm.py:80` sends only the model and messages. It does not specify reasoning effort, an output ceiling, or a response schema. It also discards provider usage information. The printed call counter includes mock and unconfigured paths, so it is not a reliable count of paid calls.

The live [OpenRouter models API](https://openrouter.ai/api/v1/models), retrieved during this review, reports for `z-ai/glm-5.3-flash`:

```json
{
  "mandatory": true,
  "default_enabled": true,
  "supported_efforts": ["max", "high", "low"],
  "default_effort": "max"
}
```

Use explicit low reasoning as the first benchmark. Do not attempt to disable reasoning for this model. Actual billed reasoning in this application is unknown until usage is recorded. Hiding reasoning does not avoid its cost, and completion limits can include both reasoning and visible output; an overly small limit may produce an empty response and more retries. See [OpenRouter reasoning documentation](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

## Proposed pipeline

```text
CHP XML snapshot
  -> validate freshness, structure, coverage, and record identity
  -> persist raw source events and current incident fields
  -> normalize and select relevant facts
  -> fingerprint those facts and the description-policy version
  -> unchanged: retain description
  -> simple: render a factual template locally
  -> complex/material change: queue latest version for AI
  -> validate response and save only against the matching version
```

### 1. Add measurement and explicit model controls

Record incident identity, trigger reason, model/provider, prompt version, input hash, input tokens, completion tokens, reasoning tokens, cached tokens, reported cost, duration, finish reason, validation result, and whether the result was saved or discarded as stale. Count real attempts separately from fallback renders. Missing usage must remain unknown, not zero.

[OpenRouter supplies usage and cost in responses](https://openrouter.ai/docs/cookbook/administration/usage-accounting); no separate billing request is normally needed. Reasoning is a component of completion tokens, so do not add it twice in cost accounting.

Benchmark `low` reasoning with several completion ceilings, for example 512, 1,024, and 2,048 tokens. Select the smallest ceiling that retains quality and reliable completion on difficult incidents. These are experiment settings, not a claim about GLM's required budget.

Use a strict JSON schema where the selected provider supports it, with local validation of summary length and field types. Check `finish_reason` before accepting output. Keep the under-200-character description target, but allow room for reasoning in the generation budget. [Structured-output guidance](https://openrouter.ai/docs/guides/features/structured-outputs) explains compatible provider selection.

### 2. Stop redundant calls and preserve source facts

Implement a durable job per incident, with desired fact version, completed version, attempt count, next-attempt time, and a worker lease. Updates replace the pending desired version instead of adding an unbounded sequence of jobs.

Before each provider call, reload the newest facts and check whether that version is already summarized. After the call, retain the version guard so stale output cannot replace newer content. Include type, location, meaningful narrative facts, and policy/model version in the fingerprint; do not key only on the raw details list.

Coalesce routine updates over an initial 30–60-second window, with a maximum wait to prevent starvation. Known lane closures, reopening reports, wrong-way reports, and other urgent material changes bypass the delay. Unknown new narrative text should conservatively trigger review/enrichment rather than being silently ignored.

Distinguish unavailable details from a successfully observed empty timeline. Keep the last successful facts and mark them stale on collection failure. A formatting change or unit assignment alone should not create a new description version.

Remove the unconditional closing-summary call. Keep the existing description when an incident leaves the source, and update its listing status separately. Disappearance is not evidence that lanes reopened or an emergency ended. If meaningful facts remain unsummarized at disappearance, finish that latest version asynchronously using facts and a version check, without inventing a resolution.

Add bounded exponential retry backoff with jitter, handling provider rate-limit guidance and separating retryable failures from invalid configuration. Maintain the factual fallback while enrichment is unavailable. Make retries fair so repeatedly failing old jobs cannot monopolize the queue.

### 3. Replace the CHP scraper behind a reversible setting

Build an XML adapter that returns the existing incident shape while preserving full native identity and raw type in additional fields. Parse quoted values, explicit timestamps, narrative order, and units separately.

Run it in comparison mode before switching ingestion. Compare incident membership, coordinates, type, dates, and details. Start with a configurable 30–60-second collection interval and measure freshness; the desktop page's 60-second auto-refresh does not prove the XML feed's publishing cadence. Use HTTP validators when actually provided and retain the last valid snapshot on invalid responses.

Preserve the existing safeguards against deactivation after failed collection. Require a valid, complete BCCC snapshot before advancing disappearance state, and consider two successful missing observations to avoid flicker. An HTTP 200 or an empty result by itself is insufficient evidence of a healthy empty feed.

Do not simply replace existing public IDs with native XML IDs: likes, comments, URLs, and active-state comparisons rely on current identity conventions. Add a native-ID mapping and reconcile existing records first; quarantine ambiguous mappings rather than guessing. Full CHP IDs also distinguish FSP from regular incidents and improve midnight handling.

Keep HTML collection as a bounded fallback, with the same identity mapping and partial-failure behavior. Do not let disagreement between adapters silently deactivate records.

### 4. Give AI a compact, factual input

Keep raw events for audit/debugging, but derive a separate description input:

- Incident category and reported uncertainty.
- Road, direction, cross street, and relevant area.
- Latest supported lane/shoulder status.
- Relevant vehicle, fire, injury-report, or hazard facts.
- A small selection of supporting narrative entries when normalization is uncertain.

Normalize whitespace, repeated shared-message wrappers, and exact duplicates. Exclude administrative unit movements and towing-company contact details from the prompt while preserving useful tow/obstruction facts. Never remove a line solely because it contains administrative wording: it may also contain a closure or correction.

Process events chronologically. Retain negation, uncertainty, and superseding corrections. Use a small reviewed glossary for common abbreviations; leave unknown codes uninterpreted. Preserve raw collision subtypes separately from the broad display category—the database currently collapses several to `Traffic Collision`.

The XML contains an instructive pattern: an older entry reports a blocked lane, a newer entry reports vehicles on the shoulder, and a later FSP message closes its own related record. The last message is not automatically the best summary, and FSP closure is not confirmation that the CHP incident has ended.

Use templates for genuinely simple records with little narrative. For complex incidents, send current source-backed facts rather than the previous AI summary plus new lines; repeatedly summarizing generated prose risks accumulating errors. Set a measured input budget with priority for contradictions and material updates, not a blind last-N-lines cutoff.

### 5. Improve severity and wording separately

The present severity rubric combines traffic impact, emergency response, vehicle count, and injury reports. It can rate routine emergency response as high, any injury/multiple vehicles as critical, and it forces every SIG-containing type to 5.

Define an explicit application severity policy using source-backed facts, including unknown/null when evidence is insufficient. Evaluate deterministic scoring for recognized facts; use AI for prose and ambiguous narrative interpretation. Keep reported injury categories distinct from confirmed injuries, and treat SIGALERT status as its own fact. Version and review score changes because the UI displays these labels prominently.

Add decorative emoji in the UI if desired, so the model focuses on a short factual sentence. Avoid duplicate location strings and empty `None` fields in the prompt. Prompt shortening is useful after fixing repeat calls and excessive reasoning.

## Delivery order and acceptance checks

| Delivery | Files/areas | Evidence required |
| --- | --- | --- |
| A: usage and controlled reasoning | `backend/llm.py`, `backend/config.py`, metrics | Real token/cost breakdown; low-effort quality and truncation comparison |
| B: refresh policy and failure handling | `backend/monitor.py`, `backend/db.py`, scraper result contract | Unchanged facts cause zero calls; latest work survives restart; stale jobs skipped before calls; failure preserves details |
| C: XML adapter and identity mapping | `backend/scrapers/chp.py`, persistence, fixtures | Repeated parity checks; correct dates/coordinates; no duplicate public incidents or lost interactions |
| D: fact selection, templates, scoring | `backend/descriptions.py`, new normalization module, LLM input | Negations/corrections preserved; simple cases need zero AI; ambiguous cases retain evidence |

Use a replay set of incident histories, including rapid updates, changing collision types, reversed lane status, FSP duplicates, missing coordinates, malformed XML, explicit empty feeds, partial responses, midnight crossings, and provider outages. Extend the existing monitor/description tests and add scraper fixtures. Runtime mocks alone cannot validate prose quality or billed reasoning; use a bounded live-model evaluation during implementation.

Collect a representative baseline, then compare over the same incident histories: tokens and cost per incident lifecycle, calls per incident, stale-result waste, description latency, missing material facts, unsupported claims, and collection failures. Run comparison collectors without duplicate AI generation. Use separate flags for the XML adapter, scheduling policy, and model settings so each can be rolled back independently.

Savings should be reported from those measurements. Illustratively, an incident with one initial call, six detail refreshes, and one closing call uses eight calls today. If only one refresh is material, two calls would be a 75% call reduction before input reduction or reasoning changes. This is an example, not a production savings estimate.

No production usage logs or paid model calls were inspected in this review. The local database predates the current code and was not used to infer current traffic volume or spend.
