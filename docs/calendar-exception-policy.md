# Calendar exception policy

The exception policy sits between academic-calendar resolution and normalized
timetable queries:

```text
date -> calendar resolution -> date policy -> meeting policy
     -> effective/uncertain intervals -> room availability
```

It never changes raw or canonical timetable rows. It derives an auditable view
for one date and records the exceptions responsible for every adjustment.

## Source-data profile and population limits

Canonical classes expose course code/title, index, class type, group, and raw
provenance. Programme-selection labels describe discovery routes, not a reliable
UG/PG classification. Inspection of the AY2026-27 database found no explicit,
complete population field. Course-code or programme-name heuristics would
misclassify shared and cross-listed teaching, so UG/PG scope remains unresolved.

## Domain model

`CalendarException` has a stable ID, date, effect, population scope, optional
time window or cutoff, description, and source note. Effects are `no_classes`,
`classes_end_at`, `timetable_not_authoritative`, and `informational`.

`MeetingApplicabilityResult` uses `applicable`, `not_applicable`, or `uncertain`.
It retains scheduled intervals and exposes effective, confirmed, and uncertain
intervals, reason codes, and applied exceptions. The engine is event-name
independent: availability code does not know about Students' Union Day.

## Availability taxonomy

- `free`: confidently no applicable or uncertain meeting overlaps;
- `occupied`: a confirmed effective interval overlaps;
- `uncertain`: a potentially applicable interval overlaps;
- `regular_timetable_not_applicable`: orientation or recess;
- `regular_timetable_not_authoritative`: public holidays or revision/exams;
- `regular_timetable_unavailable`: outside the calendar, Sunday, or a gap;
- `normalized_timetable_unavailable`: no normalized dataset for the term;
- `unknown_room`: no matching physical room in that dataset.

`is_free` is true only for `free`, false only for `occupied`, and null for all
uncertainty and unavailability states.

## Students' Union Day

On 4 September 2026, the 10:30-14:30 no-class rule is scoped to undergraduate
programmes. Because meeting population cannot be classified safely:

- meeting portions outside the exception remain confirmed;
- overlapping portions are `uncertain` with `population_scope_unknown`;
- an affected room is excluded from confident free-room results;
- rooms without an overlapping meeting remain eligible as confidently free
  under the regular timetable.

A scheduled 10:00-12:00 meeting therefore has a confirmed 10:00-10:30 interval
and an uncertain 10:30-12:00 interval. It is not called cancelled.

## Holiday-eve class-ending rule

| Eve | Date | Cutoff |
| --- | --- | --- |
| Deepavali | 7 Nov 2026 | 14:30 |
| New Year's Day | 31 Dec 2026 | 14:30 |
| Chinese New Year | 5 Feb 2027 | 14:30 |
| Hari Raya Puasa | 9 Mar 2027 | 14:30 |

The official wording says classes end at 14:30. The implemented interpretation
is an effective-interval cutoff: 13:30-15:20 becomes 13:30-14:30, while a class
starting at or after 14:30 is `not_applicable`. Canonical scheduled times remain
unchanged and appear beside the effective interval in policy output. Half-open
boundaries mean a request starting at 14:30 does not overlap a class ending then.

This only describes regular scheduled teaching. It does not prove that a room is
physically empty after 14:30; ad-hoc bookings remain outside the dataset.

## Public holidays and replacement days

Actual and explicitly configured replacement holidays return
`regular_timetable_not_authoritative`, never confident free-room results. Room
schedules may retain scheduled rows, but their applicability is `uncertain`.

Only replacement Mondays shown by the PDF are configured for Sunday holidays.
No other replacement days are inferred. Monday after a Saturday holiday is not
marked as a holiday; its ordinary period still controls. Thus 3 May 2027 remains
an examination-period date independently of Labour Day on Saturday.

## Non-teaching periods

| Calendar context | Regular timetable | Physical availability |
| --- | --- | --- |
| Teaching/Special Term week | authoritative, subject to exceptions | queryable |
| Recess/orientation | not applicable | unknown |
| Revision/examination | not authoritative | unknown |
| Outside term/Sunday/gap | unavailable | unknown |

"No scheduled class according to the regular timetable" is not equivalent to
"the physical room is definitely available."

## Free-room and free-until behavior

Normal free-room results contain only confidently free rooms.
`--include-uncertain` returns uncertain rooms separately with reason codes; they
are never mixed into `rooms`. `free_until` uses policy-evaluated intervals. Both
the next confirmed and next uncertain interval bound confident freedom. Unparsed
day/time rows continue to disqualify a room conservatively.

## CLI

```powershell
python -m ntu_room_checker calendar-date 2026-09-04 --verbose

python -m ntu_room_checker room-availability "TR+15" `
  --date 2026-09-04 --time 1100 --duration 60 --explain

python -m ntu_room_checker free-rooms `
  --date 2026-09-04 --time 1100 --duration 60 `
  --include-uncertain --limit 20
```

Legacy AY/semester/week mode is a lower-level diagnostic path and does not apply
calendar exceptions.

## Intentionally unresolved

- UG/PG population classification is unavailable.
- Public-holiday wording is insufficient to declare all scheduled classes
  cancelled.
- Exam allocations, ad-hoc bookings, make-up lessons, and events are absent.
- Future effects require authoritative configuration and tests before they may
  alter effective intervals.
