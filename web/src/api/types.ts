export type AvailabilityStatus =
  | "free"
  | "occupied"
  | "uncertain"
  | "regular_timetable_not_applicable"
  | "regular_timetable_not_authoritative"
  | "regular_timetable_unavailable"
  | "normalized_timetable_unavailable";

export interface CalendarException {
  id: string;
  effect: string;
  date: string;
  start: string | null;
  end: string | null;
  cutoff: string | null;
  affected_population: string;
  description: string;
  source_note: string;
}

export interface CalendarContext {
  date: string;
  weekday: string;
  academic_year: string | null;
  academic_year_start: number | null;
  semester: string | null;
  period_type: string;
  teaching_week: number | null;
  regular_timetable_applicable: boolean;
  is_public_holiday: boolean;
  holiday: string | null;
  holiday_observed: boolean;
  exceptions: CalendarException[];
}

export interface TimeInterval {
  start: string;
  end: string;
}

export interface RoomSearchItem {
  id: string;
  name: string;
}

export interface RoomSearchResponse {
  rooms: RoomSearchItem[];
  count: number;
}

export interface FreeRoomItem {
  room: string;
  free_until: string | null;
  free_duration_minutes: number | null;
  class_types: string[];
  capacity: number | null;
  bookable_by_staff: boolean | null;
  bookable_by_student_orgs: boolean | null;
}

export interface UncertainRoomItem {
  room: string;
  reason_codes: string[];
  reasons: string[];
  class_types: string[];
  capacity: number | null;
  bookable_by_staff: boolean | null;
  bookable_by_student_orgs: boolean | null;
}

export interface FreeRoomsResponse {
  date: string;
  requested_start: string;
  requested_end: string;
  duration_minutes: number;
  status: AvailabilityStatus | "ok";
  reason: string;
  calendar: CalendarContext;
  rooms: FreeRoomItem[];
  uncertain_rooms: UncertainRoomItem[];
}

export interface Meeting {
  course_code: string;
  course_title: string;
  index_number: string;
  class_type: string;
  group: string;
  scheduled_start: string;
  scheduled_end: string;
  effective_start: string | null;
  effective_end: string | null;
  applicability: "applicable" | "not_applicable" | "uncertain";
  remark: string;
  teaching_weeks: number[];
  confirmed_intervals: TimeInterval[];
  uncertain_intervals: TimeInterval[];
  reason_codes: string[];
  reasons: string[];
}

export interface RoomScheduleResponse {
  room: string;
  date: string;
  calendar: CalendarContext;
  status: AvailabilityStatus | "ok" | "ok_with_adjustments";
  reason: string;
  meetings: Meeting[];
  class_types: string[];
  capacity: number | null;
  bookable_by_staff: boolean | null;
  bookable_by_student_orgs: boolean | null;
}

export interface RoomAvailabilityResponse {
  room: string;
  date: string;
  requested_start: string;
  requested_end: string;
  duration_minutes: number;
  status: AvailabilityStatus;
  is_free: boolean | null;
  free_until: string | null;
  free_duration_minutes: number | null;
  occupied_intervals: TimeInterval[];
  uncertain_intervals: TimeInterval[];
  reason_codes: string[];
  reasons: string[];
  calendar: CalendarContext;
}

export interface ApiErrorPayload {
  error?: { code?: string; message?: string };
}

export interface LocationItem {
  id: string;
  name: string;
  official_name: string | null;
  short_name: string;
  aliases: string[];
  room_count: number;
}

export interface LocationRoomItem {
  room: string;
  status: AvailabilityStatus;
  is_free: boolean | null;
  free_until: string | null;
  free_duration_minutes: number | null;
  available_from: string | null;
  reason_codes: string[];
  reasons: string[];
  class_types: string[];
  capacity: number | null;
  bookable_by_staff: boolean | null;
  bookable_by_student_orgs: boolean | null;
}

export interface LocationRoomsResponse {
  location: LocationItem;
  date: string;
  requested_time: string;
  duration_minutes: number;
  status: AvailabilityStatus | "ok";
  reason: string;
  calendar: CalendarContext;
  rooms: LocationRoomItem[];
}
