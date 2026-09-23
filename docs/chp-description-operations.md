# CHP collection and description operations

The implementation replaces per-incident CHP detail requests with the public XML feed, preserves source evidence, and maintains one durable description job per incident. Schema additions run through `backend.db.init_db()` at normal startup. Existing public IDs, likes, and comments remain intact; new XML incidents use full native IDs. Do not run a second ingest process against production merely to compare collectors.

## Settings

Set these in the server environment or its existing `.env`, then restart the backend. Credentials continue to use `GPT_KEY`; this change does not modify them.

| Setting | Default | Behavior |
| --- | --- | --- |
| `CHP_COLLECTOR` | `xml` | `xml` uses the structured feed; `html` uses the old website; `compare` serves HTML while logging XML/list/detail/coordinate differences without extra AI jobs. |
| `CHP_HTML_FALLBACK` | `true` | Use HTML when XML is unavailable. Failed details preserve stored evidence. |
| `CHP_POLL_SECONDS` | `30` | Minimum interval between CHP collections; locally cached reads do not count as new disappearance observations. |
| `CHP_MISSING_POLLS` | `2` | Fresh, successful missing observations before marking a CHP incident inactive. |
| `DESCRIPTION_COMPACT` | `true` | Remove known administrative noise and duplicates before fingerprinting and building input. `false` keeps raw narrative in the fact representation. |
| `DESCRIPTION_TEMPLATES` | `true` | Render recognized simple category/location reports without an AI call. |
| `DESCRIPTION_DEBOUNCE_SECONDS` | `30` | Delay routine refreshes so later updates replace pending work. Set `0` for immediate scheduling. |
| `DESCRIPTION_MAX_WAIT_SECONDS` | `90` | Maximum coalescing wait during continuous updates. |
| `DESCRIPTION_INPUT_CHARS` | `2400` | Narrative character budget, prioritizing impact reports and recency. This is not a claimed token count. |
| `DESCRIPTION_MAX_ATTEMPTS` | `5` | Stop failed enrichment after this many attempts for a version. |
| `LLM_REASONING_EFFORT` | `low` | GLM supports `low`, `high`, or `max`; reasoning cannot be disabled. |
| `LLM_MAX_TOKENS` | `2048` | Combined completion/reasoning budget; configurable after evaluation. |
| `LLM_TIMEOUT_SECONDS` | `45` | Explicit request timeout. SDK retries are disabled; the durable queue controls retry/backoff. |

The model remains `z-ai/glm-5.3-flash`. JSON schema routing requires provider support, and responses are locally checked for normal completion, allowed fields, nonempty prose, and the under-200-character limit.

## Deployment sequence

1. Back up the production database using the existing backup procedure. Run the regression suite before deploying.
2. Deploy and restart the backend to apply additive migrations and start the new queue. Start with `CHP_COLLECTOR=compare` if operational comparison is preferred. This mode still performs the older HTML detail requests, so it is a temporary validation mode.
3. Inspect comparison logs over changing incidents and a quiet period, then select `CHP_COLLECTOR=xml`. A changed feed between two requests can legitimately produce a short-lived difference. Missing or malformed BCCC snapshots fail collection rather than clearing incidents.
4. Inspect the metrics dashboard's AI usage tiles and `llmUsage` in `/api/dashboard_metrics`. AI figures always cover the last 24 hours, independently of the incident chart range. Queue counts and stored-template counts are current totals.
5. Compare cost and tokens per incident lifecycle, material-update latency, queue failures, and unsupported summary claims. The monitoring loop still runs other sources on their existing interval; CHP has its own minimum poll interval.

To revert collection independently, set `CHP_COLLECTOR=html`. To remove routine coalescing, set `DESCRIPTION_DEBOUNCE_SECONDS=0`. To change model reasoning or completion budget, use the LLM settings above. Rolling application code back leaves additive database columns/tables in place; take a backup first and do not drop them as part of ordinary rollback.

## Queue and accounting

Each job contains the newest desired fact hash, source payload, completed hash, due time, attempt count, status, and lease. Jobs survive restarts. Two workers drain bounded portions of the queue; updates to a leased incident wait for the in-flight attempt to finish. Superseded claims are skipped before calling the provider when possible, and stale results cannot overwrite newer source facts.

Initial incidents and recognized urgent changes are eligible immediately. Routine changes coalesce for up to 90 seconds by default, plus worker/monitor scheduling time. Material changes immediately replace an obsolete AI description with a factual source fallback and update deterministic severity, so provider downtime does not leave an old lane-closure claim as the current description.

Disappearance updates listing status without generating a closing summary. Existing unfinished work can finish after an incident disappears; it uses the last real facts and never fabricates reopening. Fully closed records arriving from a source do not create new jobs.

