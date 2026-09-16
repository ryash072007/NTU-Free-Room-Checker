import type { CalendarContext } from "./types";
import { cachedJson } from "../data/cache";
import type { StaticDay } from "../data/types";

export async function getCalendarDate(date: string, signal?: AbortSignal): Promise<CalendarContext> {
  return (await cachedJson<StaticDay>(`/data/days/${date}.json`, signal)).calendar;
}
