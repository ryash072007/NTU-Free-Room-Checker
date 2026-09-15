import { type FormEvent, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { findFreeRooms } from "../api/rooms";
import type { FreeRoomItem, FreeRoomsResponse } from "../api/types";
import { CalendarContextLine } from "../components/CalendarContextLine";
import { StatusMessage, friendlyApiError } from "../components/StatusMessage";
import { formatDuration, roundedSingaporeDateTime, singaporeDateTime } from "../utils/time";

const DURATION_PRESETS = [30, 60, 120, 180];

function sortRooms(rooms: FreeRoomItem[], sort: "longest" | "name") {
  return [...rooms].sort((left, right) => {
    if (sort === "name") return left.room.localeCompare(right.room);
    const leftDuration = left.free_duration_minutes ?? Number.POSITIVE_INFINITY;
    const rightDuration = right.free_duration_minutes ?? Number.POSITIVE_INFINITY;
    return rightDuration - leftDuration || left.room.localeCompare(right.room);
  });
}

export function FreeRoomsPage() {
  const initial = useRef(singaporeDateTime()).current;
  const [date, setDate] = useState(initial.date);
  const [time, setTime] = useState(initial.time);
  const [duration, setDuration] = useState(60);
  const [customDuration, setCustomDuration] = useState("");
  const [queryMode, setQueryMode] = useState<"now" | "date">("date");
  const [result, setResult] = useState<FreeRoomsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sort, setSort] = useState<"longest" | "name">("longest");

  const rooms = useMemo(() => sortRooms(result?.rooms ?? [], sort), [result, sort]);

  const useNow = () => {
    const current = roundedSingaporeDateTime();
    setDate(current.date);
    setTime(current.time);
    setQueryMode("now");
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      setResult(await findFreeRooms({ date, time, duration, includeUncertain: true, limit: 100 }));
    } catch (caught) {
      setResult(null);
      setError(friendlyApiError(caught instanceof ApiError ? caught.status : undefined));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="page">
      <section className="finder-heading">
        <div className="eyebrow">Campus spaces</div>
        <h1>Find a free room</h1>
        <p className="intro">Only rooms confirmed free by the regular NTU timetable are listed.</p>
      </section>

      <form className="finder-form" onSubmit={submit}>
        <div className="mode-switch" aria-label="Time selection mode">
          <button type="button" className={queryMode === "now" ? "active" : ""} onClick={useNow}>Now</button>
          <button type="button" className={queryMode === "date" ? "active" : ""} onClick={() => setQueryMode("date")}>Choose date</button>
        </div>
        <div className="date-time-grid">
          <label>Date<input type="date" value={date} onChange={(event) => { setDate(event.target.value); setQueryMode("date"); }} required /></label>
          <label>Start time<input type="time" value={time} onChange={(event) => { setTime(event.target.value); setQueryMode("date"); }} required /></label>
        </div>
        {queryMode === "now" && <p className="query-note">Querying from {time} Singapore time (rounded to 5 minutes).</p>}
        <fieldset>
          <legend>How long?</legend>
          <div className="duration-options">
            {DURATION_PRESETS.map((minutes) => (
              <button
                type="button"
                key={minutes}
                className={duration === minutes && !customDuration ? "active" : ""}
                aria-pressed={duration === minutes && !customDuration}
                onClick={() => { setDuration(minutes); setCustomDuration(""); }}
              >{minutes < 60 ? "30 min" : `${minutes / 60}h`}</button>
            ))}
            <label className="custom-duration">
              <span>Custom</span>
              <input
                type="number" min="1" max="1440" inputMode="numeric"
                value={customDuration} placeholder="min" aria-label="Custom duration in minutes"
                onChange={(event) => {
                  setCustomDuration(event.target.value);
                  if (event.target.value) setDuration(Number(event.target.value));
                }}
              />
            </label>
          </div>
        </fieldset>
        <button className="primary-button" type="submit" disabled={loading || duration < 1}>
          {loading ? "Finding rooms…" : "Find rooms"}
        </button>
      </form>

      {error && <div className="error-message" role="alert"><strong>Couldn’t load rooms.</strong><span>{error}</span></div>}
      {loading && <div className="result-skeleton" aria-label="Loading room results"><i /><i /><i /></div>}
      {!loading && result && (
        <section className="results" aria-live="polite">
          <div className="results-header">
            <div>
              <p className="result-count">{rooms.length} confidently free {rooms.length === 1 ? "room" : "rooms"}</p>
              <CalendarContextLine calendar={result.calendar} />
            </div>
            {rooms.length > 1 && (
              <label className="sort-control">Sort<select value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}><option value="longest">Longest available</option><option value="name">Room name</option></select></label>
            )}
          </div>

          {result.status !== "ok" ? (
            <StatusMessage status={result.status} reason={result.reason} calendar={result.calendar} />
          ) : rooms.length ? (
            <ul className="room-list">
              {rooms.map((room) => (
                <li key={room.room}>
                  <Link to={`/rooms/${encodeURIComponent(room.room)}`}>
                    <div><strong>{room.room}</strong><span className="status-label free">Confirmed free</span></div>
                    <div className="room-free-time">
                      <span>{room.free_until ? `Free until ${room.free_until}` : "Free for the rest of the regular timetable"}</span>
                      {room.free_duration_minutes !== null && <small>{formatDuration(room.free_duration_minutes)} available</small>}
                    </div>
                    <span aria-hidden="true">›</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <div className="empty-state">
              <strong>No rooms are confidently free for this period.</strong>
              {result.uncertain_rooms.length > 0 && <p>{result.uncertain_rooms.length} rooms have uncertain availability.</p>}
            </div>
          )}

          {result.uncertain_rooms.length > 0 && (
            <details className="uncertain-results">
              <summary>{result.uncertain_rooms.length} rooms with uncertain availability</summary>
              <p>These rooms are not included in the confirmed-free list.</p>
              <ul>{result.uncertain_rooms.map((room) => <li key={room.room}><strong>{room.room}</strong><span>Availability uncertain</span><small>{room.reasons[0]}</small></li>)}</ul>
            </details>
          )}
        </section>
      )}
    </main>
  );
}
