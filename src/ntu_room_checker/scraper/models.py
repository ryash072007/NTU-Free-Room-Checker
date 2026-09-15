"""Data models shared by discovery, parsing, and storage."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class AcademicTerm:
    value: str
    label: str
    academic_year: str
    semester: str


@dataclass(frozen=True, slots=True)
class ProgrammeOption:
    value: str
    label: str


@dataclass(frozen=True, slots=True)
class ScheduleEntry:
    course_code: str
    course_title: str
    academic_units: str
    course_remark: str
    index_number: str
    class_type: str
    group_name: str
    day: str
    time: str
    venue: str
    remark: str
    raw_fields: dict[str, Any] = field(default_factory=dict)
