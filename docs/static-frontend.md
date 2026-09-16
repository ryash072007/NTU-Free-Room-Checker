# Static frontend production architecture

Production is a React/Vite site served entirely from Vercel's static CDN. It has no
runtime Python service, database connection, API endpoint, or secret. Python and
SQLite remain the data pipeline and correctness oracle used before deployment.

## Data flow

The source of truth is `data/ntu_schedule.db`, produced by the existing scrape and
normalization pipeline. The exporter runs the existing calendar policy and query
services at build/update time and writes validated artifacts to `web/public/data`.
Those artifacts are committed, so Vercel only needs `npm install` and `npm run build`.

Run an export directly:

```powershell
python -m ntu_room_checker export-web-data --db data/ntu_schedule.db --output web/public/data
```

For the normal update, including integrity checks, Python tests, frontend tests, and
a production build, use:

```powershell
.\tools\update_web_data.ps1
```

`-Database` selects another normalized SQLite file. `-SkipTests` and `-SkipBuild`
exist for focused development only; the default is the release-safe workflow.

## Generated schema

- `manifest.json`: schema/data format versions, AY/semester, generation time,
  logical source fingerprint, normalization run, supported date range/list, and counts.
- `rooms.json`: exact canonical physical-room IDs and conservative location metadata.
- `locations.json`: the four verified location definitions and exact member lists.
- `days/YYYY-MM-DD.json`: calendar context and authority, per-room actual schedule
  cards, policy-evaluated occupied blocks, uncertain blocks with reason codes, and
  rooms affected by unparsed timetable records.

The date files contain actual scheduled times for display. Their separate effective
blocks apply holiday/exception policy and coalesce gaps of 10 minutes or less. The
browser performs only interval overlap, next-boundary, duration, and sorting logic.
Missing/corrupt assets and uncertain or non-authoritative periods never become free
claims. Distinct IDs such as `LHN-TR+17` and `TR+17` remain distinct.

Raw `schedule_entries`, `meeting_source_entries`, programme provenance, scraper
internals, and the SQLite database are not exported. This keeps the site data much
smaller than the roughly 302 MB source database and avoids exposing irrelevant data.

## Development and verification

The Python domain layer is the build-time correctness oracle; no HTTP server is
retained on `main`. Run the normal checks with:

```powershell
python -m pytest
Set-Location web
npm test
npm run build
```

Serve only `web/dist` for a production-shaped check. Direct routes such as `/`,
`/locations`, `/schedule`, and `/rooms/LHN-TR%2B17` are handled by the Vercel SPA
rewrite while `/assets/*` and `/data/*` remain real static files.

## Vercel configuration

Set the project Root Directory to `web`, Build Command to `npm run build`, and Output
Directory to `dist`. `web/vercel.json` contains the SPA fallback. No Turso, SQLite,
`NTU_ROOM_CHECKER_DB`, Python function, or other backend environment variable is used.

## Next-semester workflow

1. Scrape the new NTU timetable and normalize it into `data/ntu_schedule.db`.
2. Update the registered Python academic calendar if dates or exception policy changed.
3. Run `.\tools\update_web_data.ps1`.
4. Review counts, size statistics, tests, and the built site.
5. Commit the generated data and source changes, then push for Vercel auto-deployment.

Historical runtime alternatives remain outside `main`: `archive/backend-runtime`
preserves the former SQLite/FastAPI/Docker application, and the validated
`feature/turso-runtime` branch preserves the Turso variant. Neither is part of this
deployment.
