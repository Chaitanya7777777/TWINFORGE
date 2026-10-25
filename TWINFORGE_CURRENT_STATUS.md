# TWINFORGE current status and teammate handoff

Reviewed and checked on **2026-10-25**. This describes the current code, not a
future blueprint. Start here, then consult the versioned calculation contracts.
No original full blueprint document was found in this checkout.

## Purpose and actual architecture

TWINFORGE provides read-only manufacturing digital-twin visibility, durable
observations, independent operational calculations and observed-condition
assessments. It currently uses synthetic factory data, not industrial hardware.
**Factory Simulator is a separate repository and process**, normally on port
8000. It is not bundled into or deployed by this repository. Each teammate runs
their own simulator, TWINFORGE and database unless a shared environment is
explicitly agreed and configured. A GitHub clone does not share running services
or database contents.

```text
Separate Factory Simulator :8000
  GET /api/v1/snapshot
    -> HTTPX connector -> serialized SyncService -> canonical mapper
    -> optional PostgreSQL transaction -> in-memory TwinRegistry
    -> TWINFORGE FastAPI :8001 -> same-origin Operator Dashboard

PostgreSQL observations/events -> bounded retrieval -> pure kpi.v1 / health.v1
  -> read-only historical/calculation APIs -> dashboard
```

FastAPI lifespan owns one background synchronization loop and closes its task
and database pool on shutdown. Polls and manual synchronization share a lock.
Only increasing per-asset sequences are accepted within a run; a changed run ID
allows sequence reset. Failed polls retain last-known twins and retry on the
normal schedule. Errors are summarized; source status checks the latest attempt
and age of the last successful sync. Successful twin retrieval alone does not
prove the source is connected.

When configured, PostgreSQL persistence precedes the registry update. Normalized
factories, lines, assets and runs link to telemetry observations and observed
state/fault events. Unique source/run/asset/sequence keys prevent duplicate
history, including after restart. Transactions are bounded and atomic. A failed
write does not advance the successful synchronization timestamp. There is no
durable retry queue: the next poll reads the latest snapshot, so outage intervals
may be lost. The registry starts empty after restart and repopulates from the
source; it is not hydrated from old database history.

The frontend is **HTML/CSS/vanilla JavaScript**, not Next.js or React. Typed
JSDoc/API contracts, uPlot charts and an esbuild bundle extend the existing
frontend. FastAPI serves built assets; no separate frontend server is required.
Dashboard traffic is GET-only to TWINFORGE. It never controls or directly calls
the simulator.

## Functionality and verification status

“Implemented” means present in code; it does not imply browser or real-database
acceptance. The current preview was checked again during this handoff: source
reported connected, three twins were returned, and **persistence was disabled**.
Both application and isolated-test database environment variables were unset.
That is local runtime configuration, not a missing persistence implementation.

| Feature | Status | Implementation location | Limitation |
| --- | --- | --- | --- |
| Simulator connection, automatic sync, run/sequence validation | Implemented; unit/API checks and live HTTP smoke verified | `app/connectors/simulator.py`, `app/services/sync_service.py`, `app/twin/` | Snapshot sampling can miss intermediate transitions |
| Connectivity/freshness and retained last-known values | Implemented; regression verified | `app/twin/registry.py`, `app/main.py`, frontend `console.js` | Source status and twin requests are not atomic; global sync freshness is not physical machine liveness |
| PostgreSQL identity, telemetry, events, deduplication | Implemented; current real-DB verification pending | `app/storage/`, migrations `001` and `002` | Disabled in current preview; 15 SQL integration tests skipped this session |
| Overview | Implemented; HTTP delivery and transformation tests verified | `app/static/dashboard/console.js` | Counts cover known twins, not installed inventory; visual acceptance pending |
| Machines | Implemented | `console.js`, `components.js`, `evidence-view.js` | Only supplied metadata/telemetry; unknown sensors/units are not inferred |
| KPI Analytics | Implemented, backend/unit/API checks verified | `app/kpi/`, `analysis-view.js` | Requires persisted inputs and valid source-time boundaries; no historical KPI trend endpoint |
| Health Assessment | Implemented, backend/unit/API checks verified | `app/health/`, `analysis-view.js` | Historical condition evidence, not validated prediction or physical machine health |
| History | Implemented; pagination/gap utilities tested | `app/storage/postgres.py`, `evidence-view.js`, `charts.js` | Time/source filters apply to loaded rows; no server time filter or run catalog |
| Navigation, URL selection, search, filters, refresh | Implemented; URL/filter utilities tested | `console.js`, `data.js` | Full keyboard/mobile/race acceptance in a real browser is still pending |
| JSON exports, charts, quality labels | Implemented; data/gap tests verified | `data.js`, `charts.js`, view modules | Export is only loaded/filtered data; chart gaps are not reconstructed |
| Frontend typing/lint | Partial static coverage; checks passed | `contracts.d.ts`, `frontend/tsconfig.json`, `frontend/check.mjs` | Type checking targets API/data boundary; lint is syntax/safety checking, not a full UI type or accessibility audit |
| Production deployment/authentication/hardware adapters | Planned, not implemented | None | This is a local development workspace, not a hardened hosted service |

