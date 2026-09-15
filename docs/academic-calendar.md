# AY2026-27 academic calendar resolution

The auditable calendar configuration is
[`ay2026_27.py`](../src/ntu_room_checker/calendar/calendars/ay2026_27.py).
It was manually transcribed from the supplied official NTU **Academic Calendar
(Semester): AY2026-27** image. Core resolution is generic and lives in
`calendar/models.py` and `calendar/resolver.py`; it contains no AY-specific date
logic.

## Semester 1

| Period | Date range |
| --- | --- |
| Orientation | 20 Jul–6 Aug 2026 |
| Teaching Week 1 | 10–15 Aug |
| Teaching Week 2 | 17–22 Aug |
| Teaching Week 3 | 24–29 Aug |
| Teaching Week 4 | 31 Aug–5 Sep |
| Teaching Week 5 | 7–12 Sep |
| Teaching Week 6 | 14–19 Sep |
| Teaching Week 7 | 21–26 Sep |
| Recess | 28 Sep–3 Oct |
| Teaching Week 8 | 5–10 Oct |
| Teaching Week 9 | 12–17 Oct |
| Teaching Week 10 | 19–24 Oct |
| Teaching Week 11 | 26–31 Oct |
| Teaching Week 12 | 2–7 Nov |
| Teaching Week 13 | 9–14 Nov |
| Revision/examination | 16 Nov–4 Dec |

## Semester 2

| Period | Date range |
| --- | --- |
| Orientation | 4–8 Jan 2027 |
| Teaching Week 1 | 11–16 Jan |
| Teaching Week 2 | 18–23 Jan |
| Teaching Week 3 | 25–30 Jan |
| Teaching Week 4 | 1–6 Feb |
| Teaching Week 5 | 8–13 Feb |
| Teaching Week 6 | 15–20 Feb |
| Teaching Week 7 | 22–27 Feb |
| Recess | 1–6 Mar |
| Teaching Week 8 | 8–13 Mar |
| Teaching Week 9 | 15–20 Mar |
| Teaching Week 10 | 22–27 Mar |
| Teaching Week 11 | 29 Mar–3 Apr |
| Teaching Week 12 | 5–10 Apr |
| Teaching Week 13 | 12–17 Apr |
| Revision/examination | 19 Apr–7 May |

## Special Term

| Period | Date range |
| --- | --- |
| Teaching Weeks 1–4 | 10 May–5 Jun 2027, as four explicit Mon–Sat ranges |
| Recess | 7–12 Jun |
| Teaching Weeks 5–8 | 14 Jun–10 Jul, as four explicit Mon–Sat ranges |
| Recess | 12–17 Jul |
| Teaching Weeks 9–10 | 19–31 Jul, as two explicit Mon–Sat ranges |
| Teaching Weeks 11–12 | 2–14 Aug, as two explicit Mon–Sat ranges |

The supplied image labels the last Special Term block “Teaching Wk 9-12” but its
visible month grid ends at 31 July. Weeks 11 and 12 are encoded as the continuing
Monday–Saturday weeks of 2–7 and 9–14 August. Each returned resolution for those
dates carries a `source_note` explaining that inference. This is the sole calendar
range not directly visible as numbered dates in the supplied image.

Sundays and one-day gaps between the colored Monday–Saturday blocks are not
silently assigned to a teaching week. They resolve as `outside_term` unless the
date is independently listed as a public holiday.

## Public holidays

Public-holiday status is independent of academic-period status. A holiday may
therefore also resolve as a teaching week; the resolver does not invent a
class-cancellation policy.

| Date | Holiday |
| --- | --- |
| 9 Aug 2026 | National Day |
| 10 Aug 2026 | National Day replacement holiday |
| 8 Nov 2026 | Deepavali |
| 9 Nov 2026 | Deepavali replacement holiday |
| 25 Dec 2026 | Christmas Day |
| 1 Jan 2027 | New Year's Day |
| 6–7 Feb 2027 | Chinese New Year |
| 8 Feb 2027 | Chinese New Year replacement holiday |
| 10 Mar 2027 | Hari Raya Puasa |
| 26 Mar 2027 | Good Friday |
| 1 May 2027 | Labour Day |
| 17 May 2027 | Hari Raya Haji |
| 20 May 2027 | Vesak Day |

The image notes that classes proceed normally on the immediate Monday after a
Saturday public holiday, while a Sunday public holiday receives a Monday
replacement. It also notes 14:30 dismissal on the eves of New Year's Day, Chinese
New Year, Hari Raya Puasa, and Deepavali. Exact “eve” dates and partial-day
timetable policies are not inferred by this backend.

## Resolution and safety behavior

`CalendarResolver.resolve()` returns AY, semester, ISO weekday, period type,
teaching week, holiday metadata, and `regular_timetable_applicable`.

Date-aware room queries delegate to the existing canonical timetable engine only
when regular timetable applicability is established. Otherwise they return one
of these explicit statuses without claiming availability:

- `regular_timetable_not_applicable` for orientation, recess,
  revision/examination, and outside-term dates;
- `normalized_timetable_unavailable` when a date resolves correctly but that
  semester has not been scraped and normalized;
- `unknown_room` when a requested physical room is absent from normalized data.

The academic calendar describes regular teaching. It does not prove that rooms
are physically unused during recess, examinations, holidays, orientation,
weekends, or gaps between periods. Exam allocations, ad-hoc bookings, events, and
replacement lessons are outside the current dataset.

## CLI examples

```powershell
python -m ntu_room_checker calendar-date 2026-09-15
python -m ntu_room_checker room-schedule "LHN-TR+15" --date 2026-09-15
python -m ntu_room_checker free-rooms --date 2026-09-15 --time 1430 --duration 120 --limit 20
python -m ntu_room_checker room-availability "LHN-TR+15" --date 2026-09-14 --time 1430 --duration 120
```

The legacy `--academic-year`, `--semester`, `--day`, and `--week` query mode
remains available for debugging.

## Adding AY2027-28

1. Add a new module under `calendar/calendars/` with explicit `CalendarPeriod`
   and `PublicHoliday` values.
2. Construct an `AcademicCalendar` with its source and ambiguity notes.
3. Register it in `default_resolver()`.
4. Add boundary tests for every teaching/recess/exam transition and holiday.
5. Scrape and normalize the corresponding semesters before enabling availability
   responses for them.
