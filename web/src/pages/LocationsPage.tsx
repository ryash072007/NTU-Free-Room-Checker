import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { getLocationRooms, getLocations } from "../api/locations";
import { findFreeRooms } from "../api/rooms";
import type { AvailabilityStatus, CalendarContext, LocationItem, LocationRoomItem } from "../api/types";
import { CalendarContextLine } from "../components/CalendarContextLine";
import { StatusMessage } from "../components/StatusMessage";
import { formatDuration, roundedSingaporeDateTime, singaporeDateTime } from "../utils/time";

const ANYWHERE_ID = "anywhere";
const DURATIONS = [0, 30, 60, 120, 180] as const;

interface BrowseResult {
  location: LocationItem;
  calendar: CalendarContext;
  status: AvailabilityStatus | "ok";
  reason: string;
  rooms: LocationRoomItem[];
}

function errorMessage(error: unknown) {
  return error instanceof ApiError && error.status === 503
    ? "Timetable database is currently unavailable."
    : "Room availability could not be loaded. Please try again.";
}

function RoomRow({ room }: { room: LocationRoomItem }) {
  const detail = room.status === "free"
    ? room.free_until
      ? `Free for ${formatDuration(room.free_duration_minutes)} · until ${room.free_until}`
      : "No later regular-timetable meeting today"
    : room.status === "occupied"
      ? `Available at ${room.available_from}`
      : room.reasons[0] || "Availability cannot be confirmed";
  return <li><Link to={`/rooms/${encodeURIComponent(room.room)}`}>
    <strong>{room.room}</strong>
    <span className={`status-label ${room.status}`}>{room.status === "occupied" ? "In use" : room.status}</span>
    <small>{detail}</small><span aria-hidden="true">›</span>
  </Link></li>;
}

function bestAvailability(left: LocationRoomItem, right: LocationRoomItem) {
  const rank = (room: LocationRoomItem) => room.status === "free" ? 0 : room.status === "occupied" ? 1 : 2;
  const rankDifference = rank(left) - rank(right);
  if (rankDifference) return rankDifference;
  if (left.status === "free" && right.status === "free") {
    const leftDuration = left.free_duration_minutes ?? Number.POSITIVE_INFINITY;
    const rightDuration = right.free_duration_minutes ?? Number.POSITIVE_INFINITY;
    if (leftDuration !== rightDuration) return rightDuration - leftDuration;
  }
  if (left.status === "occupied" && right.status === "occupied") {
    const availability = (left.available_from ?? "99:99").localeCompare(right.available_from ?? "99:99");
    if (availability) return availability;
  }
  return left.room.localeCompare(right.room);
}

