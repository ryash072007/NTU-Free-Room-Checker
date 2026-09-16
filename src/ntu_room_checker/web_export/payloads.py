"""Static JSON payload adapters for calendar and timetable domain values."""

from __future__ import annotations

from typing import Any

from ntu_room_checker.calendar.models import DateResolution
from ntu_room_checker.normalization.venue import normalize_venue
from ntu_room_checker.queries.calendar_service import DateScheduleResult


def minute_to_clock(value: int | None) -> str | None:
    if value is None:
        return None
    return f"{value // 60:02d}:{value % 60:02d}"


def _without_none(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}


def calendar_payload(value: DateResolution) -> dict[str, Any]:
    return _without_none({
        "date": value.date.isoformat(),
        "weekday": value.weekday,
        "academic_year": value.academic_year_label,
        "academic_year_start": value.academic_year,
        "semester": value.semester,
        "period_type": value.period_type.value,
        "teaching_week": value.teaching_week,
        "regular_timetable_applicable": value.regular_timetable_applicable,
        "is_public_holiday": value.is_public_holiday,
        "holiday": value.holiday_name,
        "holiday_observed": value.holiday_observed,
        "exceptions": [
            {
                "id": item.exception_id,
                "effect": item.effect.value,
                "date": item.date.isoformat(),
                "start": minute_to_clock(item.start_minute),
                "end": minute_to_clock(item.end_minute),
                "cutoff": minute_to_clock(item.cutoff_minute),
                "affected_population": item.affected_population.value,
                "description": item.description,
                "source_note": item.source_note,
            }
            for item in value.exceptions
        ],
    })


def _interval(value: tuple[int, int]) -> dict[str, str | None]:
    return {"start": minute_to_clock(value[0]), "end": minute_to_clock(value[1])}


def schedule_payload(room: str, result: DateScheduleResult) -> dict[str, Any]:
    meetings = []
    for item in result.evaluated_meetings:
        meeting = item.meeting
        decision = item.applicability
        meetings.append(_without_none({
            "course_code": meeting.course_code,
            "course_title": meeting.course_title,
            "index_number": meeting.index_number,
            "class_type": meeting.class_type,
            "group": meeting.group_name,
            "scheduled_start": minute_to_clock(decision.scheduled_start),
            "scheduled_end": minute_to_clock(decision.scheduled_end),
            "effective_start": minute_to_clock(decision.effective_start),
            "effective_end": minute_to_clock(decision.effective_end),
            "applicability": decision.status.value,
            "remark": meeting.remark,
            "teaching_weeks": list(meeting.teaching_weeks),
            "confirmed_intervals": [_interval(value) for value in decision.confirmed_intervals],
            "uncertain_intervals": [_interval(value) for value in decision.uncertain_intervals],
            "reason_codes": [] if decision.reason_code == "regular_timetable_meeting" else [decision.reason_code],
            "reasons": [] if decision.reason_code == "regular_timetable_meeting" else [decision.reason],
        }))
    return {
        "room": normalize_venue(room).normalized,
        "date": result.calendar.date.isoformat(),
        "calendar": calendar_payload(result.calendar),
        "status": result.status,
        "reason": result.reason,
        "meetings": meetings,
    }
