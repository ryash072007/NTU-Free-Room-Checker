# NTU Free Room Checker

Who wants to do trial and error when trying to find a free TR? This project will
eventually turn NTU timetable data into room availability. The current phase is
a reusable raw-data scraper for NTU's public class schedule.

## Schedule scraper

The scraper uses Playwright to read the academic-term and programme options from
the live page, submits each legitimate option sequentially, parses all module and
class rows, and stores the result in SQLite. It preserves NTU's raw day, time,
venue, teaching-week/remark, academic-unit, and module-remark strings. It also
handles rowspans and class rows whose index/type/group cells inherit from the
previous row.

No authentication, browser profile, OCR, or hardcoded programme list is used.

### Installation

Python 3.11 or newer is required.

```powershell
python -m pip install -e ".[dev]"
playwright install chromium
```

### Usage

Discover the current term and every option value:

```powershell
python -m ntu_room_checker scrape --list-programmes
```

Run a small test against the first five choices:

```powershell
python -m ntu_room_checker scrape --limit 5 --db data/test_schedule.db
```

Scrape one programme by its exact runtime-discovered value or label:

```powershell
python -m ntu_room_checker scrape --programme "CSC;;1;F"
python -m ntu_room_checker scrape --programme "Computer Science Year 1" --headed
```

Scrape every programme for the term selected by NTU's page:

```powershell
python -m ntu_room_checker scrape --db data/ntu_schedule.db
```

An older available term can be selected using its live option value:

```powershell
python -m ntu_room_checker scrape --academic-term "2025;2"
```

Useful reliability controls include `--timeout MS`, `--retries N`, `--delay
SECONDS`, and `--debug-dir debug`. The default is headless mode, three attempts,
a 60-second timeout, and a one-second delay between requests. Debug HTML is only
written after a failed attempt when `--debug-dir` is supplied. Run `python -m
ntu_room_checker scrape --help` for the complete command reference.

### Database and provenance

The default database is `data/ntu_schedule.db`. Database files and other runtime
artifacts are ignored by git.

- `scrape_runs` records source URL, detected term, timestamps, and aggregate status.
- `programme_selections` records the exact option value/label, attempts, errors,
  row count, timestamps, and per-selection status.
- `schedule_entries` records module metadata and each timetable row. `raw_data`
  is JSON containing the original named table fields and source table/row indexes.

Each entry receives a deterministic SHA-256 fingerprint. A uniqueness constraint
prevents duplicates within a programme snapshot, and retrying a selection replaces
its partial rows transactionally. Separate completed runs remain separate snapshots
so provenance and changes across refreshes are retained.

Use `--resume` to reuse the newest incomplete run for the same source and academic
term. Completed selections are skipped; pending and failed selections are tried
again. A completed prior run is never silently modified—`--resume` starts a new
snapshot in that case.

### Development and validation

Parser tests use local representative HTML, so they do not contact NTU:

```powershell
python -m pytest
```

Before a full refresh, use `--programme` or `--limit` and inspect the database,
for example with Python's built-in `sqlite3` module or the SQLite CLI.

### Known limitations

- The scraper preserves rather than normalizes NTU's time, venue, week, and
  academic-unit values.
- It depends on the public OWA page's form and result-table structure; fixture
  tests catch known rowspan/inheritance cases, while future NTU markup changes
  may require selector or parser updates.
- A valid selection with no published class rows is stored as a successful
  selection with zero entries.
- Historical snapshots intentionally repeat unchanged records across scrape runs;
  their fingerprints make later cross-run comparisons straightforward.

Free-room calculation, venue normalization, an API, and user interfaces are out
of scope for the raw scraping phase.

## Canonical timetable and room queries

The derived normalization pipeline keeps the raw scraper tables immutable while
building deterministic classes, meetings, rooms, parsed teaching weeks, and full
source-row provenance. See [the normalization model](docs/timetable-normalization.md)
for the measured data profile, deduplication rationale, conservative uncertainty
rules, schema, parsing coverage, and query examples.

Typical commands are:

```powershell
python -m ntu_room_checker profile
python -m ntu_room_checker normalize --rebuild --stats
python -m ntu_room_checker room-schedule "LHN-TR+15" --academic-year 2026 --semester 1 --day MON --week 3
python -m ntu_room_checker free-rooms --academic-year 2026 --semester 1 --day MON --time 1430 --duration 120 --week 3
```

No HTTP API, frontend, or calendar-date mapping is included yet.