The five views share a navy sidebar, real factory/line context, source and
persistence status, and URL-preserved asset/run/source selection. Overview has
search and state/factory/line filters plus a selected-machine inspection panel.
Machines shows canonical identity, observed state, job, reported fault,
relationships, telemetry and source scores. KPI and health calculations require
explicit user actions. History uses 200-row forward pages, initially capped at
2,000 records per stream, with explicit budget extension and retry deduplication.
Loaded extents and source/receipt timestamps remain separate. Numeric charts
break at context/sequence gaps, stale/invalid samples and missing timestamps or
values; overlapping source time is not silently sorted into a continuous line.
Errors retain clearly labelled last-known results where supported.

### Independent calculations versus source data

- `kpi.v1` derives quality, reject rate and per-asset good-unit throughput from
  persisted raw counters. It integrates interval power for estimated energy and
  energy per good unit, and derives estimated sampled downtime/reasons from
  observed states. It does not forward the simulator's precomputed factory KPIs.
- Availability, performance, OEE and WIP are unavailable through the current
  API when their required inputs are absent. Pure standard OEE formulas have
  synthetic tests, but this does not establish measured OEE. Never aggregate
  upstream/downstream throughput as line output or call sampled downtime verified
  OEE downtime. See `docs/kpi-v1.md` for precise definitions.
- `health.v1`, method `observed_condition_rules`, independently reports six
  evidence indicators: `fault_reported_at_last_observation`,
  `fault_state_observed`, `offline_state_observed`, `fault_start_observations`,
  `fault_clear_observations`, and `evidence_discontinuity`. It preserves evidence
  references, reasons, data-quality counts and available/partial/unavailable
  states. Initial `fault_observed` is not a known onset; duplicate event IDs do
  not inflate counts. No confidence percentage or prediction is fabricated.
- `MachineTwin.health.health_score` and `anomaly_score` originate from the
  simulator. They are displayed separately, not independently validated or used
  as the health engine's evidence. State, faults, job, telemetry and quality flags
  are also source-reported observations. See `docs/health-v1.md`.

## Structure and API reference

| Path | Responsibility |
| --- | --- |
| `app/main.py`, `app/config.py` | FastAPI routes/lifespan/static mount; environment configuration |
| `app/connectors/`, `app/services/`, `app/twin/` | Source protocol, synchronization, canonical mapping/registry |
| `app/storage/` | asyncpg pool, persistence, bounded reads, migration runner/models |
| `app/storage/migrations/001_initial.sql`, `002_kpi_inputs.sql` | Initial normalized schema; additive nullable counter/power inputs |
| `app/kpi/`, `app/health/` | Separate pure engines, evidence/response models and storage-facing services |
| `app/static/dashboard/index.html`, `console.js` | Current five-view entry point and shared shell |
| `client.js`, `contracts.d.ts`, `data.js` in that directory | Typed API access and data utilities |
| `analysis-view.js`, `evidence-view.js`, `components.js`, `charts.js`, `styles.css` | Views, safe rendering, charting and styling |
| `frontend/` | npm lockfile, build/watch/type/syntax tooling, public configuration example |
| `design/` | Five HTML exports/screenshots/design notes; illustrative reference data, not production fixtures |
| `tests/`, `tests/dashboard/` | unittest/API/SQL integration and Node tests; legacy browser harness |
| `docs/` | Calculation contracts and dashboard operational documentation |