export function LocationsPage() {
  const initial = useRef(singaporeDateTime()).current;
  const [locations, setLocations] = useState<LocationItem[]>([]);
  const [locationId, setLocationId] = useState(ANYWHERE_ID);
  const [date, setDate] = useState(initial.date);
  const [time, setTime] = useState(initial.time);
  const [duration, setDuration] = useState(0);
  const [result, setResult] = useState<BrowseResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [sort, setSort] = useState<"best" | "name">("best");
  const [filter, setFilter] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    getLocations(controller.signal).then(({ locations: items }) => setLocations(items))
      .catch((caught) => { if (!(caught instanceof DOMException)) setError(errorMessage(caught)); });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError("");
    const load = async () => {
      if (locationId === ANYWHERE_ID) {
        const response = await findFreeRooms({ date, time, duration: duration || 1, includeUncertain: true, limit: 1000 }, controller.signal);
        setResult({
          location: { id: ANYWHERE_ID, name: "Anywhere on campus", official_name: null, short_name: "Anywhere", aliases: [], room_count: response.rooms.length + response.uncertain_rooms.length },
          calendar: response.calendar, status: response.status, reason: response.reason,
          rooms: [
            ...response.rooms.map((room) => ({ ...room, status: "free" as const, is_free: true, available_from: null, reason_codes: [], reasons: [] })),
            ...response.uncertain_rooms.map((room) => ({ ...room, status: "uncertain" as const, is_free: null, free_until: null, free_duration_minutes: null, available_from: null })),
          ],
        });
      } else {
        setResult(await getLocationRooms(locationId, { date, time, duration: duration || 1 }, controller.signal));
      }
    };
    load().catch((caught) => {
      if (!(caught instanceof DOMException)) { setResult(null); setError(errorMessage(caught)); }
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [locationId, date, time, duration]);

  const visibleRooms = useMemo(() => {
    const needle = filter.trim().toUpperCase();
    let values = (result?.rooms ?? []).filter((room) => !needle || room.room.toUpperCase().includes(needle));
    if (locationId !== ANYWHERE_ID && duration > 0) {
      values = values.filter((room) => room.status !== "free" || room.free_duration_minutes === null || room.free_duration_minutes >= duration);
    }
    return [...values].sort(sort === "name" ? (a, b) => a.room.localeCompare(b.room) : bestAvailability);
  }, [result, filter, sort, locationId, duration]);
  const groups = [["free", "Free"], ["occupied", "In use"], ["uncertain", "Uncertain"]] as const;
  const useNow = () => { const current = roundedSingaporeDateTime(); setDate(current.date); setTime(current.time); };

  return <main className="page locations-page">
    <section className="finder-heading"><div className="eyebrow">Campus spaces</div><h1>Browse rooms</h1>
      <p className="intro">Choose an area and see usable rooms now, then tap one for its full schedule.</p></section>
    <section className="location-controls" aria-label="Browse controls">
      <label>Location<select aria-label="Location" value={locationId} onChange={(event) => setLocationId(event.target.value)}>
        <option value={ANYWHERE_ID}>Anywhere on campus</option>
        {locations.map((location) => <option key={location.id} value={location.id}>{location.name} · {location.room_count} rooms</option>)}
      </select></label>
      <label>Date<input aria-label="Date" type="date" value={date} onChange={(event) => setDate(event.target.value)} /></label>
      <label>Time<input aria-label="Time" type="time" value={time} onChange={(event) => setTime(event.target.value)} /></label>
      <button type="button" className="secondary-button" onClick={useNow}>Now</button>
      <label>Need it for<select aria-label="Need it for" value={duration} onChange={(event) => setDuration(Number(event.target.value))}>
        {DURATIONS.map((minutes) => <option key={minutes} value={minutes}>{minutes === 0 ? "Any" : minutes < 60 ? `${minutes}m` : `${minutes / 60}h`}</option>)}
      </select></label>
    </section>
    {error && <div role="alert" className="error-message">{error}</div>}
    {loading && <div className="result-skeleton" aria-label="Loading room results"><i /><i /><i /></div>}
    {!loading && result && <section className="location-results" aria-live="polite">
      <div className="location-title"><div><h2>{result.location.name}</h2>{result.location.official_name && <p>{result.location.official_name}</p>}<CalendarContextLine calendar={result.calendar} /></div>
        <label className="sort-control">Sort<select value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}><option value="best">Best availability</option><option value="name">Room name</option></select></label></div>
      {result.status !== "ok" ? <StatusMessage status={result.status} reason={result.reason} calendar={result.calendar} /> : <>
        <label className="room-filter">Filter rooms<input type="search" value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="e.g. LHN-TR+17" /></label>
        {groups.map(([status, label]) => { const matching = visibleRooms.filter((room) => room.status === status); return matching.length ? <section className="room-status-group" key={status}><h3>{label} <span>{matching.length}</span></h3><ul>{matching.map((room) => <RoomRow key={room.room} room={room} />)}</ul></section> : null; })}
        {!visibleRooms.length && <div className="empty-state">No rooms match these filters.</div>}
      </>}
    </section>}
  </main>;
}
