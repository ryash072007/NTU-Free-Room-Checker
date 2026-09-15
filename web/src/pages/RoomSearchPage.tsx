import { useNavigate } from "react-router-dom";
import { RoomSearch } from "../components/RoomSearch";

export function RoomSearchPage() {
  const navigate = useNavigate();
  return (
    <main className="page narrow-page">
      <div className="eyebrow">Room timetable</div>
      <h1>Check a room schedule</h1>
      <p className="intro">Search by room name to see today’s classes, free gaps, and calendar exceptions.</p>
      <RoomSearch autoFocus onSelect={(room) => navigate(`/rooms/${encodeURIComponent(room)}`)} />
      <p className="helper-text">Searches normalized physical rooms only.</p>
    </main>
  );
}
