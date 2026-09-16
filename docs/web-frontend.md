# Web frontend

The production application is a mobile-first React 19, TypeScript, Vite, and React Router single-page application. It loads generated JSON from `/data`; it does not call a runtime backend.

## Local development

```powershell
Set-Location web
npm install
npm run dev
```

The generated dataset must exist under `web/public/data`. Refresh it from the repository root with `python -m ntu_room_checker export-web-data` or run the complete `.\tools\update_web_data.ps1` workflow.

## Routes and behavior

- `/` and `/locations`: campus-wide or named-location room browsing with Singapore-local date/time, duration, filtering, and availability sorting.
- `/schedule`: keyboard-accessible room search.
- `/rooms/:room`: room schedule, calendar context, availability, and safe free gaps.

The repository fetches only `manifest.json`, `rooms.json`, `locations.json`, and date-scoped `days/YYYY-MM-DD.json` assets. Missing or corrupt files, unsupported dates, unparsed meetings, and non-authoritative calendar periods remain explicit unknown/uncertain states.

## Verification

```powershell
npm test
npm run build
```

Tests cover static repository caching, Singapore time, URL-safe room names, campus-wide and location sorting, uncertainty handling, route behavior, and schedule rendering. The production output is `web/dist`; `web/vercel.json` supplies the SPA fallback while preserving real `/assets` and `/data` files.
