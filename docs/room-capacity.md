# Room type, capacity, and booking eligibility

This adds two independent, evidence-based signals on top of the canonical room
catalog: a room-type classification derived from the timetable itself, and a
capacity/booking-eligibility join against NTU's public facility list. Neither
infers anything from a room's name; both follow the same no-guessing rules as
`docs/room-locations.md`.

## Room type: `class_types`

NTU's own `class_type` value (`LEC/STUDIO`, `TUT`, `SEM`, `LAB`, `PRJ`, `DES`
in the current dataset) is recorded on every class meeting by the source
timetable and already survives normalization on `class_meetings.class_type`
and the per-day static export (`schedule[].class_type`). This feature reuses
that value directly as the room-type signal; it never pattern-matches room
name substrings such as `LT`/`TR`/`SR`.

`TimetableQueries.class_types_by_room` counts each room's canonical meetings
per `class_type` and keeps:

- the single dominant type (highest meeting count) unconditionally, and
- any other type that accounts for at least 20% of the room's meetings.

This threshold was chosen by inspecting the actual distribution across the
committed AY2026-27 Semester 1 export (`web/public/data/days/*.json`, 532
rooms): 333 rooms have exactly one observed type, and of the 199 rooms with
more than one, most of the "extra" types are a single stray booking (1-2% of
that room's meetings) rather than genuine mixed use. A 20% floor keeps a
single-use room single-type while still surfacing genuinely mixed-use rooms
(for example a lab room split roughly 75%/25% between `LAB` and `TUT`
bookings). The result lands in `rooms.json` as `class_types: string[]`,
omitted only if a room somehow has no canonical meetings at all.

## Capacity and booking eligibility

NTU's public [Facility Location and Capacity list](https://wis.ntu.edu.sg/pls/webexe88/FBSDOCU.FBSLOCATN)
(the same source `docs/room-locations.md` uses for the location catalog) also
publishes SPINES, FACILITY, CAPACITY, LOCATION, "Bookable by staff", and
"Bookable by student organisations" across North Spine, Sci Building, South
Spine, and The Arc — 232 rows as of this writing. The page's own note says it
lists LTs and TRs only, so seminar rooms, labs, NIE rooms, and school-specific
venues legitimately have no capacity data; that gap is not filled in by
guessing.

### Scrape and storage

`ntu-room-checker scrape-facility-list --db data/ntu_schedule.db` fetches the
page and stores every parsed row's raw and parsed fields in
`facility_list_runs`/`facility_list_entries` in the same database file the
schedule scraper uses (`src/ntu_room_checker/scraper/facility_list.py`),
following the same raw-provenance pattern as `scraper/storage.py`: a row with
a blank capacity or a non-YES/NO bookable cell is still stored, with its
parsed field left `NULL`, so a page-layout change is visible in the data
rather than silently dropped. A run that parses zero rows raises instead of
"succeeding" with an empty snapshot.

### Join

`normalization/facility_join.py` joins each facility row to a canonical room
using the *same* `normalize_venue` pass already used for canonical room
identity — never a separate ad hoc string match — plus one narrow, evidence
-based extra step: leading zeros are stripped from a trailing `+<digits>`
suffix on both sides before comparing (`LHN-TR+01` and `LHN-TR+1` are the
same room). This is scoped to numeric zero-padding only; it is not fuzzy or
substring matching, it is a no-op on identifiers that are not zero-padded
(so it never changes an existing exact match), and if stripping would ever
make two *distinct* canonical rooms collide (e.g. a run that somehow has both
`TR+1` and `TR+01` as separate canonical identifiers) the row is left
unjoined as ambiguous rather than picking one arbitrarily. A row joins only
when:

- its capacity, "bookable by staff", and "bookable by student orgs" cells all
  parsed (an incomplete row is left unjoined, never defaulted), and
- its normalized, zero-suffix-stripped facility code equals exactly one
  canonical room's normalized, zero-suffix-stripped identifier (an ambiguous
  many-to-one collision is left unjoined for every row involved, not
  force-picked).

