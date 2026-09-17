# Ingestion Design Decisions

## Why incremental loading instead of full re-pulls
Re-fetching the entire NYC 311 dataset on every run would waste API calls,
storage, and time as the dataset grows into the millions of records. Instead,
each run only fetches records created after the last successful run's
timestamp, using the API's `created_date` field with a `$where` filter.

## Why idempotency matters here, and how it's achieved
If a run crashes or is manually re-triggered, it must never create duplicate
records or corrupt pipeline state. Two mechanisms guarantee this:

1. **Each run writes to its own uniquely-timestamped file**
   (`raw/complaints_<timestamp>.json`) rather than appending to a shared file.
   Re-running never overwrites or duplicates a prior write.
2. **State only updates after a successful write.** The "last run" timestamp
   is only persisted once data has been written to storage successfully. If
   a run fails partway, the state file is untouched, so the next run safely
   retries the same time window instead of silently skipping data.

## Why a 7-day lookback on first run
With no prior state, the pipeline needs a starting point. Too short a window
(e.g. 1 day) yields too little data to be useful; too long (e.g. all-time)
risks pulling far more than the per-run limit in one shot. 7 days is a
deliberate, named constant (`FIRST_RUN_LOOKBACK_DAYS`), not a hardcoded
magic number — chosen to give a meaningful initial dataset without
overwhelming a single run.

## Why a 5,000-record cap per run
This is a deliberate constraint for a portfolio-scale project: it keeps each
run fast, keeps storage costs at zero (well within GCS free tier), and
avoids hitting Socrata API rate limits. In a production system, this would
be tuned based on actual data volume and infrastructure capacity.

## Why retries use exponential backoff, and only on some errors
Transient failures (network blips, server-side 5xx errors, timeouts) are
retried up to 3 times with exponential backoff (5s, 10s, 20s) — this avoids
hammering an already-struggling API with immediate retries. Client errors
(4xx — e.g. an invalid token or malformed query) are **not** retried, since
they'll fail identically every time; the script fails fast instead of
wasting time on a request that can't succeed.

## Why local emulation (Floci) before real cloud
All ingestion logic was developed and tested against `floci-gcp`, a local
GCS emulator, before ever touching a real Google Cloud account. This gave a
fast, zero-cost iteration loop during development. The same code works
against real GCS with no changes — only the `client_options` endpoint
changes — because the official `google-cloud-storage` SDK is used
throughout, not custom HTTP calls.

## Postmortem: duplicate rows during BigQuery load

**What happened:** the initial version of `load_to_bigquery.py` had no
tracking of which staged files had already been loaded. Running the script
twice (once accidentally, before the fix was written) loaded every staged
file both times, doubling the row count in BigQuery (25,000 → 50,000).

**Root cause:** unlike the ingestion and transform stages — which were
idempotent from the start — the BigQuery load stage was initially written
without state tracking, since testing focused on "does it load correctly"
rather than "is it safe to run twice."

**Fix:** added a state file (`_state/loaded_to_bq.json`, stored in GCS)
recording which staged files have already been loaded, following the same
idempotency pattern used in ingestion and transformation. The load function
now checks this state before loading each file and skips anything already
processed.

**Cleanup:** since duplicate rows already existed before the fix was
deployed, a one-off `reset_bq_state.py` script was used to clear the load
state, followed by `DELETE FROM ... WHERE TRUE` to clear the table, then a
clean reload.

**Lesson:** every write operation in a pipeline needs idempotency
designed in from the start, not added after the fact once duplication is
already observed in production. This also reinforced why running each new
pipeline stage twice in a row — deliberately, as a test — should be a
standard verification step, not just a "does it work once" check.