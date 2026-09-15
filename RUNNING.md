# How to Run NTU Free Room Checker

This guide provides the exact commands to run the NTU Free Room Checker across different environments:

1. **[Production Mode (Unified Service)](#1-production-mode-unified-service-recommended)** — Single FastAPI process serving the bundled React SPA and REST API on one port.
2. **[Docker Container](#2-docker-container)** — Multi-stage container running Python runtime with a read-only volume-mounted SQLite database.
3. **[Development Mode](#3-development-mode-vite--fastapi)** — Live Vite dev server with Hot Module Replacement (HMR) proxying to FastAPI.
4. **[Running Tests](#4-running-tests)** — Regression testing backend and frontend suites.
5. **[CLI Commands](#5-cli-commands)** — Direct terminal queries for schedules and free rooms.

---

## Prerequisites

- **Python 3.11+** installed
- **Node.js 20+** & **npm** installed (for building or developing the frontend)
- Normalized SQLite database located at `data/ntu_schedule.db` (or custom path)

---

## 1. Production Mode (Unified Service) [Recommended]

In production mode, FastAPI serves the compiled React single-page application and the REST API from the same origin on port `8000`.

### Step 1: Install Python dependencies
```powershell
python -m pip install -e .
```

### Step 2: Build the frontend SPA
```powershell
cd web
npm ci
npm run build
cd ..
```

### Step 3: Start the server
#### Windows (PowerShell):
```powershell
$env:NTU_ROOM_CHECKER_DB = "data/ntu_schedule.db"
python -m ntu_room_checker serve --host 127.0.0.1 --port 8000
```

#### Linux / macOS (Bash):
```bash
export NTU_ROOM_CHECKER_DB="data/ntu_schedule.db"
python -m ntu_room_checker serve --host 127.0.0.1 --port 8000
```

### Step 4: Open in browser
- Web Application: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Room Timetables: [http://127.0.0.1:8000/schedule](http://127.0.0.1:8000/schedule)
- Direct Room Route: [http://127.0.0.1:8000/rooms/LHN-TR%2B15](http://127.0.0.1:8000/rooms/LHN-TR%2B15)
- Interactive API Docs (Swagger): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health Check: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

---

## 2. Docker Container

The container packages the built frontend and Python runtime without requiring Node.js at runtime. The SQLite database is mounted as a read-only volume.

### Step 1: Build the Docker image
```powershell
docker build -t ntu-free-room-checker .
```

### Step 2: Run container with read-only database mount
#### Windows (PowerShell):
```powershell
docker run --rm -p 8000:8000 `
  -e NTU_ROOM_CHECKER_DB=/data/ntu_schedule.db `
  -v "${PWD}\data:/data:ro" `
  ntu-free-room-checker
```

#### Linux / macOS (Bash):
```bash
docker run --rm -p 8000:8000 \
  -e NTU_ROOM_CHECKER_DB=/data/ntu_schedule.db \
  -v "$(pwd)/data:/data:ro" \
  ntu-free-room-checker
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

---

## 3. Development Mode (Vite + FastAPI)

For active frontend or backend feature development:

### Terminal 1 — Start the FastAPI Backend:
```powershell
$env:NTU_ROOM_CHECKER_DB = "data/ntu_schedule.db"
python -m ntu_room_checker serve --host 127.0.0.1 --port 8000
```

### Terminal 2 — Start the Vite Dev Server:
```powershell
cd web
npm install
npm run dev
```

Open [http://localhost:5173/](http://localhost:5173/). Vite will automatically proxy API requests (`/api/*`) to `http://127.0.0.1:8000`.

---

## 4. Running Tests

### Backend Tests (Pytest — 222 tests):
```powershell
python -m pytest
```

### Frontend Tests (Vitest — 21 tests):
```powershell
cd web
npm test
```

---

## 5. CLI Commands

You can also query room availability and timetables directly from the terminal:

### Find free rooms for a date and time:
```powershell
python -m ntu_room_checker free-rooms --date 2026-09-15 --time 1425 --duration 60
```

### Check a specific room's schedule:
```powershell
python -m ntu_room_checker room-schedule "LHN-TR+15" --date 2026-09-15
```

### Check a room's availability:
```powershell
python -m ntu_room_checker room-availability "LHN-TR+15" --date 2026-09-15 --time 1425 --duration 60
```

### Resolve an academic calendar date:
```powershell
python -m ntu_room_checker calendar-date 2026-09-15
```
