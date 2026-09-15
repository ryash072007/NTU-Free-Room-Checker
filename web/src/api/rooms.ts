import { apiGet } from "./client";
import type {
  FreeRoomsResponse,
  RoomAvailabilityResponse,
  RoomScheduleResponse,
  RoomSearchResponse,
} from "./types";

export interface AvailabilityQuery {
  date: string;
  time: string;
  duration: number;
}

export function searchRooms(query: string, limit = 8, signal?: AbortSignal) {
  return apiGet<RoomSearchResponse>("/rooms", { q: query, limit }, signal);
}

export function findFreeRooms(
  query: AvailabilityQuery & { limit?: number; includeUncertain?: boolean },
  signal?: AbortSignal,
) {
  return apiGet<FreeRoomsResponse>("/rooms/free", {
    date: query.date,
    time: query.time,
    duration: query.duration,
    limit: query.limit ?? 100,
    include_uncertain: query.includeUncertain ?? true,
  }, signal);
}

export function getRoomSchedule(room: string, date: string, signal?: AbortSignal) {
  return apiGet<RoomScheduleResponse>(
    `/rooms/${encodeURIComponent(room)}/schedule`, { date }, signal,
  );
}

export function getRoomAvailability(
  room: string,
  query: AvailabilityQuery,
  signal?: AbortSignal,
) {
  return apiGet<RoomAvailabilityResponse>(
    `/rooms/${encodeURIComponent(room)}/availability`, {
      date: query.date, time: query.time, duration: query.duration,
    }, signal,
  );
}
