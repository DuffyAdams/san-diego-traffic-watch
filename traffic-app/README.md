# Traffic App Frontend

The public interface is a Svelte 5 single-page app built with Vite. It renders the incident feed, statistics, comments, and MapLibre/PMTiles maps while the Flask backend provides `/api` and legacy `/maps` routes.

## Commands

```bash
npm install
npm run dev
npm run build
npm run preview
```

`npm run dev` serves 24 sample incidents directly from Vite, so no Python server is needed. Mock mode supports source and incident filters, pagination, maps, statistics, likes, and comments. A demo notice identifies the sample data. Changes stay in memory until Vite restarts (or you send `POST /__reset`).

- `npm run dev:mock`: explicitly use mock data, even when `VITE_PROD_URL` is set.
- `npm run dev:live`: proxy `/api` and `/maps` to the Python backend at `http://127.0.0.1:5002`.
- `npm run dev:full`: start Python and Vite together using real backend data.
- `npm run dev:proxy`: use `https://sandiegotraffic.com`.

Setting `VITE_PROD_URL` also switches ordinary `npm run dev` to the specified backend. Production builds and previews do not enable the mock API.

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
