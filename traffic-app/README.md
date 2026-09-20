# Traffic App Frontend

The public interface is a Svelte 5 single-page app built with Vite. It renders the incident feed, statistics, comments, and MapLibre/PMTiles maps while the Flask backend provides `/api` and legacy `/maps` routes.

## Commands

```bash
npm install
npm run dev
npm run build
npm run preview
```

`npm run dev` serves 24 recent sample incidents plus more than two years of generated incident history directly from Vite, so no Python server is needed. Mock mode supports source and incident filters, pagination, maps, statistics, likes, and comments. A demo notice identifies the sample data. Changes stay in memory until Vite restarts (or you send `POST /__reset`).

- `npm run dev:mock`: explicitly use mock data, even when `VITE_PROD_URL` is set.
- `npm run dev:live`: proxy `/api` and `/maps` to the Python backend at `http://127.0.0.1:5002`.
- `npm run dev:full`: start Python and Vite together using real backend data.
- `npm run dev:proxy`: use `https://sandiegotraffic.com`.

Setting `VITE_PROD_URL` also switches ordinary `npm run dev` to the specified backend. Production builds and previews do not enable the mock API.

## Stats comparisons in mock mode

Open **Stats**, then switch between **1 day**, **Week**, **Month**, and **Year**. Each view overlays muted historical bars behind the current bars on a shared scale. All three sources (CHP, SDPD, SDFD) have deterministic history with varied hourly, daily, and monthly counts.

- **1 day:** matching rolling 24 hours seven days earlier.
- **Week:** the preceding seven calendar-day buckets.
- **Month:** the preceding 30 calendar-day buckets.
- **Year:** the preceding 12 calendar-month buckets.

The final historical day/month is cut off at the equivalent current time, including leap-day clamping, so partial periods are compared fairly. The stats API returns `previousPeriodData` with the same bucket count as `hourlyData`, or `null` when history is unavailable. `previousWeekHourlyData` remains an alias for day-view clients. Coverage uses incident records on each historical day (each month for Year) as a proxy; it is not an ingestion-uptime guarantee. Mock comparisons are computed from the seeded incidents, not fixed chart arrays. `POST /__reset` restores the same sample data.

## Source layout

- `src/App.svelte`: application orchestration and page-level state
- `mocks/`: sample incidents and the shared API handler used by local development and Playwright
- `src/components/feed/`: incident feed cards, tables, comments, and loading states
- `src/components/map/`: full and compact map views
- `src/components/shared/`: components reused across multiple features
- `src/components/stats/`: incident statistics and activity charts
- `src/components/ui/`: page-level controls and feedback
- `src/stores/`: shared toast and map-selection state
- `src/utils/apiUrls.js`: API query construction
- `src/utils/cache.js`: bounded client-side cache helpers
- `src/utils/incidents.js`: API incident-to-view-model normalization
- `src/utils/i18n.js`: localized strings and date formatting
- `src/utils/mapRuntime.js`: lazy MapLibre and PMTiles loading

Production output is written to `dist/` and served by Flask.