Retries use exponential backoff and jitter and respect numeric `Retry-After` values. Invalid requests/authentication failures stop that job immediately. Missing API configuration does not spin the queue. After correcting configuration, explicitly requeue failed work:

```sh
python -m scripts.description_queue
python -m scripts.description_queue --retry-failed
```

`llm_attempts` records actual provider attempts, source identity/hash, trigger, model, prompt-policy version, reasoning effort, completion budget, provider/generation ID, token/cost fields, latency, finish reason, and saved/stale/failed outcome. Template and mock paths do not inflate paid attempt counts. Unknown usage/cost remains NULL. Reasoning is already included in completion tokens and must not be added again when calculating total tokens or cost. The dashboard labels partial accounting rather than reporting missing usage as zero.

Source snapshots are retained in `incident_source_events` only when their contents change. These contain the dispatch history, including administrative events omitted from AI input. Set an operational retention policy for this table and `llm_attempts` as data volume grows; no historical records are deleted by this change.

## Identity and correlated FSP records

Native XML IDs include date and FSP namespace. Existing short public IDs are reused only when date, location, and timestamp match; ambiguous migration or fallback identities fail the collection rather than overwrite the wrong incident. The native ID is then persisted for future matching. Ambiguous mappings require inspecting the source record and existing row before repair.

A present FSP record is correlated with a present regular CHP record only with matching location plus an explicit native-ID reference, or matching coordinates, type, and at least two identical normalized narrative entries. Multiple possible parents remain separate. The related row and its interactions remain stored; it is omitted from the main feed and incident statistics while related. Unique FSP reports remain visible and eligible for summaries. BCCC coverage, including Temecula, is preserved.

## Description and severity policy

Raw incident labels remain stored alongside normalized display categories. Administrative wrappers and exact duplicate statements do not trigger new summaries. Unknown narrative is retained. Newer statements retain chronology; FSP closure and unit status are not road-reopening evidence. Input selection signals omitted narrative rather than suggesting it is complete.

Severity currently scores only narrow, explicit traffic-impact evidence: 1 for explicit full reopening/vehicles moved to shoulder, 2 for one blocked lane, 3 for multiple blocked lanes, and 4 for full closure. Unknown/ambiguous evidence remains null. Category-only SIGALERT, injury reports, vehicle counts, and unit presence do not automatically imply a critical rating. The code deliberately does not assign 5 without a further reviewed critical-impact policy. Negated or uncertain reopening statements do not score as reopened.

The policy and normalization version is `facts-v1`; bump it when changing the fact/prompt interpretation. Do not use the prior AI summary as source evidence for the next generation.

## Validation tools

```sh
# Deterministic regression tests; no paid provider calls
python -m unittest discover -s tests -p 'test_*.py'

# XML and up to three live HTML detail pages; no database writes or AI calls
python -m scripts.chp_probe

# Inspect synthetic compact inputs without contacting a provider
python -m scripts.evaluate_descriptions

# At most nine synthetic provider calls, with temporary accounting DB
python -m scripts.evaluate_descriptions --live --output /tmp/description-eval.json
```

The live evaluation tests 512, 1,024, and 2,048 completion budgets at low reasoning. Review the returned prose as well as finish reasons and token counts. A small synthetic evaluation validates integration and obvious contradictions; it is not a production savings estimate or a comprehensive quality benchmark.

## Validation recorded September 23, 2026

- 88 Python regression tests passed, including durable jobs, retries, partial-source preservation, identity migration, FSP correlation, source disappearance, and accounting.
- `node --check metrics-app/app.js` and `git diff --check` passed.
- A live comparison sampled three incidents. Incident fields, normalized narratives, and coordinates matched between XML and HTML for all three. The XML returned 11 incidents; the HTML table included those 11 plus the excluded Media Log.
- Replaying the downloaded 11-incident XML snapshot twice against a temporary database produced 11 incident rows and 11 distinct source snapshots, with nine independent description jobs after correlation. Two subsequent empty-source observations deactivated the records without a closing AI call.
- Nine synthetic live-model requests at low reasoning completed normally and passed the JSON/length checks. They consumed 1,407 input tokens and 736 completion tokens, including 399 reasoning tokens. Total reported cost was $0.000421754. Individual calls used 153–161 input tokens and 33–314 completion tokens. One call took about 43 seconds; the others took approximately 0.5–6.2 seconds.
- All three tested completion ceilings passed these short cases. The default remains 2,048 for headroom on more complex dispatch histories. This sample does not establish a production savings percentage or worst-case quality/latency.

See [the synthetic inputs and returned results](description-evaluation-2026-09-23.json). The test credential was supplied only to the evaluation process and was not written to the repository or the production configuration.
