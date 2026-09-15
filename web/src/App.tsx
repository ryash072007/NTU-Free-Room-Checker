import { Link, NavLink, Route, Routes } from "react-router-dom";
import { FreeRoomsPage } from "./pages/FreeRoomsPage";
import { RoomPage } from "./pages/RoomPage";
import { RoomSearchPage } from "./pages/RoomSearchPage";
import { LocationsPage } from "./pages/LocationsPage";

export default function App() {
  return (
    <div className="app-shell">
      <header className="site-header">
        <Link className="brand" to="/" aria-label="NTU Free Room Checker home">
          <span className="brand-mark" aria-hidden="true">N</span>
          <span><strong>Free Room</strong><small>Unofficial NTU utility</small></span>
        </Link>
        <nav aria-label="Primary navigation">
          <NavLink to="/" end>Find a room</NavLink>
          <NavLink to="/schedule">Room schedule</NavLink>
          <NavLink to="/locations">Browse rooms</NavLink>
        </nav>
      </header>
      <Routes>
        <Route path="/" element={<FreeRoomsPage />} />
        <Route path="/schedule" element={<RoomSearchPage />} />
        <Route path="/rooms/:room" element={<RoomPage />} />
        <Route path="/locations" element={<LocationsPage />} />
        <Route path="*" element={<main className="page narrow-page"><h1>Page not found</h1><p className="intro">That page does not exist.</p><Link className="primary-button inline-button" to="/">Find a free room</Link></main>} />
      </Routes>
      <footer>Unofficial student utility · Always check room signage.</footer>
    </div>
  );
}
