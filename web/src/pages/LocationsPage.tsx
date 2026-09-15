import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { getLocationRooms, getLocations } from "../api/locations";
import type { LocationItem, LocationRoomItem, LocationRoomsResponse } from "../api/types";
import { CalendarContextLine } from "../components/CalendarContextLine";
import { StatusMessage } from "../components/StatusMessage";
import { formatDuration, roundedSingaporeDateTime, singaporeDateTime } from "../utils/time";

function message(error: unknown) {
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
  return <li>
    <Link to={`/rooms/${encodeURIComponent(room.room)}`}>
      <strong>{room.room}</strong>
      <span className={`status-label ${room.status}`}>{room.status === "occupied" ? "In use" : room.status}</span>
      <small>{detail}</small><span aria-hidden="true">›</span>
    </Link>
  </li>;
}

export function LocationsPage() {
  const initial = useRef(singaporeDateTime()).current;
  const [locations, setLocations] = useState<LocationItem[]>([]);
  const [locationId, setLocationId] = useState("");
  const [date, setDate] = useState(initial.date);
  const [time, setTime] = useState(initial.time);
  const [result, setResult] = useState<LocationRoomsResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [sort, setSort] = useState<"best" | "name">("best");

  useEffect(() => {
    const controller = new AbortController();
    getLocations(controller.signal).then(({ locations: items }) => {
      setLocations(items);
      setLocationId((current) => current || items[0]?.id || "");
    }).catch((caught) => { if (!(caught instanceof DOMException)) setError(message(caught)); });
    return () => controller.abort();
  }, []);

  const rooms = useMemo(() => {
    const values = [...(result?.rooms ?? [])];
    return sort === "name" ? values.sort((a, b) => a.room.localeCompare(b.room)) : values;
  }, [result, sort]);
  const groups = [
    ["free", "Free"], ["occupied", "In use"], ["uncertain", "Uncertain"],
  ] as const;

  const useNow = () => {
    const current = roundedSingaporeDateTime();
    setDate(current.date); setTime(current.time);
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault(); if (!locationId) return;
    setLoading(true); setError("");
    try { setResult(await getLocationRooms(locationId, { date, time })); }
    catch (caught) { setResult(null); setError(message(caught)); }
    finally { setLoading(false); }
  };

  return <main className="page locations-page">
    <section className="finder-heading"><div className="eyebrow">Campus spaces</div><h1>Browse rooms</h1>
      <p className="intro">See every mapped room around a campus location at a glance.</p></section>
    <form className="location-controls" onSubmit={submit}>
      <label>Location<select aria-label="Location" value={locationId} onChange={(event) => setLocationId(event.target.value)} required>
        {locations.map((location) => <option key={location.id} value={location.id}>{location.name} · {location.room_count} rooms</option>)}
      </select></label>
      <label>Date<input aria-label="Date" type="date" value={date} onChange={(event) => setDate(event.target.value)} /></label>
      <label>Time<input aria-label="Time" type="time" value={time} onChange={(event) => setTime(event.target.value)} /></label>
      <button type="button" className="secondary-button" onClick={useNow}>Now</button>
      <button type="submit" className="primary-button" disabled={loading || !locationId}>{loading ? "Refreshing…" : "Show rooms"}</button>
    </form>
    {error && <div role="alert" className="error-message">{error}</div>}
    {result && <section className="location-results" aria-live="polite">
      <div className="location-title"><div><h2>{result.location.name}</h2>{result.location.official_name && <p>{result.location.official_name}</p>}<CalendarContextLine calendar={result.calendar} /></div>
        {result.rooms.length > 1 && <label className="sort-control">Sort<select value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}><option value="best">Best availability</option><option value="name">Room name</option></select></label>}</div>
      {result.status !== "ok" ? <StatusMessage status={result.status} reason={result.reason} calendar={result.calendar} /> :
        groups.map(([status, label]) => {
          const matching = rooms.filter((room) => room.status === status);
          return matching.length ? <section className="room-status-group" key={status}><h3>{label} <span>{matching.length}</span></h3><ul>{matching.map((room) => <RoomRow key={room.room} room={room} />)}</ul></section> : null;
        })}
    </section>}
  </main>;
}