Legacy `dashboard.js`, `api.js`, `history.js` and `kpi.js` remain for existing
tests/harness compatibility; `index.html` now loads `build/console.js`. Do not
assume tests of legacy renderers cover the new five-view DOM interactions.

All URLs below are relative to `http://127.0.0.1:8001`:

| Endpoint | Purpose / parameters |
| --- | --- |
| `GET /health` | Application liveness only, not a source/database health probe |
| `GET /api/twins` | Current known canonical twins |
| `GET /api/twins/{asset_id}` | One current twin; unknown ID returns 404 |
| `GET /api/source-status` | Connection/freshness, run, last attempt/success, safe error and failures |
| `GET /api/persistence-status` | Enabled flag and process-local last write/error; not a live DB probe |
| `GET /api/twins/{asset_id}/telemetry` | Persisted observations; `limit` 1–1000 (default 100), exclusive `after_id` (default 0), optional exact `run_id` |
| `GET /api/twins/{asset_id}/history` | Observed state/fault events; same pagination parameters, independent cursor |
| `GET /api/twins/{asset_id}/kpis` | Required `run_id`, `start`, `end`; `source` defaults to `factory_simulator` |
| `GET /api/twins/{asset_id}/health-assessment` | Required `source`, `run_id`, `start`, `end`, `assessment_generated_at` |
| `POST /sync` | Existing manual synchronization API; not invoked by the dashboard |
| `/dashboard/` | Built read-only UI; hash routes `#/overview`, `#/machines/{encoded_asset_id}`, `#/kpi`, `#/health`, `#/history` |
| `/docs`, `/redoc`, `/openapi.json` | Generated API documentation and exact response schemas |

KPI windows use **source time** with exact recorded start/end boundaries, up to
24 hours and 10,000 observations. Health windows use half-open **receipt time**
`[start,end)`, up to 24 hours and 10,000 records per evidence stream; assessment
time is mandatory, caller-supplied and disclosed in the response. Use aware ISO
8601 timestamps (`Z` or offset); encode a raw URL's `+` as `%2B`. Oversized or
invalid queries return 422. Disabled/unavailable storage returns 503. Empty
history is `[]`; unknown/empty health evidence yields 200 with unavailable
reasons, not a healthy result. Unexpected health failures return a sanitized 500.

Source simulation time, UTC receipt time, last successful synchronization time
and browser refresh time are different clocks/meanings. Never subtract a
simulated historical timestamp from wall-clock now to claim transport latency.

## Fresh-clone setup (PowerShell)

### Prerequisites and reproducibility

- Git; Python **3.11+** and PostgreSQL **14+** are documented by the repository.
  Current checks used Python **3.11.9**. PostgreSQL was not exercised this session.
- Node/npm are required for build/tests. Current checks used Node **26.5.1**, npm
  **11.17.0**. No project `engines` support matrix is declared; older Node versions
  are not verified. esbuild declares Node >=18; that is not full-app certification.
- `requirements.txt` contains FastAPI, Uvicorn, HTTPX, Pydantic and
  `asyncpg>=0.29,<1`; most Python versions are not pinned. The frontend lockfile
  fixes npm resolution (uPlot 1.6.32, esbuild 0.28.2, TypeScript 7.0.2 currently).
- Access to the separate Factory Simulator repository is needed for live source
  data. Its clone URL is not configured here; obtain it from the teammate.

```powershell
git clone https://github.com/Chaitanya7777777/TWINFORGE.git
cd TWINFORGE
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm.cmd ci
npm.cmd run build
cd ..
```

The bundle is intentionally not committed. Build after cloning before opening
the dashboard. `npm.cmd run dev` in `frontend` watches/rebuilds assets; it does
not start an HTTP server. FastAPI continues to serve the generated JS/CSS.

### Environment and optional persistence

`.env.example` and `frontend/.env.example` contain placeholders only. Neither is
automatically loaded. Set variables in the shell that launches the relevant
process, or through your own secret manager. Never commit a populated `.env`.

