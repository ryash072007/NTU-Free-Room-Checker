import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getLocationRooms, getLocations } from "../api/locations";
import { findFreeRooms } from "../api/rooms";
import { calendar, freeRooms } from "../test/fixtures";
import { LocationsPage } from "./LocationsPage";

vi.mock("../api/locations", () => ({ getLocations: vi.fn(), getLocationRooms: vi.fn() }));
vi.mock("../api/rooms", () => ({ findFreeRooms: vi.fn() }));
const mockedLocations = vi.mocked(getLocations);
const mockedLocationRooms = vi.mocked(getLocationRooms);
const mockedFreeRooms = vi.mocked(findFreeRooms);

const arc = { id: "the-arc", name: "The Arc", official_name: "Learning Hub North", short_name: "Arc", aliases: ["LHN"], room_count: 3 };
const namedResponse = {
  location: arc, date: "2026-09-15", requested_time: "15:45", duration_minutes: 1,
  status: "ok" as const, reason: "", calendar,
  rooms: [
    { room: "LHN-TR+17", status: "free" as const, is_free: true, free_until: "17:50", free_duration_minutes: 125, available_from: null, reason_codes: [], reasons: [] },
    { room: "LHN-TR+15", status: "occupied" as const, is_free: false, free_until: null, free_duration_minutes: null, available_from: "18:20", reason_codes: [], reasons: [] },
    { room: "LHN-TR+19", status: "uncertain" as const, is_free: null, free_until: null, free_duration_minutes: null, available_from: null, reason_codes: ["calendar_exception_uncertain"], reasons: ["Cannot confirm this meeting."] },
  ],
};

function renderPage() { return render(<MemoryRouter><LocationsPage /></MemoryRouter>); }

describe("Browse Rooms", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-09-15T07:43:00Z"));
    mockedLocations.mockResolvedValue({ locations: [arc] });
    mockedLocationRooms.mockResolvedValue(namedResponse);
    mockedFreeRooms.mockResolvedValue(freeRooms({
      rooms: [
        { room: "LHN-TR+17", free_until: "17:50", free_duration_minutes: 125 },
        { room: "UNMAPPED-LAB", free_until: null, free_duration_minutes: null },
      ],
      uncertain_rooms: [{ room: "TR+17", reason_codes: ["unparsed_timetable_meeting"], reasons: ["Cannot confirm this room."] }],
    }));
  });
  afterEach(() => { vi.useRealTimers(); vi.resetAllMocks(); });

  it("defaults to Anywhere on campus and reactively loads unmapped free rooms", async () => {
    renderPage();
    expect(screen.getByLabelText("Location")).toHaveValue("anywhere");
    expect(await screen.findByText("UNMAPPED-LAB")).toBeInTheDocument();
    expect(mockedFreeRooms).toHaveBeenCalledWith(expect.objectContaining({
      date: "2026-09-15", time: "15:43", duration: 1, limit: 1000,
    }), expect.any(AbortSignal));
    expect(screen.getByRole("heading", { name: /Uncertain/ })).toBeInTheDocument();
    const roomLinks = screen.getAllByRole("link").filter((link) => link.getAttribute("href")?.startsWith("/rooms/"));
    expect(roomLinks[0]).toHaveTextContent("UNMAPPED-LAB");
  });

  it("selects a named location and renders all three status groups", async () => {
    renderPage(); await screen.findByText("UNMAPPED-LAB");
    await userEvent.selectOptions(screen.getByLabelText("Location"), "the-arc");
    expect(await screen.findByText("Available at 18:20")).toBeInTheDocument();
    expect(screen.getByText("Free for 2h 5m · until 17:50")).toBeInTheDocument();
    expect(screen.getByText("Cannot confirm this meeting.")).toBeInTheDocument();
    expect(mockedLocationRooms).toHaveBeenCalledWith("the-arc", { date: "2026-09-15", time: "15:43" }, expect.any(AbortSignal));
  });

  it("uses Singapore Now and duration filters campus-wide at the source", async () => {
    renderPage(); await screen.findByText("UNMAPPED-LAB");
    await userEvent.click(screen.getByRole("button", { name: "Now" }));
    await userEvent.selectOptions(screen.getByLabelText("Need it for"), "120");
    await waitFor(() => expect(mockedFreeRooms).toHaveBeenLastCalledWith(expect.objectContaining({
      time: "15:45", duration: 120,
    }), expect.any(AbortSignal)));
  });

  it("filters short free rooms for a named location and supports room-name sorting", async () => {
    renderPage(); await screen.findByText("UNMAPPED-LAB");
    await userEvent.selectOptions(screen.getByLabelText("Location"), "the-arc");
    await screen.findByText("LHN-TR+17");
    await userEvent.selectOptions(screen.getByLabelText("Need it for"), "180");
    expect(screen.queryByText("LHN-TR+17")).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Sort"), "name");
    const links = screen.getAllByRole("link").filter((link) => link.getAttribute("href")?.startsWith("/rooms/"));
    expect(links[0]).toHaveTextContent("LHN-TR+15");
  });

  it("preserves canonical plus identifiers and encoded room navigation", async () => {
    renderPage(); await screen.findByText("UNMAPPED-LAB");
    await userEvent.selectOptions(screen.getByLabelText("Location"), "the-arc");
    const link = await screen.findByRole("link", { name: /LHN-TR\+17/ });
    expect(link).toHaveAttribute("href", "/rooms/LHN-TR%2B17");
  });

  it("shows a page-level non-teaching state without room claims", async () => {
    mockedFreeRooms.mockResolvedValue(freeRooms({ status: "regular_timetable_not_applicable", reason: "The regular class timetable does not apply during recess_week.", calendar: { ...calendar, period_type: "recess_week", teaching_week: null }, rooms: [], uncertain_rooms: [] }));
    renderPage();
    expect(await screen.findByText("Regular timetable not applicable")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /^Free/ })).not.toBeInTheDocument();
  });

  it("keeps compact semantic list markup for mobile styling", async () => {
    renderPage(); await screen.findByText("UNMAPPED-LAB");
    const freeHeading = screen.getByRole("heading", { name: /Free/ });
    expect(within(freeHeading.closest("section")!).getByRole("list")).toBeInTheDocument();
  });
});
