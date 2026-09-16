import { ApiError } from "../api/client";
import type { FreeRoomsResponse, LocationRoomsResponse, RoomAvailabilityResponse, RoomScheduleResponse, RoomSearchResponse } from "../api/types";
import { cachedJson } from "./cache";
import { evaluateRoom, locationItem } from "./evaluator";
import type { StaticDay, StaticLocations, StaticRooms } from "./types";

const DATA = "/data";
const rooms = (signal?: AbortSignal) => cachedJson<StaticRooms>(`${DATA}/rooms.json`, signal);
const locations = (signal?: AbortSignal) => cachedJson<StaticLocations>(`${DATA}/locations.json`, signal);
const day = async (date: string, signal?: AbortSignal) => {
  try { return await cachedJson<StaticDay>(`${DATA}/days/${date}.json`, signal); }
  catch (error) { if (error instanceof DOMException) throw error; throw new ApiError(503, "static_data_unavailable", "Timetable data is unavailable for this date."); }
};
const canonical = (value: string) => value.trim().toUpperCase();

export async function searchRooms(query: string, limit = 8, signal?: AbortSignal): Promise<RoomSearchResponse> {
  const needle = canonical(query);
  const matches = (await rooms(signal)).rooms.filter((room) => room.id.includes(needle)).sort((a, b) => {
    const rank = (v: string) => v === needle ? 0 : v.startsWith(needle) ? 1 : 2;
    return rank(a.id) - rank(b.id) || a.id.length - b.id.length || a.id.localeCompare(b.id);
  }).slice(0, limit).map(({ id, name }) => ({ id, name }));
  return { rooms: matches, count: matches.length };
}

export async function getLocations(signal?: AbortSignal) {
  const value = await locations(signal);
  return { locations: value.locations.map(({ rooms: _rooms, ...item }) => item) };
}

export async function getRoomSchedule(room: string, date: string, signal?: AbortSignal): Promise<RoomScheduleResponse> {
  const id = canonical(room), [catalog, value] = await Promise.all([rooms(signal), day(date, signal)]);
  if (!catalog.rooms.some((item) => item.id === id)) throw new ApiError(404, "unknown_room", "Room was not found.");
  const roomDay = value.rooms[id];
  return { room: id, date, calendar: value.calendar,
    status: (value.status === "ok" ? roomDay?.status ?? "ok" : value.status) as RoomScheduleResponse["status"],
    reason: value.status === "ok" ? roomDay?.reason ?? "" : value.reason,
    meetings: roomDay?.schedule ?? [] };
}

export async function getRoomAvailability(room: string, query: { date: string; time: string; duration: number }, signal?: AbortSignal): Promise<RoomAvailabilityResponse> {
  const id = canonical(room), [catalog, value] = await Promise.all([rooms(signal), day(query.date, signal)]);
  if (!catalog.rooms.some((item) => item.id === id)) throw new ApiError(404, "unknown_room", "Room was not found.");
  return evaluateRoom(id, value, query.time, query.duration);
}

export async function findFreeRooms(query: { date: string; time: string; duration: number; limit?: number; includeUncertain?: boolean }, signal?: AbortSignal): Promise<FreeRoomsResponse> {
  const [catalog, value] = await Promise.all([rooms(signal), day(query.date, signal)]);
  const results = catalog.rooms.map((item) => locationItem(item.id, value, query.time, query.duration));
  const free = results.filter((item) => item.status === "free").sort((a, b) => (b.free_duration_minutes ?? Infinity) - (a.free_duration_minutes ?? Infinity) || a.room.localeCompare(b.room));
  const uncertain = results.filter((item) => item.status === "uncertain");
  const start = query.time, end = evaluateRoom(catalog.rooms[0].id, value, query.time, query.duration).requested_end;
  return { date: query.date, requested_start: start, requested_end: end, duration_minutes: query.duration,
    status: value.status as FreeRoomsResponse["status"], reason: value.reason, calendar: value.calendar,
    rooms: free.slice(0, query.limit ?? 1000).map(({ room, free_until, free_duration_minutes }) => ({ room, free_until, free_duration_minutes })),
    uncertain_rooms: query.includeUncertain === false ? [] : uncertain.slice(0, query.limit ?? 1000).map(({ room, reason_codes, reasons }) => ({ room, reason_codes, reasons })) };
}

export async function getLocationRooms(locationId: string, query: { date: string; time: string; duration?: number }, signal?: AbortSignal): Promise<LocationRoomsResponse> {
  const [allLocations, value] = await Promise.all([locations(signal), day(query.date, signal)]);
  const location = allLocations.locations.find((item) => item.id === locationId);
  if (!location) throw new ApiError(404, "unknown_location", "Location was not found.");
  const duration = query.duration ?? 1;
  return { location: (({ rooms: _rooms, ...item }) => item)(location), date: query.date, requested_time: query.time, duration_minutes: duration,
    status: value.status as LocationRoomsResponse["status"], reason: value.reason, calendar: value.calendar,
    rooms: value.status === "ok" ? location.rooms.map((room) => locationItem(room, value, query.time, duration)) : [] };
}
