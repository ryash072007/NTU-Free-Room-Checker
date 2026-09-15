# Production Deployment & Packaging Guide

This guide documents the single-service production architecture, local production workflows, container packaging, and environment configuration for the **NTU Free Room Checker**.

---

## 1. Production Architecture

In production, the NTU Free Room Checker runs as a **single unified web service**:

```text
               Browser / HTTP Client
                         │
                         ▼
                   FastAPI Server
           (Single Origin: Port 8000)
    ┌────────────────────┼────────────────────┐
    │                    │                    │
    ▼                    ▼                    ▼
/api/v1/...        /assets/...           / & SPA routes
REST Endpoints     Hashed Static Files   Client Routes
(JSON only)        (Long-Lived Cache)    (/schedule, /rooms/...)
```

### Key Characteristics
- **Single Origin**: Frontend and API are hosted under the same origin and port, removing CORS complexity in production.
- **Direct Asset Serving**: FastAPI directly serves built Vite assets from `web/dist`.
- **Deliberate SPA Fallback**:
  - Direct hits and refreshes on React routes (e.g. `/`, `/schedule`, `/rooms/LHN-TR+15`) return `index.html` with `Cache-Control: no-cache`.
  - Static asset files under `/assets/` are served with aggressive cache headers (`Cache-Control: public, max-age=31536000, immutable`).
  - Any non-existent route beginning with `/api/` (or matching `/api`) is strictly returned as an HTTP 404 JSON API envelope (`{"error": {"code": "not_found", "message": "..."}}`), and is **never** replaced with HTML.
- **FastAPI Documentation**: Interactive documentation remains available at `/docs` (Swagger UI) and `/openapi.json`.

---

## 2. Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NTU_ROOM_CHECKER_DB` | `data/ntu_schedule.db` | Path to the SQLite timetable database containing normalized schedule tables. |
| `NTU_ROOM_CHECKER_STATIC_DIR` | Auto-detected (`web/dist`) | Directory containing built frontend static files. Set to `"none"` or empty to run in API-only mode. |
| `NTU_ROOM_CHECKER_CORS_ORIGINS` | `""` | Comma-separated allowed origins for cross-origin setups (optional; not needed for single-origin production). |

---

## 3. Local Production Workflow (Without Vite)

To build and run the unified single-service application locally:

### Step 1: Build the React Frontend
```powershell
cd web
npm ci
npm run build
cd ..
```
This compiles TypeScript and bundles the client app into `web/dist/`.

### Step 2: Start the Unified FastAPI Server
```powershell
$env:NTU_ROOM_CHECKER_DB = "data/ntu_schedule.db"
python -m ntu_room_checker serve --host 127.0.0.1 --port 8000
```
When `web/dist` exists, FastAPI automatically serves the frontend.

### Step 3: Verify the Production App
Open your browser to:
- `http://127.0.0.1:8000/` — Free room finder UI
- `http://127.0.0.1:8000/schedule` — Room timetable search
- `http://127.0.0.1:8000/rooms/LHN-TR%2B15` — Direct room schedule URL
- `http://127.0.0.1:8000/docs` — Swagger API documentation
- `http://127.0.0.1:8000/api/v1/health` — Health check endpoint

---

## 4. Container Packaging (Docker)

The application includes a multi-stage `Dockerfile`:
- **Stage 1 (`frontend-builder`)**: Uses `node:22-slim` to install dependencies via `npm ci` and bundle production assets with Vite.
- **Stage 2 (`runtime`)**: Uses `python:3.11-slim` to install the backend application, copies `web/dist` from Stage 1, and runs without Node.js or `node_modules`.

### Step 1: Build the Docker Image
```powershell
docker build -t ntu-free-room-checker .
```

### Step 2: Run with SQLite Database Volume Mount
The database (`data/ntu_schedule.db`, ~273 MB) is runtime data and is intentionally excluded from Git and the Docker image. Mount it as a read-only volume:

#### Windows PowerShell:
```powershell
docker run --rm `
  -p 8000:8000 `
  -e NTU_ROOM_CHECKER_DB=/data/ntu_schedule.db `
  -v "${PWD}\data:/data:ro" `
  ntu-free-room-checker
```

#### Linux / macOS:
```bash
docker run --rm \
  -p 8000:8000 \
  -e NTU_ROOM_CHECKER_DB=/data/ntu_schedule.db \
  -v "$(pwd)/data:/data:ro" \
  ntu-free-room-checker
```

---

## 5. Health Check

The service includes a lightweight health check endpoint at:

```http
GET /api/v1/health
```

**Expected 200 OK response:**
```json
{
  "status": "ok",
  "database": "available",
  "academic_calendar": "available"
}
```

The container's built-in `HEALTHCHECK` command uses Python's standard library `urllib` to poll this endpoint every 30 seconds.

---

## 6. Development vs. Production Differences

| Feature | Development Mode | Production Mode |
|---|---|---|
| **Frontend Server** | Vite Dev Server (`localhost:5173`) with HMR | Direct static serving from FastAPI (`web/dist`) |
| **API Proxying** | Vite proxy forwards `/api` to `127.0.0.1:8000` | Same-origin native `/api/v1` routes |
| **Origin / Port** | Two ports (`5173` & `8000`) | One port (`8000`) |
| **Asset Caching** | Uncached with module imports | Immutable cache headers on hashed bundles |
| **Node.js Runtime** | Required | Not required at runtime |

---

## 7. Hosting Prerequisites & Considerations

Before deploying to a public cloud provider:
1. **Database Persistence**: The SQLite database (`~273 MB`) must be provisioned via persistent volume, object storage sync, or pre-seeded volume mount. SQLite requires read access.
2. **Memory & CPU**: The Python application is lightweight (~100–200 MB RSS under moderate load) and benefits from fast disk I/O for SQLite index scans.
3. **No External Dependencies**: The service has no dependency on Redis, PostgreSQL, or live third-party network APIs during room checking queries.
