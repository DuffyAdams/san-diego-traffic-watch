# CHP summary validation diagnostics

## Diagnosis of saved job 1019 (2026-09-23)

Production SQLite was inspected with `mode=ro`. The current failed version had
five attempts, `last_error=ValueError`, all with finish reason `stop`. Historical
response bodies were not retained, so their exact validation branches cannot be
recovered from this evidence alone.

Two isolated provider calls used that job's saved facts, with accounting written
only to disposable temporary databases. No prompt or response text was logged.

| Instructions | Result | Summary characters | Input tokens | Completion tokens | Provider-reported cost |
|---|---|---:|---:|---:|---:|
| Previous | valid summary-only JSON, stop, rejected for length | 279 | 255 | 64 | 0.00004087 |
| Revised | validated, stop | 185 | 464 | 1703 | 0.000637346 |

The first call reproduced a legitimate length rejection, **not** a dispatch-marker
false positive. The regex, JSON schema, 199-character ceiling, 2048-token ceiling,
reasoning effort, retry bounds, and cost accounting remain unchanged. The revised
prompt reinforces brevity and factual selection rather than widening validation.
One successful sample does not establish general model accuracy or cost savings;
the second call used substantially more completion tokens within the same limit.

`description_jobs.last_error` and generation logs now use content-free codes:
`validation:missing_choice`, `validation:unfinished_response`,
`validation:empty_content`, `validation:invalid_json`,
`validation:unexpected_fields`, `validation:summary_type`,
`validation:empty_summary`, `validation:summary_too_long`,
`validation:dispatch_log`. Other exceptions retain only their class name.
Unknown usage and costs remain NULL; failed validation still records the attempt.

## Scoped recovery plan (not executed)

1. Deploy/restart only under the parent's authorization and verify the new code.
2. Re-read job `(1019, 2026-09-23)` and its incident in a transaction. This is the
   only specifically reproduced candidate; do not reset all failed history.
3. Require CHP source, no related incident, failed status, no live lease, and the
   reviewed desired hash
   `4c262a12736bc1d09e429a1525e2f16ca2fdf561d3d068605fca0ec84a1d7f5a`.
   If source facts or the job changed, stop and review instead of overwriting it.
   The incident was inactive at the final read: recovery is a deliberate one-row
   historical correction, not an active-incident-only retry. Skip unless approved.
4. Recompute facts/payload and hash from the persisted incident using the current
   facts policy (the companion change advances it to facts-v2). Existing `sync_job`
   handles a changed hash atomically and installs an honest source fallback. If
   the hash is unchanged, use a compare-and-set update on this exact key/hash and
   failed/no-lease state to reset attempts to 0, status to pending, clear last_error,
   set first_queued_at/due_at to now, and set the incident pending marker. Retain
   completed_hash, raw Details, and all historical attempts/accounting. Abort if
   completed_hash already equals desired_hash. Do not enqueue a second copy.
5. Let the normal worker run with the existing retry bound. Read back the exact
   job, incident origin/summary and attempt record; stop on a fresh validation
   failure and inspect its code, not its prompt/response body.
6. Other same-date failures (0741, 0867, 0870) were also inactive and had only the
   old generic ValueError. They are unproven candidates, not an automatic requeue
   list. Review individually if correction is desired.

## Test isolation issue found

An existing `test_llm_pipeline` provider-failure test did not mock accounting.
The first full-suite run inadvertently inserted production `llm_attempts.id=925`
(null incident/date/cost, direct, failed); it made no paid request and changed no
incident/job. The test now mocks `record_attempt`. The row was left untouched to
avoid an unauthorized cleanup write. Parent should decide whether to remove that
exact synthetic row after re-verifying its fields; never delete by a broad null-key
predicate.