The join runs automatically at the end of `ntu-room-checker normalize` (a
no-op, leaving all rooms without capacity fields, if `scrape-facility-list`
has never been run against that database). Matched rooms get `capacity`,
`bookable_by_staff`, and `bookable_by_student_orgs` written onto their `rooms`
row; those fields are then included on the matching room in `rooms.json` only
for a confirmed join — omitted entirely, not `null`, for everything else.

### Measured coverage

Running the real scraper and join against the committed AY2026-27 Semester 1
room catalog (532 canonical rooms) on 2026-09-17 matched **185 of 232**
facility-list rows (79.7%). All 47 unmatched rows fell into one underlying
reason — `no_canonical_room`, i.e. normalizing (and zero-suffix-stripping)
the facility code found no canonical room with that identifier for the
current semester — for a mix of legitimate reasons:

- **Non-teaching facilities** the page lists alongside LTs/TRs but that never
  appear in a class timetable: `RECEP RM`, `FOYER`, `EXHIB GALY`, `FN RM` (4
  rows).
- **Rooms with zero scheduled classes this semester.** The canonical room
  catalog only contains rooms that appear in at least one timetable meeting
  (see `docs/timetable-normalization.md`), so a physical facility that simply
  wasn't used for a class this term has no canonical identifier to join
  against — this is expected, not a parsing failure. It accounts for the
  large majority of the gap (42 rows): `TRX122`; `S3.2 ESR3` (no canonical
  `ESR3` this term, independent of how the code is split); both `ICC-LAB1`
  and `ICC-LAB2` (dedicated co-working spaces, never scheduled as class
  venues, so absent from the catalog regardless of code-extraction quality);
  several higher-numbered `LHN-TR+3x`/`4x`/`5x` rooms; and all 23
  `LHS-TR+1`-`LHS-TR+23` rows, most of which the list itself marks
  "Repurposed for I&E Use", "to be repurposed", or "Booked by TUM Asia".
- **One genuine code-extraction miss**: `S3.2 ESR4` splits (by the
  leading-uppercase-run heuristic in `_extract_code`) into a code that
  includes `S3.2`, but the canonical room this semester is `ESR4` on its own.
  This is a real, documented gap in the code-splitting heuristic (not a
  zero-padding issue), and it is intentionally not special-cased further —
  doing so would mean guessing which leading token(s) of a multi-word,
  all-uppercase facility name are "really" the room code, which risks a wrong
  join on some other row shaped the same way.

Earlier documentation for this feature incorrectly attributed 9 of these rows
(`LHN-TR+01`-`LHN-TR+09`) to a zero-padding mismatch. Re-verification found
this was wrong: the timetable's own venue strings for that specific room
range are *already* zero-padded (`LHN-TR+01`, not `LHN-TR+1`), so those 9
rows were matching correctly even before the zero-suffix-stripping join step
existed. The stripping step is still worth keeping — it is correctly scoped,
fully tested (`tests/test_facility_join.py`), and protects against a genuine
instance of this class of mismatch if a future scrape or schedule update ever
produces one — but it recovers 0 rows in the current dataset; measured
coverage is unchanged at 185/232.

Re-running the scrape later in the semester, or after a schedule update, will
change this count as rooms move in and out of the canonical catalog; rerun
`ntu-room-checker scrape-facility-list` and `normalize` and re-check
`rooms_with_capacity` in the `normalize --stats` output rather than assuming
these numbers hold.

## Frontend

`web/public/data/rooms.json` carries the new fields per room
(`class_types`, `capacity`, `bookable_by_staff`, `bookable_by_student_orgs`),
threaded through `web/src/data/types.ts` and `web/src/api/types.ts`. The
Browse Rooms page (`LocationsPage.tsx`) adds a room-type dropdown (options are
derived from whatever `class_types` values are actually present in the
current result set — never a hardcoded list), a "Fits N+" capacity dropdown
matching the existing duration control's style, and a "Bookable by student
organisations" toggle. All three are pure client-side filters over data
already loaded; they never trigger a new query. The room schedule page
(`RoomPage.tsx`) shows the same fields as a short info line under the room
name when present, and omits it entirely for a room with no type or capacity
evidence.