| Variable | Default / use |
| --- | --- |
| `TWINFORGE_SIMULATOR_URL` | `http://127.0.0.1:8000` |
| `TWINFORGE_SIMULATOR_TIMEOUT_SECONDS` | `2.0` |
| `TWINFORGE_SYNC_POLL_INTERVAL_SECONDS` | `1.0`, delay between completed polls |
| `TWINFORGE_SOURCE_STALE_AFTER_SECONDS` | `5.0` |
| `TWINFORGE_DATABASE_URL` | Unset: in-memory mode; no historical calculations |
| `TWINFORGE_DATABASE_TIMEOUT_SECONDS` | `5`, bounds complete DB operations |
| `TWINFORGE_KPI_MAX_GAP_SECONDS` | `5`, source-time gap tolerance, not sequence-gap forgiveness |
| `TWINFORGE_TEST_DATABASE_URL` | Separate test-only database, exactly named `twinforge_test` |
| `TWINFORGE_API_BASE` | Empty build-time same-origin prefix; optional `/proxy-prefix`, not a credential-bearing URL |

For persistence, use a **new local development database** and dedicated role.
With your PostgreSQL administrator, run the following once only if these names
do not already exist; never reset an existing database to follow this guide:

```sql
CREATE ROLE twinforge LOGIN;
\password twinforge
CREATE DATABASE twinforge OWNER twinforge;
```

Then in the TWINFORGE shell (replace placeholders and URL-encode credentials):

```powershell
$env:TWINFORGE_DATABASE_URL = 'postgresql://YOUR_USER:YOUR_PASSWORD@127.0.0.1:5432/twinforge'
$env:TWINFORGE_DATABASE_TIMEOUT_SECONDS = '5'
.\.venv\Scripts\python.exe -m app.storage.migrate
```

Confirm the target before migrations. `schema_migrations` tracks numbered files
under an advisory lock and transaction. Apply `001` and `002`; rerunning is safe.
Startup does not create tables. Migration 002 leaves unavailable historical
counter/power inputs null, with no invented backfill. A previous dedicated local
verification instance used port 55432/database `twinforge_test`; that instance
is not created or shared by cloning this repository.

### Start the two separate services

In the **separate Factory Simulator repository**, its inspected README uses:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Follow that repository's own README for its optional React frontend and commands
to advance simulation. Its clock advances when commanded; TWINFORGE polling
does not advance it. Do not copy its files or virtual environment into TWINFORGE.

In the **TWINFORGE repository**, with the chosen environment already set:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Open `http://127.0.0.1:8001/dashboard/` and `/docs`. No database is needed to view
live twins, but History/KPI/Health reads require configured, migrated PostgreSQL.
The frontend uses same-origin API requests, not the simulator address. There is
no authentication layer; keep local development services bound to loopback.

## Verification evidence

The following were rerun for this handoff on 2026-10-25:

| Command (from repository root) | Observed result |
| --- | --- |
| `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` | 96 discovered: **81 passed, 15 skipped**; skips say `No isolated PostgreSQL test URL configured` |
| `npm.cmd --prefix frontend test` | **35 passed**, 0 failed/skipped (new console utilities plus legacy module checks) |
| `npm.cmd --prefix frontend run typecheck` | Passed; typed API/data boundary only |
| `npm.cmd --prefix frontend run lint` | Passed; syntax and rendering-safety checks |
| `npm.cmd --prefix frontend run build` | Passed; production JS/CSS generated locally, excluded from Git |
| `.\.venv\Scripts\python.exe -m compileall -q app tests` | Passed |
| `git diff --check` | Passed; Git also reports LF/CRLF normalization warnings |

Read-only HTTP smoke recheck: dashboard HTML/bundle, twins, source status and
persistence status returned 200; **3 known twins**, source connected, persistence
disabled. This does not verify persistent-history rendering or SQL behavior.
No database writes/migrations, simulator mutations or browser actions were
performed for this handoff. Earlier real PostgreSQL/reference/recovery reports
are documented in README but were **not rerun here**. They are not evidence that
the current full suite passed against PostgreSQL.

**Real-browser visual acceptance remains pending.** The earlier Computer Use
attempt stopped because it could not confidently determine the Windows browser
URL. No desktop/mobile screenshot or interaction pass is claimed. Node tests
are not real-browser tests, and some renderer tests target legacy modules.

