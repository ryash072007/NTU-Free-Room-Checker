# Web Frontend

The NTU Free Room Checker web application provides a responsive, mobile-first interface for students and staff to quickly identify physically available teaching facilities and inspect room schedules across the NTU campus.

It is built as a client-side single-page application using React 19, TypeScript, Vite, and React Router. It communicates with the versioned FastAPI backend (`/api/v1`).

---

## Quickstart / Running Locally

### 1. Start the Backend API

From the repository root with Python 3.11+:

```powershell
$env:NTU_ROOM_CHECKER_DB = "data/ntu_schedule.db"
python -m ntu_room_checker serve --host 127.0.0.1 --port 8000
```

The API will be available at `http://127.0.0.1:8000`, with interactive OpenAPI documentation at `http://127.0.0.1:8000/docs`.

### 2. Start the Frontend Development Server

In a separate terminal:

```powershell
cd web
npm install
npm run dev
```

Vite starts a local development server at `http://localhost:5173/`. By default, Vite proxies `/api` requests to `http://127.0.0.1:8000`.

---

## Configuration & Environment Variables

The frontend reads configuration via Vite environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `/api/v1` | Base URL prefix for all API requests. Can be configured to an absolute URL (e.g. `http://127.0.0.1:8000/api/v1`) or a relative proxy path (`/api/v1`). |

### Vite Proxy Behavior

In development mode (`npm run dev`), `web/vite.config.ts` configures a local proxy:

```typescript
server: {
  proxy: {
    "/api": "http://127.0.0.1:8000",
  },
}
```

This forwards any client request starting with `/api` directly to the local backend server, eliminating Cross-Origin Resource Sharing (CORS) complications during local development.

---

## Application Architecture & Routes

The application features two primary user flows:

### 1. Find a Free Room (`/`)
- **Route**: `/` (`FreeRoomsPage`)
- **UX flow**: Submit-driven query to find available rooms across campus.
- **Controls**:
  - **"Now" button**: Automatically populates the current date and rounds the start time up to the next 5-minute Singapore-time boundary.
  - **Custom date/time picker**: Allows querying arbitrary dates and times.
  - **Duration presets**: Quick selection of 30 min, 1h (default), 2h, or 3h, plus custom minute input.
  - **Sorting**: Sort confident results by longest availability or alphabetically by room name.
- **Result presentation**:
  - Displays each confident room with free-until time and total duration available.
  - Links directly to each room's detailed schedule page with URL-encoded parameters.
  - Keeps uncertain rooms strictly segregated in an expandable accordion with explicit reason descriptions.

### 2. Check Room Schedule (`/schedule` and `/rooms/:room`)
- **Routes**:
  - `/schedule` (`RoomSearchPage`): Search landing page with an accessible room search combobox.
  - `/rooms/:room` (`RoomPage`): Detailed room schedule and availability view.
- **UX flow**:
  - **Debounced Autocomplete**: Server-side prefix and exact search (`/api/v1/rooms?q=...`) debounced at 250ms.
  - **Keyboard Accessible**: Arrow up/down selection, Enter to navigate, Escape to dismiss.
  - **Plus-Sign Safety**: Room identifiers containing `+` (e.g. `LHN-TR+15`) are safely URL-encoded (`%2B`) in route parameters and API calls.
  - **Current Availability Summary**: Indicates whether the room is currently Free, Occupied, or Uncertain.
  - **Date Navigation**: Previous/Next day buttons, date picker, and "Today" button.
  - **Meeting Details**: Shows class type, group, course name, and scheduled vs effective timings.
  - **Safe Free Gaps**: Derives and highlights gaps between scheduled classes only when the timetable is authoritative.

---

## Domain Semantics & Uncertainty Handling

The web client rigorously adheres to the backend's conservative availability rules:

### Singapore Timezone (`Asia/Singapore`)
All date, time, and "Now" calculations strictly use Singapore local time (`Asia/Singapore`, UTC+8) regardless of the user's browser timezone.

### Confirmed vs. Non-Authoritative States
The client never equates *"no regular class scheduled"* with *"the physical room is definitely free"*:
- **CONFIRMED FREE (`is_free = true`)**: Rendered in green with explicit free-until and duration metrics.
- **OCCUPIED (`is_free = false`)**: Rendered with occupied indicators and meeting details.
- **UNCERTAIN (`is_free = null`)**: Rendered with amber warning badges and domain reason explanations. Uncertain rooms are never mixed into confident free room results.
- **NON-APPLICABLE PERIODS (e.g. Recess Week)**: Displays informative notices explaining why the regular timetable cannot establish physical availability; no free gaps are invented.
- **NON-AUTHORITATIVE PERIODS (e.g. Revision & Exam Weeks)**: Timetable entries are suppressed or marked non-authoritative; the user is advised that rooms may be reserved for exams or study.
- **CALENDAR EXCEPTIONS (e.g. Students' Union Day, Eve Dismissals)**: Explains adjusted ending times or uncertain intervals resulting from population scope ambiguity.
- **ROOM TRANSITIONS (`ROOM_TRANSITION_MINUTES = 10`)**: Gaps of 10 minutes or less between consecutive classes are treated as student changeover intervals and never rendered as "Free" rows; genuine gaps (> 10 minutes) render as confirmed free gaps.

---

## Testing & Quality Assurance

### Frontend Test Suite
The frontend uses Vitest and React Testing Library:

```powershell
cd web
npm test
```

The test suite covers:
- `client.test.ts`: Plus-sign URL encoding, structured API error envelope handling.
- `time.test.ts`: Singapore time calculation, boundary rounding, duration formatting, date shifts.
- `RoomSearch.test.tsx`: Search debouncing, keyboard navigation, safe plus-sign handling.
- `FreeRoomsPage.test.tsx`: Default state, Singapore "Now" rounding, duration submission, confident vs uncertain segregation, recess week handling, error states.
- `RoomPage.test.tsx`: Encoded room loading, live availability, safe free-gap derivation, exception-adjusted timings, exam period warnings, date navigation, 404 unknown room handling.

### Backend Test Suite
The FastAPI and domain logic backend test suite (219 tests) can be run from the repository root:

```powershell
python -m pytest
```

### Production Build
To create an optimized production build:

```powershell
cd web
npm run build
```

Production artifacts are compiled with TypeScript project references (`tsc -b`) and bundled via Vite into `web/dist/`.

---

## Current MVP Limitations

- **Timetable-Based Only**: Availability is derived exclusively from the published academic class schedule and calendar policy; ad-hoc bookings, club activities, or physical card-access lockouts are not captured.
- **Single Campus Scope**: AY2026-27 undergraduate and postgraduate semester calendars are modeled.
- **No Client State Persistence**: Searches and preferences are session-bound without persistent user accounts or saved favorite rooms.
