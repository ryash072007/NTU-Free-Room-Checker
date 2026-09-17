import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { getRoomAvailability, getRoomSchedule } from "../api/rooms";
import type { Meeting, RoomAvailabilityResponse, RoomScheduleResponse } from "../api/types";
import { CalendarContextLine } from "../components/CalendarContextLine";
import { StatusMessage, friendlyApiError } from "../components/StatusMessage";
import {
  ROOM_TRANSITION_MINUTES,
  clockToMinutes,
  formatDuration,
  shiftIsoDate,
  singaporeDateTime,
} from "../utils/time";

export { ROOM_TRANSITION_MINUTES };

type TimelineItem =
  | { kind: "free"; start: string; end: string }
  | { kind: "meeting"; meeting: Meeting };

function effectiveRange(meeting: Meeting): [string, string] {
  return [
    meeting.effective_start ?? meeting.scheduled_start,
    meeting.effective_end ?? meeting.scheduled_end,
  ];
}

export function buildTimeline(meetings: Meeting[], safeToInferGaps: boolean): TimelineItem[] {
  const sorted = [...meetings].sort(
    (left, right) => clockToMinutes(effectiveRange(left)[0]) - clockToMinutes(effectiveRange(right)[0]),
  );
  if (!safeToInferGaps) return sorted.map((meeting) => ({ kind: "meeting", meeting }));
  const items: TimelineItem[] = [];
  let cursor: number | null = null;
  for (const meeting of sorted) {
    if (meeting.applicability === "not_applicable") continue;
    const [start, end] = effectiveRange(meeting);
    const startMinute = clockToMinutes(start);
    const endMinute = clockToMinutes(end);
    if (cursor !== null && startMinute - cursor > ROOM_TRANSITION_MINUTES) {
      items.push({ kind: "free", start: minuteLabel(cursor), end: start });
    }
    items.push({ kind: "meeting", meeting });
    cursor = Math.max(cursor ?? endMinute, endMinute);
  }
  return items;
}

