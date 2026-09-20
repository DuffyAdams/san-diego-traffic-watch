# San Diego Traffic Watch

<div align="center">
  <img src="screenshots/logo.png" alt="San Diego Traffic Watch logo" width="320" />
</div>

San Diego Traffic Watch is a Flask plus Svelte application that ingests live public-safety and traffic incidents across San Diego County, stores them in SQLite, enriches them with geocoding and AI-generated summaries, and serves both the public site and operational metrics from the same backend.

## Overview

The repository has three main pieces:

- `backend/` contains the Flask API, persistence, enrichment, source scrapers, and continuous monitoring loop.
- `traffic-app/` contains the Svelte frontend that is built into `traffic-app/dist` and served by Flask in production.
- `metrics-app/` is a separate static dashboard that reads from the same backend APIs for operational visibility.

## Current Features

- Aggregates incidents from CHP, SDPD, SDFD, and optionally SDSO when `SDSO_API_URL` is configured.
- Runs continuous scrape cycles every 15 seconds and marks stale incidents inactive when they fall out of source feeds.
- Stores incidents, likes, comments, geocoding cache entries, and API analytics events in SQLite with WAL mode enabled.
- Geocodes non-coordinate incidents with cached lookups, Nominatim first, and ArcGIS fallback constrained to the San Diego region.
- Generates incident summaries and 1 to 5 severity scores with Mistral Nemo
  through OpenRouter via the OpenAI SDK.
- Supports per-device likes and up to two comments per incident using a persistent UUID cookie.
- Serves incident statistics, operational dashboard metrics, and health checks over JSON endpoints.
- Renders interactive frontend maps with MapLibre plus local PMTiles assets instead of remote static map images.
- Includes backup, restore, geocoding catch-up, mock-data, and deployment helpers in `scripts/` and `deploy/`.

## Screenshots

The current dark-mode UI is shown below using deterministic local incident data.

| Incident Feed | Map and Incident Log | Stats Panel |
| --- | --- | --- |
| <img src="screenshots/frontpage.png" alt="Traffic feed dashboard" height="260" /> | <img src="screenshots/map_screenshot.png" alt="Interactive map view" height="260" /> | <img src="screenshots/stats_screenshot.png" alt="Traffic statistics panel" height="260" /> |

## Architecture

- Backend entry point: [backend/__main__.py](backend/__main__.py)
- Flask routes and background monitoring: [backend/routes.py](backend/routes.py) and [backend/monitor.py](backend/monitor.py)
- API infrastructure: bounded TTL caching, keyed request coalescing, and rate limiting in [backend/api_support.py](backend/api_support.py)
- Statistics queries and chart buckets: [backend/stats.py](backend/stats.py)
- Frontend: Svelte 5 plus Vite in [traffic-app](traffic-app)
- Metrics UI: static dashboard in [metrics-app](metrics-app)
- Database: SQLite file at `traffic_data.db`
- SQLite lifecycle: deterministic commit, rollback, and connection cleanup in [backend/sqlite_utils.py](backend/sqlite_utils.py)
- Geocoding: cached Nominatim and ArcGIS lookups in [backend/geocoding.py](backend/geocoding.py)
- LLM summaries: OpenRouter-backed client in [backend/llm.py](backend/llm.py)

## Frontend Performance

- Timestamps share one visibility-aware clock and reuse bounded caches of internationalization formatters.
- Feed and map polling pause in hidden tabs, cancel obsolete requests, and refresh on return. Unchanged feed responses preserve card identities; changed responses preserve local interaction state.
- Mini-maps activate near the viewport, retain their canvas during brief scroll excursions, and release offscreen or hidden-tab resources after a short grace period.
- Card entrances use opacity and transforms instead of animating layout. Subtle source-selection, search, like, and overlay feedback respects reduced-motion and accessibility preferences, including JavaScript transitions and map camera movement.

## Remaining Performance Opportunities

