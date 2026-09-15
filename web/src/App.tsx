import { Link, Route, Routes } from "react-router-dom";

function Placeholder({ title }: { title: string }) {
  return <main className="page"><h1>{title}</h1></main>;
}

export default function App() {
  return (
    <div className="app-shell">
      <header className="site-header">
        <Link className="brand" to="/" aria-label="NTU Free Room Checker home">
          <span className="brand-mark" aria-hidden="true">N</span>
          <span><strong>Free Room</strong><small>Unofficial NTU utility</small></span>
        </Link>
        <nav aria-label="Primary navigation">
          <Link to="/">Find a room</Link>
          <Link to="/schedule">Room schedule</Link>
        </nav>
      </header>
      <Routes>
        <Route path="/" element={<Placeholder title="Find a free room" />} />
        <Route path="/schedule" element={<Placeholder title="Check room schedule" />} />
        <Route path="/rooms/:room" element={<Placeholder title="Room schedule" />} />
      </Routes>
      <footer>Unofficial student utility · Always check room signage.</footer>
    </div>
  );
}
