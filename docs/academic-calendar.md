# AY2026-27 academic calendar resolution

The auditable configuration is
[`ay2026_27.py`](../src/ntu_room_checker/calendar/calendars/ay2026_27.py).
It was audited and manually transcribed from the official NTU **Academic Calendar
(Semester): AY2026-27** PDF, published 10 March 2026. Core resolution remains
AY-independent in `calendar/models.py` and `calendar/resolver.py`.

## Semester 1

| Period | Date range |
| --- | --- |
| Orientation Activities | 20 Jul-6 Aug 2026 |
| Teaching Week 1 | 10-15 Aug |
| Teaching Week 2 | 17-22 Aug |
| Teaching Week 3 | 24-29 Aug |
| Teaching Week 4 | 31 Aug-5 Sep |
| Teaching Week 5 | 7-12 Sep |
| Teaching Week 6 | 14-19 Sep |
| Teaching Week 7 | 21-26 Sep |
| Recess | 28 Sep-2 Oct |
| Teaching Week 8 | 5-10 Oct |
| Teaching Week 9 | 12-17 Oct |
| Teaching Week 10 | 19-24 Oct |
| Teaching Week 11 | 26-31 Oct |
| Teaching Week 12 | 2-7 Nov |
| Teaching Week 13 | 9-14 Nov |
| Revision/examination block 1 | 16-20 Nov |
| Revision/examination block 2 | 23-27 Nov |
| Revision/examination block 3 | 30 Nov-4 Dec |

## Semester 2

| Period | Date range |
| --- | --- |
| Orientation Activities (PG only) | 4-8 Jan 2027 |
| Teaching Week 1 | 11-16 Jan |
| Teaching Week 2 | 18-23 Jan |
| Teaching Week 3 | 25-30 Jan |
| Teaching Week 4 | 1-6 Feb |
| Teaching Week 5 | 8-13 Feb |
| Teaching Week 6 | 15-20 Feb |
| Teaching Week 7 | 22-27 Feb |
| Recess | 1-5 Mar |
| Teaching Week 8 | 8-13 Mar |
| Teaching Week 9 | 15-20 Mar |
| Teaching Week 10 | 22-27 Mar |
| Teaching Week 11 | 29 Mar-3 Apr |
| Teaching Week 12 | 5-10 Apr |
| Teaching Week 13 | 12-17 Apr |
| Revision/examination block 1 | 19-23 Apr |
| Revision/examination block 2 | 26-30 Apr |
| Revision/examination block 3 | 3-7 May |

## Special Term

| Period | Date range |
| --- | --- |
| Teaching Week 1 | 10-15 May 2027 |
| Teaching Week 2 | 17-22 May |
| Teaching Week 3 | 24-29 May |
| Teaching Week 4 | 31 May-5 Jun |
| Teaching Week 5 | 7-12 Jun |
| Teaching Week 6 | 14-19 Jun |
| Teaching Week 7 | 21-26 Jun |
| Teaching Week 8 | 28 Jun-3 Jul |
| Teaching Week 9 | 5-10 Jul |
| Teaching Week 10 | 12-17 Jul |
| Teaching Week 11 | 19-24 Jul |
| Teaching Week 12 | 26-31 Jul |

The PDF shows all twelve Special Term teaching weeks continuously. There are no
Special Term recess periods or inferred August weeks. The first Monday after the
term, 2 August 2027, resolves as `outside_term`.

Teaching weeks are explicit Monday-Saturday ranges. Sundays are not assigned to
an adjacent teaching week. Recess and revision/examination dates follow the
colored dates in the PDF; uncolored intervening weekend dates resolve as
`outside_term` and never imply room availability.

## Public holidays and policy

Holiday status is independent of academic-period status. The resolver does not
invent a class-cancellation policy.

| Date | Holiday |
| --- | --- |
| 9 Aug 2026 | National Day |
| 10 Aug 2026 | National Day replacement holiday |
| 8 Nov 2026 | Deepavali |
| 9 Nov 2026 | Deepavali replacement holiday |
| 25 Dec 2026 | Christmas Day |
| 1 Jan 2027 | New Year's Day |
| 6-7 Feb 2027 | Chinese New Year |
| 8 Feb 2027 | Chinese New Year replacement holiday |
| 10 Mar 2027 | Hari Raya Puasa |
| 26 Mar 2027 | Good Friday |
| 1 May 2027 | Labour Day |
| 17 May 2027 | Hari Raya Haji |
| 20 May 2027 | Vesak Day |

The PDF states that classes proceed normally on the immediate Monday after a
Saturday public holiday. When a public holiday falls on Sunday, Monday is a
replacement holiday. The configuration creates replacement records only for the
Sunday cases shown; it does not generalize beyond the PDF.

The rule that classes end at 14:30 on the eves of New Year's Day, Chinese New
Year, Hari Raya Puasa, and Deepavali is stored as a structured
`EarlyDismissalPolicy`. It is metadata only: meetings are not silently shortened
without reliable row-level override semantics.

## Students' Union Day exception

The University Key Events table is encoded as a structured exception:

| Field | Value |
| --- | --- |
| Date | 4 Sep 2026 |
| Time | 10:30-14:30 |
| Affected population | Undergraduate programmes |
| Description | No classes for UG programmes from 1030 to 1430 hours. |

The normalized timetable cannot reliably distinguish UG from PG applicability.
Room schedules retain their rows and return `ok_with_calendar_exception`.
Free-room and direct availability queries overlapping this window return
`calendar_exception_unapplied` and no rooms, rather than guessing which meetings
are cancelled.

## Resolution and conservative behavior

`CalendarResolver.resolve()` returns AY, semester, ISO weekday, period type,
teaching week, holiday metadata, structured date exceptions, and
`regular_timetable_applicable`.

Date-aware queries refuse to claim availability with these statuses:

- `regular_timetable_not_applicable`: orientation, recess,
  revision/examination, Sunday/gap, or outside-term date;
- `calendar_exception_unapplied`: an overlapping scoped no-class exception;
- `normalized_timetable_unavailable`: that semester is not normalized;
- `unknown_room`: the room is absent from normalized physical rooms.

The calendar governs regular teaching only. It does not prove rooms are unused
during holidays, recess, examinations, orientation, weekends, or exceptional
events. Exam allocations, ad-hoc bookings, replacement lessons, and events are
outside the current timetable dataset.

All dates are subject to change at the discretion of the University, as stated
in the PDF. A newly published calendar requires an explicit configuration update
and boundary-test audit.

## CLI examples

```powershell
python -m ntu_room_checker calendar-date 2026-09-15
python -m ntu_room_checker room-schedule "LHN-TR+15" --date 2026-09-15
python -m ntu_room_checker free-rooms --date 2026-09-15 --time 1430 --duration 120 --limit 20
python -m ntu_room_checker room-availability "LHN-TR+15" --date 2026-09-14 --time 1430 --duration 120
```

Legacy `--academic-year`, `--semester`, `--day`, and `--week` mode remains for
debugging.

## Adding another academic year

1. Add a module under `calendar/calendars/` with explicit periods, holidays,
   exceptions, and policies.
2. Construct an `AcademicCalendar` with source and change-warning notes.
3. Register it in `default_resolver()`.
4. Add tests for every colored period boundary, holiday, and exception.
5. Scrape and normalize those semesters before allowing availability responses.
