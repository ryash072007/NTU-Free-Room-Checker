# HTTP API

The FastAPI application exposes the existing calendar and timetable services.
Routes validate and serialize requests; availability, exception, and timetable
logic remains in the domain/query layer.

All application endpoints use `/api/v1`. Interactive Swagger documentation is
at `/docs`, and the OpenAPI document is at `/openapi.json`.

## Installation and startup

```powershell
python -m pip install -e ".[dev]"

$env:NTU_ROOM_CHECKER_DB = "data/ntu_schedule.db"
$env:NTU_ROOM_CHECKER_CORS_ORIGINS = "http://localhost:3000,http://localhost:5173"

python -m ntu_room_checker serve --host 127.0.0.1 --port 8000
```

Direct Uvicorn startup is also supported:

```powershell
python -m uvicorn ntu_room_checker.api.app:app --host 127.0.0.1 --port 8000
```

`NTU_ROOM_CHECKER_DB` defaults to `data/ntu_schedule.db`. It is never returned
by the API. `NTU_ROOM_CHECKER_CORS_ORIGINS` is a comma-separated allowlist. An
empty value disables CORS middleware. Credentials are disabled, and wildcard
origins are not configured.

## Timezone and input format

The application timezone is explicitly `Asia/Singapore` (UTC+08:00). Separate
`date=YYYY-MM-DD` and `time=HH:MM` inputs are interpreted as Singapore local
time. Server and client machine timezones are irrelevant. A reusable
`singapore_now()` helper exists for future “now” behavior; current endpoints are
deterministic and require a date/time.

Duration must be positive, at most 1,440 minutes, and the interval must remain
within one local calendar day. Room path components must be URL encoded; for
example, `LHN-TR+15` can be sent as `LHN-TR%2B15`.

## Endpoints

| Method and path | Purpose |
| --- | --- |
| `GET /api/v1/health` | Check normalized DB and calendar availability |
| `GET /api/v1/calendar/{date}` | Resolve date, term, week, holiday, and exceptions |
| `GET /api/v1/rooms?q=&limit=` | Search normalized physical rooms |
| `GET /api/v1/rooms/{room}/schedule?date=` | Policy-evaluated room schedule |
| `GET /api/v1/rooms/{room}/availability?date=&time=&duration=` | Check one room |
| `GET /api/v1/rooms/free?date=&time=&duration=&limit=&include_uncertain=` | Find confidently free rooms |

The static `/rooms/free` route is registered before parameterized room routes.

Room search ranks exact, prefix, then contains matches, case-insensitively. It
queries normalized physical rooms only. The maximum result limit is 100.

## Examples

```http
GET /api/v1/calendar/2026-09-15
GET /api/v1/rooms?q=LHN&limit=20
GET /api/v1/rooms/LHN-TR%2B15/schedule?date=2026-09-15
GET /api/v1/rooms/LHN-TR%2B15/availability?date=2026-09-15&time=15:30&duration=60
GET /api/v1/rooms/free?date=2026-09-04&time=11:00&duration=60&include_uncertain=true
```

A confirmed-free response retains the domain state:

```json
{
  "room": "LHN-TR+15",
  "date": "2026-09-15",
  "requested_start": "15:30",
  "requested_end": "16:30",
  "duration_minutes": 60,
  "status": "free",
  "is_free": true,
  "free_until": "17:00",
  "free_duration_minutes": 90,
  "occupied_intervals": [],
  "uncertain_intervals": [],
  "reason_codes": [],
  "reasons": [],
  "calendar": {}
}
```

The abbreviated `{}` calendar above is populated with the full typed calendar
context in actual responses.

## Status and uncertainty semantics

The API preserves these domain statuses:

- `free`
- `occupied`
- `uncertain`
- `regular_timetable_not_applicable`
- `regular_timetable_not_authoritative`
- `regular_timetable_unavailable`
- `normalized_timetable_unavailable`
- `unknown_room` (represented as HTTP 404 at the API boundary)

`is_free` is true only for confirmed freedom, false for confirmed occupancy,
and null whenever the answer is unknown. Recess, examinations, public holidays,
and calendar exceptions are valid HTTP 200 domain responses rather than server
errors.

Free-room search never mixes uncertainty into `rooms`. With
`include_uncertain=true`, ambiguous rooms appear in `uncertain_rooms` with
reason codes. Without it, they are omitted.

Schedule meetings expose both scheduled and effective times. Confirmed and
uncertain sub-intervals are included for partial exceptions such as Students'
Union Day. Canonical source records are never modified.

## Errors

Protocol errors use a consistent envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request parameters are invalid.",
    "details": []
  }
}
```

Malformed input returns 422, unknown rooms and routes return 404, and an absent
database returns 503. Domain uncertainty remains HTTP 200.

## Database lifecycle and performance

Each request obtains one request-scoped query service/SQLite connection and
closes it after serialization. Route code does not issue row-level queries.
Date-aware free-room search batch-loads daily room meetings to avoid one query
per room. No cache is currently required.

The API is read-oriented, but the underlying normalization and scraper commands
remain separate CLI workflows. Production deployments should point the API at a
completed database and configure an explicit frontend-origin allowlist.
