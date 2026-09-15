export interface LocalDateTime {
  date: string;
  time: string;
}

const SINGAPORE_ZONE = "Asia/Singapore";

export function singaporeDateTime(now = new Date()): LocalDateTime {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: SINGAPORE_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(now);
  const value = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? "";
  return {
    date: `${value("year")}-${value("month")}-${value("day")}`,
    time: `${value("hour")}:${value("minute")}`,
  };
}

export function roundedSingaporeDateTime(now = new Date(), increment = 5): LocalDateTime {
  const current = singaporeDateTime(now);
  const [hour, minute] = current.time.split(":").map(Number);
  const rounded = Math.ceil((hour * 60 + minute) / increment) * increment;
  if (rounded < 24 * 60) {
    return { ...current, time: minutesToClock(rounded) };
  }
  const tomorrow = new Date(`${current.date}T00:00:00+08:00`);
  tomorrow.setUTCDate(tomorrow.getUTCDate() + 1);
  return { date: singaporeDateTime(tomorrow).date, time: "00:00" };
}

export function clockToMinutes(value: string): number {
  const [hours, minutes] = value.split(":").map(Number);
  return hours * 60 + minutes;
}

export function minutesToClock(value: number): string {
  return `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
}

export function formatDuration(minutes: number | null): string {
  if (minutes === null) return "";
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  if (!hours) return `${remainder} min`;
  if (!remainder) return `${hours}h`;
  return `${hours}h ${remainder}m`;
}

export function shiftIsoDate(date: string, days: number): string {
  const instant = new Date(`${date}T12:00:00+08:00`);
  instant.setUTCDate(instant.getUTCDate() + days);
  return singaporeDateTime(instant).date;
}