function minuteLabel(value: number) {
  return `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
}

function AvailabilitySummary({ value, time }: { value: RoomAvailabilityResponse; time: string }) {
  if (value.status === "free") {
    return <div className="availability-summary free"><span className="status-dot" />
      <div><strong>Free at {time}</strong><small>{value.free_until ? `Until ${value.free_until} · ${formatDuration(value.free_duration_minutes)}` : "No later regular class found"}</small></div>
    </div>;
  }
  if (value.status === "occupied") {
    return <div className="availability-summary occupied"><span className="status-dot" />
      <div><strong>Occupied at {time}</strong><small>Regular timetable class in progress</small></div>
    </div>;
  }
  return <div className="availability-summary warning"><span className="status-dot" />
    <div><strong>Availability uncertain</strong><small>{value.reasons[0] || "Regular timetable cannot confirm this room."}</small></div>
  </div>;
}

function MeetingRow({ meeting }: { meeting: Meeting }) {
  const [start, end] = effectiveRange(meeting);
  const adjusted = start !== meeting.scheduled_start || end !== meeting.scheduled_end;
  return (
    <article className={`timeline-row meeting ${meeting.applicability}`}>
      <time>{start}<span>{end}</span></time>
      <div className="timeline-line"><i /></div>
      <div className="meeting-body">
        <div className="meeting-title"><strong>{meeting.course_code}</strong><span>{meeting.class_type} · {meeting.group || "Group not listed"}</span></div>
        <p>{meeting.course_title}</p>
        {adjusted && <div className="policy-note">Ends early by calendar policy · Scheduled {meeting.scheduled_start}–{meeting.scheduled_end}</div>}
        {meeting.applicability === "uncertain" && <div className="policy-note warning">Availability uncertain · {meeting.reasons[0]}</div>}
        <details><summary>Class details</summary><dl><div><dt>Index</dt><dd>{meeting.index_number || "—"}</dd></div><div><dt>Remark</dt><dd>{meeting.remark || "None"}</dd></div></dl></details>
      </div>
    </article>
  );
}

export function RoomPage() {
  const room = useParams().room ?? "";
  const now = useMemo(() => singaporeDateTime(), []);
  const [date, setDate] = useState(now.date);
  const [schedule, setSchedule] = useState<RoomScheduleResponse | null>(null);
  const [availability, setAvailability] = useState<RoomAvailabilityResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError("");
    try {
      const [scheduleResult, availabilityResult] = await Promise.all([
        getRoomSchedule(room, date, signal),
        getRoomAvailability(room, { date, time: now.time, duration: 1 }, signal),
      ]);
      setSchedule(scheduleResult);
      setAvailability(availabilityResult);
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      setSchedule(null);
      setAvailability(null);
      setError(friendlyApiError(caught instanceof ApiError ? caught.status : undefined));
    } finally {
      setLoading(false);
    }
  }, [date, now.time, room]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const safeGaps = schedule?.status === "ok" || schedule?.status === "ok_with_adjustments";
  const timeline = useMemo(
    () => buildTimeline(schedule?.meetings ?? [], Boolean(safeGaps)),
    [schedule, safeGaps],
  );

  return (
    <main className="page room-page">
      <Link className="back-link" to="/schedule">← Search another room</Link>
      <header className="room-header">
        <div><div className="eyebrow">Room schedule</div><h1>{room}</h1>
          {schedule && (schedule.class_types.length > 0 || schedule.capacity !== null) && (
            <p className="room-meta">
              {schedule.class_types.join(" · ")}
              {schedule.class_types.length > 0 && schedule.capacity !== null && " · "}
              {schedule.capacity !== null && `Capacity ${schedule.capacity}`}
              {schedule.bookable_by_student_orgs && " · Bookable by student orgs"}
            </p>
          )}
        </div>
        <button className="secondary-button refresh-button" type="button" onClick={() => void load()} disabled={loading}>↻ Refresh</button>
      </header>
      {availability && <AvailabilitySummary value={availability} time={now.time} />}

      <section className="date-navigation" aria-label="Schedule date">
        <button type="button" aria-label="Previous day" onClick={() => setDate(shiftIsoDate(date, -1))}>←</button>
        <label>Date<input type="date" value={date} onChange={(event) => setDate(event.target.value)} /></label>
        <button type="button" onClick={() => setDate(now.date)}>Today</button>
        <button type="button" aria-label="Next day" onClick={() => setDate(shiftIsoDate(date, 1))}>→</button>
      </section>

      {loading && <div className="schedule-skeleton" aria-label="Loading schedule"><i /><i /><i /></div>}
      {error && <div className="error-message" role="alert"><strong>Couldn’t load this room.</strong><span>{error}</span></div>}
      {!loading && schedule && (
        <section className="schedule-section">
          <div className="schedule-heading"><div><h2>Daily timetable</h2><CalendarContextLine calendar={schedule.calendar} /></div><span>{schedule.meetings.length} {schedule.meetings.length === 1 ? "class" : "classes"}</span></div>
          {schedule.status !== "ok" && schedule.status !== "ok_with_adjustments" && schedule.status !== "uncertain" ? (
            <StatusMessage status={schedule.status} reason={schedule.reason} calendar={schedule.calendar} />
          ) : (
            <>
              {!safeGaps && <div className="gap-warning" role="note">Free gaps are hidden because part of this timetable is uncertain.</div>}
              {timeline.length ? <div className="timeline">
                {timeline.map((item, index) => item.kind === "free" ? (
                  <div className="timeline-row gap" key={`${item.start}-${item.end}-${index}`}><time>{item.start}<span>{item.end}</span></time><div className="timeline-line"><i /></div><div><strong>Free</strong><span>Confirmed gap in the regular timetable</span></div></div>
                ) : <MeetingRow meeting={item.meeting} key={`${item.meeting.course_code}-${item.meeting.index_number}-${index}`} />)}
              </div> : <div className="empty-state"><strong>No scheduled classes are listed.</strong><p>The regular timetable shows no classes for this room on this date.</p></div>}
            </>
          )}
        </section>
      )}
    </main>
  );
}
