import type { CalendarContext } from "../api/types";

function periodLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function CalendarContextLine({ calendar }: { calendar: CalendarContext }) {
  const pieces = [calendar.weekday];
  if (calendar.teaching_week) pieces.push(`Teaching Week ${calendar.teaching_week}`);
  else pieces.push(periodLabel(calendar.period_type));
  if (calendar.is_public_holiday && calendar.holiday) pieces.push(calendar.holiday);
  return <p className="context-line">{pieces.join(" · ")}</p>;
}
