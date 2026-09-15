"""Policy evaluation between calendar context and canonical meetings."""

from dataclasses import dataclass
from enum import StrEnum

from ntu_room_checker.calendar.models import (
    CalendarException,
    DateResolution,
    ExceptionEffect,
    PeriodType,
    PopulationScope,
)


class ApplicabilityStatus(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    UNCERTAIN = "uncertain"


class TimetableAuthority(StrEnum):
    AUTHORITATIVE = "authoritative"
    NOT_APPLICABLE = "not_applicable"
    NOT_AUTHORITATIVE = "not_authoritative"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class MeetingApplicabilityResult:
    status: ApplicabilityStatus
    reason_code: str
    reason: str
    scheduled_start: int
    scheduled_end: int
    effective_start: int | None
    effective_end: int | None
    applied_exceptions: tuple[CalendarException, ...] = ()


@dataclass(frozen=True, slots=True)
class DatePolicyResult:
    authority: TimetableAuthority
    reason_code: str
    reason: str


class CalendarPolicyEngine:
    """Apply generic exception effects without knowledge of named NTU events."""

    def evaluate_date(self, resolution: DateResolution) -> DatePolicyResult:
        if resolution.is_public_holiday:
            return DatePolicyResult(
                TimetableAuthority.NOT_AUTHORITATIVE,
                "public_holiday_timetable_uncertain",
                "The date is a public or replacement holiday; the regular timetable "
                "does not establish physical-room availability.",
            )
        if resolution.regular_timetable_applicable:
            return DatePolicyResult(
                TimetableAuthority.AUTHORITATIVE,
                "regular_teaching_timetable",
                "The regular teaching timetable applies.",
            )
        if resolution.period_type == PeriodType.OUTSIDE_TERM:
            return DatePolicyResult(
                TimetableAuthority.UNAVAILABLE,
                "outside_calendar_timetable_unavailable",
                "No regular timetable is available for this calendar date.",
            )
        if resolution.period_type == PeriodType.REVISION_EXAM:
            return DatePolicyResult(
                TimetableAuthority.NOT_AUTHORITATIVE,
                "revision_exam_timetable_not_authoritative",
                "The regular class timetable is not authoritative during revision/examinations.",
            )
        return DatePolicyResult(
            TimetableAuthority.NOT_APPLICABLE,
            f"{resolution.period_type.value}_regular_timetable_not_applicable",
            f"The regular class timetable does not apply during {resolution.period_type.value}.",
        )

    def evaluate_meeting(
        self,
        resolution: DateResolution,
        start_minute: int,
        end_minute: int,
    ) -> MeetingApplicabilityResult:
        date_policy = self.evaluate_date(resolution)
        if date_policy.authority != TimetableAuthority.AUTHORITATIVE:
            return MeetingApplicabilityResult(
                ApplicabilityStatus.UNCERTAIN,
                date_policy.reason_code,
                date_policy.reason,
                start_minute,
                end_minute,
                start_minute,
                end_minute,
            )

        effective_end = end_minute
        applied: list[CalendarException] = []
        for exception in resolution.exceptions:
            if exception.effect == ExceptionEffect.INFORMATIONAL:
                continue
            if exception.effect == ExceptionEffect.TIMETABLE_NOT_AUTHORITATIVE:
                return self._uncertain(exception, start_minute, end_minute, "exception_scope_uncertain")
            if exception.effect == ExceptionEffect.CLASSES_END_AT:
                cutoff = exception.cutoff_minute
                assert cutoff is not None
                applied.append(exception)
                if start_minute >= cutoff:
                    return MeetingApplicabilityResult(
                        ApplicabilityStatus.NOT_APPLICABLE,
                        "after_official_class_end",
                        f"The meeting starts at or after the official {cutoff // 60:02d}:{cutoff % 60:02d} class-ending cutoff.",
                        start_minute, end_minute, None, None, tuple(applied),
                    )
                effective_end = min(effective_end, cutoff)
                continue
            if exception.effect == ExceptionEffect.NO_CLASSES and self._overlaps_exception(
                exception, start_minute, effective_end
            ):
                if exception.affected_population == PopulationScope.ALL:
                    return MeetingApplicabilityResult(
                        ApplicabilityStatus.NOT_APPLICABLE,
                        "official_no_classes_window",
                        exception.description,
                        start_minute, end_minute, None, None, (exception,),
                    )
                return self._uncertain(
                    exception, start_minute, end_minute, "population_scope_unknown"
                )

        reason_code = "effective_interval_adjusted" if effective_end != end_minute else "regular_timetable_meeting"
        reason = (
            "The effective meeting interval was shortened by an official class-ending cutoff."
            if effective_end != end_minute
            else "The regular timetable meeting applies."
        )
        return MeetingApplicabilityResult(
            ApplicabilityStatus.APPLICABLE, reason_code, reason,
            start_minute, end_minute, start_minute, effective_end, tuple(applied),
        )

    @staticmethod
    def _overlaps_exception(exception: CalendarException, start: int, end: int) -> bool:
        exception_start = exception.start_minute if exception.start_minute is not None else 0
        exception_end = exception.end_minute if exception.end_minute is not None else 24 * 60
        return start < exception_end and end > exception_start

    @staticmethod
    def _uncertain(
        exception: CalendarException, start: int, end: int, reason_code: str
    ) -> MeetingApplicabilityResult:
        return MeetingApplicabilityResult(
            ApplicabilityStatus.UNCERTAIN,
            reason_code,
            f"{exception.description} Timetable population/applicability cannot be resolved safely.",
            start, end, start, end, (exception,),
        )
