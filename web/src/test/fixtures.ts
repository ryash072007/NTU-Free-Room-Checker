import type {
  CalendarContext,
  FreeRoomsResponse,
  Meeting,
  RoomAvailabilityResponse,
  RoomScheduleResponse,
} from "../api/types";

export const calendar: CalendarContext = {
  date: "2026-09-15",
  weekday: "TUE",
  academic_year: "AY2026-27",
  academic_year_start: 2026,
  semester: "1",
  period_type: "teaching_week",
  teaching_week: 6,
  regular_timetable_applicable: true,
  is_public_holiday: false,
  holiday: null,
  holiday_observed: false,
  exceptions: [],
};

export const meeting: Meeting = {
  course_code: "SC2008",
  course_title: "Computer Networks",
  index_number: "10234",
  class_type: "TUT",
  group: "T012",
  scheduled_start: "10:30",
  scheduled_end: "12:20",
  effective_start: "10:30",
  effective_end: "12:20",
  applicability: "applicable",
  remark: "Teaching Wk1-13",
  teaching_weeks: [1, 2, 3, 4, 5, 6],
  confirmed_intervals: [{ start: "10:30", end: "12:20" }],
  uncertain_intervals: [],
  reason_codes: [],
  reasons: [],
};

export function freeRooms(overrides: Partial<FreeRoomsResponse> = {}): FreeRoomsResponse {
  return {
    date: "2026-09-15",
    requested_start: "14:30",
    requested_end: "15:30",
    duration_minutes: 60,
    status: "ok",
    reason: "",
    calendar,
    rooms: [{ room: "LHN-TR+15", free_until: "19:00", free_duration_minutes: 270 }],
    uncertain_rooms: [],
    ...overrides,
  };
}

export function schedule(overrides: Partial<RoomScheduleResponse> = {}): RoomScheduleResponse {
  return {
    room: "LHN-TR+15",
    date: "2026-09-15",
    calendar,
    status: "ok",
    reason: "",
    meetings: [meeting],
    ...overrides,
  };
}

export function availability(
  overrides: Partial<RoomAvailabilityResponse> = {},
): RoomAvailabilityResponse {
  return {
    room: "LHN-TR+15",
    date: "2026-09-15",
    requested_start: "14:30",
    requested_end: "14:31",
    duration_minutes: 1,
    status: "free",
    is_free: true,
    free_until: "19:00",
    free_duration_minutes: 270,
    occupied_intervals: [],
    uncertain_intervals: [],
    reason_codes: [],
    reasons: [],
    calendar,
    ...overrides,
  };
}