1. **Virtualize the incident feed and recycle mini-map instances.** Cursor pagination limits each request, but every loaded card remains mounted. Rendering only the visible rows would reduce DOM size, layout work, memory use, and the number of active MapLibre canvases during long sessions.
2. **Make live refreshes conditional.** Add ETag/`If-None-Match` responses or a small server-sent-events delta stream to reduce repeated JSON transfers and SQLite reads beyond the existing visibility-aware polling.
3. **Precompute statistics rollups during scrape cycles.** Store per-source hourly and daily counters as incidents are updated, then serve `/api/incident_stats` from those rollups instead of repeatedly grouping the growing incidents table. This would keep dashboard response times stable as historical data accumulates.

## Requirements

- Python 3.10+
- Node.js 18+
- `npm`

## Setup

Clone the repo, create a virtual environment, and install backend dependencies from the project root:

```bash
cd /home/ubuntu/projects/san-diego-traffic-watch
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Install frontend dependencies:

```bash
cd /home/ubuntu/projects/san-diego-traffic-watch/traffic-app
npm install
```

Optional: install the Playwright workspace used for UI and API smoke tests:

```bash
cd /home/ubuntu/projects/san-diego-traffic-watch/tests
npm install
npx playwright install
```

## Running Locally

### Backend only

Use this when you want the API and scraper loop without the Vite dev server:

```bash
cd /home/ubuntu/projects/san-diego-traffic-watch
source venv/bin/activate
TESTMODE=true python3 -m backend
```

The Flask app serves on `http://127.0.0.1:5002` if you set `TRAFFIC_APP_HOST=127.0.0.1`.

### Frontend dev mode

Start Vite from `traffic-app/`. Local development includes sample incidents, statistics, maps, likes, and comments without running Python:

```bash
cd /home/ubuntu/projects/san-diego-traffic-watch/traffic-app
npm run dev
```

Useful frontend scripts:

- `npm run dev`: Vite dev server on port `5173` with mock data
- `npm run dev:mock`: explicitly enable mock data
- `npm run dev:live`: connect to a separately running Python backend
- `npm run dev:full`: start Python and Vite together with backend data
- `npm run dev:local`: Vite bound to `127.0.0.1`
- `npm run dev:proxy`: Vite proxied to `https://sandiegotraffic.com`
- `npm run dev:backend`: starts the backend in `TESTMODE`
- `npm run build`: production build to `traffic-app/dist`
- `npm run preview`: preview the production bundle

Mock changes are stored in memory and reset when Vite restarts. The app displays a demo notice while using sample data. Setting `VITE_PROD_URL` switches `npm run dev` to that backend; production builds never enable the mock API.

### Production-style local run

Build the SPA and let Flask serve the compiled assets:

```bash
cd /home/ubuntu/projects/san-diego-traffic-watch/traffic-app
npm run build
cd ..
source venv/bin/activate
python3 -m backend
```

## API Surface

### Read endpoints

- `GET /api/incidents`: paginated incident feed with filters for `limit`, `cursor`, `type`, `location`, `source`, `active_only`, and `date_filter`
- `GET /api/incident_stats`: aggregated counts, top locations, chart data, and scrape/runtime metrics for `day`, `week`, `month`, or `year`
- `GET /api/dashboard_metrics`: production-facing operations and engagement metrics used by `metrics-app/`
- `GET /api/user/check`: returns the device UUID used for likes and comments
- `GET /api/healthz`: lightweight backend health response with scrape freshness
- `GET /maps/<filename>`: serves generated map assets if present

### Write endpoints

- `POST /api/incidents/<incident_id>/like`: like an incident
- `DELETE /api/incidents/<incident_id>/like`: remove a like
- `POST /api/incidents/<incident_id>/comment`: add a comment with a two-comment-per-device limit

The backend applies in-memory read and write rate limiting and caches read responses for short TTL windows.

## Database and Background Jobs

The app initializes SQLite automatically on startup and creates these tables as needed:

- `incidents`
- `likes`
- `comments`
- `api_events`
- `geocode_cache`
- `reverse_geocode_cache`

Scrape and enrichment behavior:

- Source scrapers run concurrently every 15 seconds.
- A failed source is isolated from stale-incident cleanup, so an upstream outage cannot clear that source's live incidents.
- Every new incident immediately receives a description from its reported type, location,
  community, and available dispatch details. Existing meaningful summaries are preserved;
  the API also supplies factual descriptions for historical blank/placeholder records.
- Already-closed source records (including SDSO calls) keep these factual descriptions
  without scheduling AI work that the active-only worker cannot save.
- New active incidents are inserted quickly, then Mistral description refreshes continue
  in the background with `mistralai/mistral-nemo`. Pending per-incident refreshes
  are persisted and retried after transient failures or service restarts; no
  bulk-model refinement is used.
- CHP incidents usually arrive with coordinates already present.
- SDPD, SDFD, and SDSO incidents are geocoded when coordinates are missing.
- The frontend renders mini-maps client-side from coordinates and local PMTiles data. The legacy `/maps` endpoint remains available for older database rows.

Incident summaries use `mistralai/mistral-nemo`.

## Scripts

Operational helper scripts live in [scripts](scripts):

- `python3 -m scripts.backfill_descriptions`: preview historical placeholder repairs;
  add `--apply` after a database backup to persist them in bounded transactions without AI calls.
- `python3 -m scripts.backup_db`: create a consistent WAL-safe backup in `backups/` and retain the newest three copies
- `python3 -m scripts.restore_db`: restore the newest backup
- `python3 -m scripts.restore_db backups/traffic_data_<timestamp>.db`: restore a specific backup
- `python3 -m scripts.catchup_geocoding`: backfill coordinates for older incidents that still need geocoding
- `python3 -m scripts.add_mock_data`: seed historical mock incidents for dashboard or UI testing
- `python3 -m scripts.update_db`: normalize older incident type values in the database

Stop the backend before running a restore so the live SQLite file is not being written during the copy.

## Testing

Python tests use the standard-library `unittest` runner and cover API support primitives, batch enrichment, incident persistence, geocoding, statistics, and source-failure handling. They do not make live network calls.

Playwright coverage in [tests/README.md](tests/README.md) covers:

- UI workflows
- API contract checks
- accessibility smoke tests
- edge cases
- release-readiness checks

Common commands:

```bash
cd /home/ubuntu/projects/san-diego-traffic-watch
python3 -m unittest discover -s tests -p "test_*.py" -v

cd /home/ubuntu/projects/san-diego-traffic-watch/tests
npm test
npm run test:ui
npm run test:api
```

## Deployment Notes

Production deployment artifacts live in [deploy](deploy):

- `deploy/traffic-app.service` runs the Flask backend and scraper on `127.0.0.1:5002`
- `deploy/nginx-traffic-app.conf` fronts the public traffic site
- `deploy/nginx-metrics.duffyadams.com.http.conf` and `deploy/nginx-metrics.duffyadams.com.conf` front the metrics dashboard
- `deploy/DEPLOYMENT.md` and `deploy/METRICS_DEPLOYMENT.md` document the production layout

The main service expects:

- repo path: `/home/ubuntu/projects/san-diego-traffic-watch`
- virtualenv: `/home/ubuntu/projects/san-diego-traffic-watch/venv`
- env file: `/home/ubuntu/projects/san-diego-traffic-watch/.env`

## Project Layout

```text
san-diego-traffic-watch/
├── backend/
│   ├── __main__.py
│   ├── config.py
│   ├── db.py
│   ├── monitor.py
│   ├── routes.py
│   ├── scrapers/
│   └── ...
├── scripts/
├── deploy/
├── metrics-app/
├── tests/
├── traffic-app/
│   ├── src/components/{feed,map,shared,stats,ui}/
│   ├── public/
│   ├── dist/
│   └── package.json
└── traffic_data.db
```

## License

See [LICENSE](LICENSE).