To run the 15 real SQL tests, create a separate disposable `twinforge_test`
database owned by a test role with schema-creation privileges, then:

```powershell
$env:TWINFORGE_TEST_DATABASE_URL = 'postgresql://TEST_USER:TEST_PASSWORD@127.0.0.1:5432/twinforge_test'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_postgres_integration.py -v
```

The fixture verifies the database name, creates generated `tf_test_<uuid>`
schemas, applies real migrations and removes only its generated schemas. Never
point it at production. Optional `tests/manual_postgres_recovery.py` stops and
starts a specifically guarded Docker test container; read its safeguards before
running. `tests/manual_kpi_reference.py --simulator-repo '..\factory-simulator'`
uses a separate controlled simulator subprocess and isolated SQL schema. Neither
manual script was run for this handoff.

### Short manual acceptance walkthrough

1. At desktop and narrow mobile widths, visit all five routes. Check labels,
   keyboard focus, sidebar, scrollable tables and no page-wide overflow. Search
   and filter actual twins, select one, navigate and reload its URL.
2. In your own simulator, advance a few steps using its documented controls.
   Verify observed sequences/telemetry update in TWINFORGE without a page reload.
   Check source timestamps against the simulator and browser refresh separately.
3. Stop your simulator process. After the next poll, source status should report
   disconnection; twins should remain labelled last-known. Restart it and verify
   automatic recovery. Do not interrupt someone else's shared process.
4. Enable your migrated development database and restart TWINFORGE. Advance new
   observations, load History using the actual asset/run, inspect both timestamp
   columns and event records, page forward and export the loaded selection. Use
   exact recorded source boundaries for KPIs and receipt bounds for Health.
   Compare values, nulls/reasons and evidence references with API JSON. Restart
   TWINFORGE and confirm stored history persists without duplicate records.
5. Reset only your own simulator through its UI. Confirm a new run ID and reset
   sequences are accepted, prior dashboard analysis/history is invalidated, and
   explicitly selected old-run history remains queryable. Never join runs into
   a continuous chart. Switch selections during pending requests to check races.
6. Check missing/unknown IDs, empty runs, disabled persistence (503), invalid
   windows (422), request failure, hidden-tab polling and retained last-known
   data. Observe GET-only dashboard traffic, with no `/sync` or simulator calls.

## Known limitations and next work

1. **Finish browser acceptance first:** all five views, desktop/mobile, keyboard,
   refresh errors, selection races/run changes and chart gaps with controlled
   fixtures. Visual polish was implemented from references, not browser-certified.
2. **Enable isolated SQL verification:** run all 15 current PostgreSQL tests and
   a persistence-enabled dashboard walkthrough; current preview is in-memory.
   Migration state of any teammate database must be checked independently.
3. **Improve reproducibility:** establish supported Node versions and pin/test
   Python dependencies; consider broader typing and tests for the new view DOM.
4. **Resolve actual data gaps before expanding calculations:** schedules,
   trustworthy runtime, ideal-cycle data and unit-flow records are absent.
   Availability/performance/OEE/WIP must remain unknown where unsupported.

History APIs have no server time filtering, reverse paging, totals or complete
run/asset catalog. Initial old pages may not reach a desired recent window;
load more explicitly. Large user-expanded datasets may render slowly. There is
no historical KPI series API: the analysis view shows telemetry context, not an
invented KPI trend. Source health scores are not historical independent evidence.
No retention/replay policy, durable missed-snapshot queue, verified physical fault
timing or calibrated health thresholds exist. Last persistence activity is not
a real-time DB health assertion. Design export contents are illustrative only.

### Planned, not implemented

Validated predictive models, remaining-useful-life estimates, what-if
orchestration, recommendations, resilience/benchmarking, industrial protocol
adapters, 3D and cloud production deployment are outside this implementation.
Do not treat observed-condition `health.v1` as completion of predictive ML.
Review and approve any new scope before adding schema, control actions or models.

## Sharing hygiene

Commit source, migration SQL, lockfiles, tests, design references and docs only.
Exclude `.env` files (except placeholder examples), credentials, database dumps,
logs, virtual environments, `node_modules`, bytecode and generated frontend build
output. Each teammate builds assets and configures local secrets after cloning.
The simulator repository is untouched and must be shared independently.
