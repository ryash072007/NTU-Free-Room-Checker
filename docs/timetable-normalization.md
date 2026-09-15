# Timetable normalization

This document records the model and the observed AY 2026 Semester 1 dataset used
to choose it. Re-run `python -m ntu_room_checker profile` and `python -m
ntu_room_checker normalize --stats` after future scrapes instead of assuming the
numbers remain constant.

## Raw profile and canonical identity

The validated source run contains 514,394 rows, 1,138 course codes, 682 programme
selections, 554 raw venue strings, 7 day strings, 85 time strings (including the
blank value), and 137 remarks. Blank counts are 12 day, 12 time, 159 venue, and
148,537 remark values.

Candidate grouping results were:

| Candidate identity | Rows |
| --- | ---: |
| Raw programme-provenance rows | 514,394 |
| AY/semester/course/index only | 4,591 |
| Plus class type and group | 7,013 |
| Plus day, time, venue, and remark | 8,952 |
| Full meeting key without index | 5,910 |
| Full meeting key without venue | 8,146 |
| Full meeting key without group | 8,952 |
| Full meeting key without remark | 8,952 |

The canonical class key is AY, semester, course code, index, class type, and
group. There are 2,073 course/index pairs with multiple type/group combinations,
so type and group cannot safely be omitted. A meeting adds raw day, time, venue,
and remark. Index and venue are retained because removing either causes material,
potentially unsafe merging. Group and remark remain in the deterministic key even
though they happen not to change this snapshot's count.

The resulting pipeline is:

```text
514,394 raw rows -> 7,013 canonical classes -> 8,952 meetings -> 532 physical rooms
```

This is a 98.260% reduction in meeting rows caused by eliminating repeated
programme discovery provenance. All 514,394 source rows remain linked. Of 8,952
meetings, 8,595 have more than one raw source, and the most repeated meeting has
272 sources.

## Derived schema

- `normalization_runs` identifies the source scrape and schema version.
- `canonical_classes` stores immutable class identity and module metadata.
- `class_meetings` stores raw and parsed day/time/venue/week fields.
- `meeting_weeks` explicitly lists confidently parsed teaching weeks.
- `rooms` contains conservatively normalized physical venue identifiers.
- `meeting_source_entries` maps every meeting back to every raw source row.

Rebuilding deletes only the selected derived normalization snapshot through
foreign-key cascades. It never updates or deletes `schedule_entries`.

## Parsing coverage and uncertainty

All 84 nonblank time strings have the observed `HHMM-HHMM` format and parse to
ordered minute offsets. Of the canonical meetings, 8,949 times and 8,949 weekdays
parse; three retain missing day and time values. The observed weekday values are
MON through SAT plus blank.

Venue classification at meeting level is 8,840 physical, 75 online, 9 blank/none,
7 unknown (`TBA`, `TBC`, and `ADM VENUE`), and 21 other. The latter include
`OVERSEAS`, `RECORDED`, `RECORDING`, `SITE VISIT`, and observed date expressions
such as `3 AUG` and `4&11 AUG` misplaced in the venue column. Balanced quote wrappers found
on 16 raw venue rows are removed only from the normalized alias; `venue_raw`
retains them. No other punctuation aliases are inferred. This produces 532 unique
physical rooms.

The remark profile consists of 135 distinct `Teaching Wk...` expressions, one
blank pattern, and `Not conducted during Teaching Weeks`. All explicit week
expressions parse into weeks 1–13: 4,601 canonical meetings are parsed, 4,335 have
blank/unspecified applicability, and 16 are explicitly outside teaching weeks.

Blank week applicability is deliberately `unspecified_conservative`. When a
teaching week is requested it is treated as potentially occupied in that week.
Future unknown remark formats receive `unparsed_conservative` and behave the same
way. They are never used as evidence that a room is free. Explicit “Not conducted
during Teaching Weeks” rows do not occupy weeks 1–13, but remain stored.

## Query semantics

Availability uses half-open intervals. A meeting conflicts exactly when:

```text
meeting_start < requested_end AND meeting_end > requested_start
```

Therefore 10:00–11:00 does not conflict with 11:00–12:00, while a request starting
at 10:59 does. A physical room with any applicable unparsed day or time is excluded
from free-room results. Omitting `--week` asks the conservative question across
all meeting patterns, not for a specific calendar date.

No calendar-date-to-teaching-week mapping is implemented. Recess weeks, holidays,
and term dates require authoritative calendar configuration before date queries
can be safe.

## Commands

```powershell
python -m ntu_room_checker profile --db data/ntu_schedule.db
python -m ntu_room_checker normalize --db data/ntu_schedule.db --rebuild --stats
python -m ntu_room_checker room-schedule "LHN-TR+15" --academic-year 2026 --semester 1 --day MON --week 3
python -m ntu_room_checker free-rooms --academic-year 2026 --semester 1 --day MON --time 1430 --duration 120 --week 3 --limit 20
python -m pytest
```
