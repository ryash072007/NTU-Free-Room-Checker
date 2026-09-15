import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getLocationRooms, getLocations } from "../api/locations";
import { calendar } from "../test/fixtures";
import { LocationsPage } from "./LocationsPage";

vi.mock("../api/locations", () => ({ getLocations: vi.fn(), getLocationRooms: vi.fn() }));
const mockedLocations = vi.mocked(getLocations);
const mockedRooms = vi.mocked(getLocationRooms);

const arc = { id: "the-arc", name: "The Arc", official_name: "Learning Hub North", short_name: "Arc", aliases: ["LHN"], room_count: 3 };
const response = {
  location: arc, date: "2026-09-15", requested_time: "15:45", duration_minutes: 1,
  status: "ok" as const, reason: "", calendar,
  rooms: [
    { room: "LHN-TR+17", status: "free" as const, is_free: true, free_until: "17:50", free_duration_minutes: 125, available_from: null, reason_codes: [], reasons: [] },
    { room: "LHN-TR+15", status: "occupied" as const, is_free: false, free_until: null, free_duration_minutes: null, available_from: "18:20", reason_codes: [], reasons: [] },
    { room: "LHN-TR+19", status: "uncertain" as const, is_free: null, free_until: null, free_duration_minutes: null, available_from: null, reason_codes: ["calendar_exception_uncertain"], reasons: ["Cannot confirm this meeting."] },
  ],
};

function renderPage() { return render(<MemoryRouter><LocationsPage /></MemoryRouter>); }

describe("Location room browser", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-09-15T07:43:00Z"));
    mockedLocations.mockResolvedValue({ locations: [arc, { ...arc, id: "north-spine", name: "North Spine", official_name: null }] });
    mockedRooms.mockResolvedValue(response);
  });
  afterEach(() => { vi.useRealTimers(); vi.resetAllMocks(); });

  it("loads locations, supports selection, and uses Singapore time for Now", async () => {
    renderPage();
    expect(await screen.findByRole("option", { name: /The Arc/ })).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Location"), "north-spine");
    await userEvent.click(screen.getByRole("button", { name: "Now" }));
    await userEvent.click(screen.getByRole("button", { name: "Show rooms" }));
    await waitFor(() => expect(mockedRooms).toHaveBeenCalledWith("north-spine", {
      date: "2026-09-15", time: "15:45",
    }));
  });

  it("renders free first, duration, occupied availability, uncertainty, and intact link", async () => {
    renderPage();
    await screen.findByRole("option", { name: /The Arc/ });
    await userEvent.click(screen.getByRole("button", { name: "Show rooms" }));
    expect(await screen.findByText("Free for 2h 5m · until 17:50")).toBeInTheDocument();
    expect(screen.getByText("Available at 18:20")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Uncertain/ })).toBeInTheDocument();
    const links = screen.getAllByRole("link").filter((link) => link.getAttribute("href")?.startsWith("/rooms/"));
    expect(links[0]).toHaveTextContent("LHN-TR+17");
    expect(links[0]).toHaveAttribute("href", "/rooms/LHN-TR%2B17");
  });

  it("shows non-teaching context without confident room rows", async () => {
    mockedRooms.mockResolvedValue({ ...response, status: "regular_timetable_not_applicable", reason: "The regular class timetable does not apply during recess_week.", rooms: [], calendar: { ...calendar, period_type: "recess_week", teaching_week: null } });
    renderPage(); await screen.findByRole("option", { name: /The Arc/ });
    await userEvent.click(screen.getByRole("button", { name: "Show rooms" }));
    expect(await screen.findByText("Regular timetable not applicable")).toBeInTheDocument();
    expect(screen.queryByText("LHN-TR+17")).not.toBeInTheDocument();
  });
});
