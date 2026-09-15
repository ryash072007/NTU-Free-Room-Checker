import { apiGet } from "./client";
import type { CalendarContext } from "./types";

export function getCalendarDate(date: string, signal?: AbortSignal) {
  return apiGet<CalendarContext>(`/calendar/${encodeURIComponent(date)}`, {}, signal);
}
