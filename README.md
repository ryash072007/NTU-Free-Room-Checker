# NTU Free Room Checker

NTU Free Room Checker is a frontend-only React/Vite application backed by generated static timetable data. Production has no Python server, database connection, credentials, or runtime API.

```text
NTU timetable
    ↓
Python scraper and normalization
    ↓
SQLite source of truth (local build input)
    ↓
Static data exporter
    ↓
React/Vite application
    ↓
Vercel static hosting
```

Python remains the build-time data-engineering and correctness layer. It scrapes NTU's public class schedule with Playwright, preserves raw provenance, normalizes rooms and meetings into SQLite, applies academic-calendar and conservative availability policy, and exports validated JSON to `web/public/data`. React is the production application and reads only those static assets.

## Setup

Python 3.11 or newer and Node.js are required.

```powershell
python -m pip install -e ".[dev]"
playwright install chromium
Set-Location web
npm install
```

## Data pipeline

The default local database is `data/ntu_schedule.db`. Database files are ignored by Git and are never deployed.

```powershell
# Discover current NTU term/programme values
python -m ntu_room_checker scrape --list-programmes

# Scrape and normalize
python -m ntu_room_checker scrape --db data/ntu_schedule.db

# Optional: room capacity/booking-eligibility source (see docs/room-capacity.md)
python -m ntu_room_checker scrape-facility-list --db data/ntu_schedule.db

python -m ntu_room_checker normalize --db data/ntu_schedule.db --rebuild --stats

# Generate the tracked static dataset
python -m ntu_room_checker export-web-data --db data/ntu_schedule.db --output web/public/data
```

Useful build-time inspection commands include `profile`, `calendar-date`, `room-schedule`, `free-rooms`, and `room-availability`. Run `python -m ntu_room_checker --help` for the complete command list.

The normal semester refresh command performs a SQLite integrity/schema check, exports and validates the data, runs Python and frontend tests, and builds the production site:

```powershell
.\tools\update_web_data.ps1
```

See [timetable normalization](docs/timetable-normalization.md), [academic calendar](docs/academic-calendar.md), [calendar exception policy](docs/calendar-exception-policy.md), and [static frontend architecture](docs/static-frontend.md) for the data and safety model.

## Frontend development and deployment

```powershell
Set-Location web
npm run dev
npm test
npm run build
```

The primary routes are `/` (Browse Anywhere), `/locations`, `/schedule`, and `/rooms/:room`. Availability uses Singapore time and never treats missing, uncertain, recess, or examination data as confirmed free. Room identifiers such as `LHN-TR+17` remain distinct and are URL-encoded in browser routes.

Vercel configuration is static only:

- Root Directory: `web`
- Build Command: `npm run build`
- Output Directory: `dist`
- SPA fallback: `web/vercel.json`

No backend environment variables or database are required. Generated data under `web/public/data` is tracked so Vercel can build the site without Python.

## Validation

```powershell
python -m pytest
Set-Location web
npm test
npm run build
```

The test suites protect scraper/normalization behavior, academic-calendar policy, query semantics, static exporter integrity, Python-to-static equivalence, and frontend behavior.

Historical backend implementations are preserved outside `main`:

- `archive/backend-runtime` — former SQLite/FastAPI/Docker production architecture
- `feature/turso-runtime` — validated Turso backend alternative

`feature/static-frontend` preserves the feature history that introduced the current architecture.
