# Playwright Test Project

This `tests/` workspace now contains two kinds of tests:

- Deterministic Python unit tests at the root of `tests/`
- A Playwright project for UI, REST API, accessibility, edge-case, and release-readiness coverage

## What it covers

- `specs/ui-workflows.spec.js`: feed loading, source filtering, search, diagnostics panel, comments
- `specs/api-contract.spec.js`: incidents, stats, likes, and comments API contracts
- `specs/accessibility.spec.js`: keyboard smoke checks plus critical Axe violations
- `specs/edge-cases.spec.js`: empty search states and incident API failure handling
- `specs/release-readiness.spec.js`: console/network smoke checks and responsive layout sanity checks
- `specs/performance-polish.spec.js`: shared timestamp timers, visibility-aware polling, filter races, and reduced motion
- `frontend-performance.test.mjs`: refresh identity, ordering, local state, and cached formatting (`npm run test:unit`)
- `reporters/defect-reporter.mjs`: writes JSON and Markdown defect summaries into `artifacts/defects/`

## Default mode

By default, Playwright starts:

1. A local mock API at `http://127.0.0.1:8787`
2. The Svelte frontend from `/traffic-app` on `http://127.0.0.1:4173`

The frontend is pointed at the mock API through the existing Vite proxy, which keeps the suite deterministic and fast.

## Setup

```bash
cd /workspaces/traffic-app/tests
npm install
npx playwright install
```

## Run

From the repository root, run the Python suite:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

The Python suite uses temporary SQLite databases and mocks external behavior; live ArcGIS diagnostics live under `scripts/check_arcgis_*.py` instead.

From this directory, run the browser suite:

```bash
npm test
npm run test:ui
npm run test:api
npm run test:unit
```

Set `PLAYWRIGHT_CHANNEL=chrome` to use installed Google Chrome instead of bundled Chromium (the video helper still requires `npx playwright install ffmpeg`).

## Optional live-backend API smoke

If you want to hit the real Flask backend instead of the mock API, start your backend separately and then run:

```bash
cd /workspaces/traffic-app/tests
PLAYWRIGHT_USE_LIVE_BACKEND=1 \
PLAYWRIGHT_SKIP_WEB_SERVER=1 \
PLAYWRIGHT_API_BASE_URL=http://127.0.0.1:5002 \
npx playwright test specs/api-contract.spec.js
```

That mode is best used as a contract smoke check once the Python service is already running locally.
