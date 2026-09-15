import type { AvailabilityStatus, CalendarContext } from "../api/types";

const statusCopy: Record<string, { title: string; body: string; tone: string }> = {
  regular_timetable_not_applicable: {
    title: "Regular timetable not applicable",
    body: "The regular class timetable cannot determine physical room availability for this period.",
    tone: "muted",
  },
  regular_timetable_not_authoritative: {
    title: "Room availability is uncertain",
    body: "The regular timetable is not authoritative for room occupancy on this date.",
    tone: "warning",
  },
  regular_timetable_unavailable: {
    title: "Regular timetable unavailable",
    body: "This date is outside a recognized regular timetable period.",
    tone: "muted",
  },
  normalized_timetable_unavailable: {
    title: "Timetable data unavailable",
    body: "Normalized room data is not available for this academic term.",
    tone: "warning",
  },
};

export function StatusMessage({
  status,
  reason,
  calendar,
}: {
  status: AvailabilityStatus | string;
  reason?: string;
  calendar?: CalendarContext;
}) {
  const copy = statusCopy[status] ?? {
    title: "Availability cannot be confirmed",
    body: "The room timetable contains unresolved information for this period.",
    tone: "warning",
  };
  return (
    <section className={`status-message ${copy.tone}`} role="status">
      <strong>{copy.title}</strong>
      <p>{reason || copy.body}</p>
      {calendar?.is_public_holiday && calendar.holiday && <small>Public holiday: {calendar.holiday}</small>}
    </section>
  );
}

export function friendlyApiError(status?: number) {
  if (status === 404) return "Room not found.";
  if (status === 422) return "Check the selected date, time, and duration.";
  if (status === 503) return "Timetable database is currently unavailable.";
  return "Room data is temporarily unavailable. Please try again.";
}
