import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { findFreeRooms } from "../api/rooms";
import { calendar, freeRooms } from "../test/fixtures";
import { FreeRoomsPage } from "./FreeRoomsPage";

vi.mock("../api/rooms", () => ({ findFreeRooms: vi.fn() }));
const mockedFind = vi.mocked(findFreeRooms);

function renderPage() {
  return render(<MemoryRouter><FreeRoomsPage /></MemoryRouter>);
}

describe("Free room finder", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-09-15T07:43:00Z"));
    mockedFind.mockReset();
  });
  afterEach(() => vi.useRealTimers());

  it("defaults to Singapore today, current time, and 60 minutes without auto-querying", () => {
    renderPage();
    expect(screen.getByLabelText("Date")).toHaveValue("2026-09-15");
    expect(screen.getByLabelText("Start time")).toHaveValue("15:43");
    expect(screen.getByRole("button", { name: "1h" })).toHaveAttribute("aria-pressed", "true");
    expect(mockedFind).not.toHaveBeenCalled();
  });

  it("uses rounded Singapore time for Now and submits a duration preset", async () => {
    mockedFind.mockResolvedValue(freeRooms());
    renderPage();
    await userEvent.click(screen.getByRole("button", { name: "Now" }));
    await userEvent.click(screen.getByRole("button", { name: "2h" }));
    await userEvent.click(screen.getByRole("button", { name: "Find rooms" }));
    await waitFor(() => expect(mockedFind).toHaveBeenCalledWith(expect.objectContaining({
      date: "2026-09-15", time: "15:45", duration: 120, includeUncertain: true,
    })));
  });

  it("renders free-until, duration, and encoded schedule navigation", async () => {
    mockedFind.mockResolvedValue(freeRooms());
    renderPage();
    await userEvent.click(screen.getByRole("button", { name: "Find rooms" }));
    expect(await screen.findByText("Free until 19:00")).toBeInTheDocument();
    expect(screen.getByText("4h 30m available")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /LHN-TR\+15/ })).toHaveAttribute(
      "href", "/rooms/LHN-TR%2B15",
    );
  });

  it("keeps uncertain rooms separate from confident results", async () => {
    mockedFind.mockResolvedValue(freeRooms({
      rooms: [],
      uncertain_rooms: [{
        room: "TR+15", reason_codes: ["population_scope_unknown"],
        reasons: ["Students' Union Day exception affects this period."],
      }],
    }));
    renderPage();
    await userEvent.click(screen.getByRole("button", { name: "Find rooms" }));
    expect(await screen.findByText("No rooms are confidently free for this period.")).toBeInTheDocument();
    expect(screen.getByText("1 rooms with uncertain availability")).toBeInTheDocument();
    expect(screen.queryByText("Confirmed free")).not.toBeInTheDocument();
  });

  it("shows the domain-specific recess state rather than a generic empty result", async () => {
    mockedFind.mockResolvedValue(freeRooms({
      status: "regular_timetable_not_applicable",
      reason: "The regular class timetable does not apply during recess_week.",
      calendar: { ...calendar, period_type: "recess_week", teaching_week: null },
      rooms: [],
    }));
    renderPage();
    await userEvent.click(screen.getByRole("button", { name: "Find rooms" }));
    expect(await screen.findByText("Regular timetable not applicable")).toBeInTheDocument();
    expect(screen.getByText(/recess_week/)).toBeInTheDocument();
  });

  it("maps backend failure to a useful message", async () => {
    mockedFind.mockRejectedValue(new ApiError(503, "database_unavailable", "no db"));
    renderPage();
    fireEvent.submit(screen.getByRole("button", { name: "Find rooms" }).closest("form")!);
    expect(await screen.findByText("Timetable database is currently unavailable.")).toBeInTheDocument();
  });
});
