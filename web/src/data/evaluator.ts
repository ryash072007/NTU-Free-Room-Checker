import type { LocationRoomItem, RoomAvailabilityResponse } from "../api/types";
import type { StaticDay, StaticDayRoom } from "./types";

export const overlaps = (start: number, end: number, requestedStart: number, requestedEnd: number) =>
  start < requestedEnd && end > requestedStart;

export function clockToMinute(value: string) {
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
}

export function minuteToClock(value: number | null) {
  return value === null ? null : `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
}

export function evaluateRoom(room: string, day: StaticDay, time: string, duration: number): RoomAvailabilityResponse {
  const start = clockToMinute(time), end = start + duration;
  const base = { room, date: day.date, requested_start: time, requested_end: minuteToClock(end)!, duration_minutes: duration, calendar: day.calendar };
  if (day.status !== "ok") return { ...base, status: day.status as RoomAvailabilityResponse["status"], is_free: null, free_until: null, free_duration_minutes: null, occupied_intervals: [], uncertain_intervals: [], reason_codes: day.reason_code ? [day.reason_code] : [], reasons: day.reason ? [day.reason] : [] };
  if (day.unparsed_rooms.includes(room)) return { ...base, status: "uncertain", is_free: null, free_until: null, free_duration_minutes: null, occupied_intervals: [], uncertain_intervals: [], reason_codes: ["unparsed_timetable_meeting"], reasons: ["The room has a meeting with an unparsed day or time."] };
  const value: StaticDayRoom = day.rooms[room] ?? { status: "ok", reason: "", schedule: [], occupied_blocks: [], uncertain_blocks: [] };
  const occupied = value.occupied_blocks.filter(([s, e]) => overlaps(s, e, start, end));
  if (occupied.length) {
    const direct = value.schedule.some((meeting) => meeting.confirmed_intervals.some((i) => overlaps(clockToMinute(i.start), clockToMinute(i.end), start, end)));
    return { ...base, status: "occupied", is_free: false, free_until: null, free_duration_minutes: null,
      occupied_intervals: occupied.map(([s, e]) => ({ start: minuteToClock(s)!, end: minuteToClock(e)! })), uncertain_intervals: [],
      reason_codes: direct ? [] : ["room_transition_buffer"], reasons: direct ? [] : ["The room is in transition between consecutive classes."] };
  }
  const uncertain = value.uncertain_blocks.filter(([s, e]) => overlaps(s, e, start, end));
  if (uncertain.length) return { ...base, status: "uncertain", is_free: null, free_until: null, free_duration_minutes: null,
    occupied_intervals: [], uncertain_intervals: uncertain.map(([s, e]) => ({ start: minuteToClock(s)!, end: minuteToClock(e)! })),
    reason_codes: [...new Set(uncertain.flatMap((item) => item[2]))], reasons: [...new Set(uncertain.flatMap((item) => item[3]))] };
  const next = [...value.occupied_blocks, ...value.uncertain_blocks].map((item) => item[0]).filter((s) => s >= end).sort((a, b) => a - b)[0] ?? null;
  return { ...base, status: "free", is_free: true, free_until: minuteToClock(next), free_duration_minutes: next === null ? null : next - start,
    occupied_intervals: [], uncertain_intervals: [], reason_codes: [], reasons: [] };
}

export function locationItem(room: string, day: StaticDay, time: string, duration: number): LocationRoomItem {
  const result = evaluateRoom(room, day, time, duration);
  const end = result.occupied_intervals.reduce((latest, item) => Math.max(latest, clockToMinute(item.end)), -1);
  return { room, status: result.status, is_free: result.is_free, free_until: result.free_until,
    free_duration_minutes: result.free_duration_minutes, available_from: end < 0 ? null : minuteToClock(end), reason_codes: result.reason_codes, reasons: result.reasons };
}
