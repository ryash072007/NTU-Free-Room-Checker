import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { getRoomAvailability, getRoomSchedule } from "../api/rooms";
import { availability, calendar, meeting, schedule } from "../test/fixtures";
import { buildTimeline, RoomPage } from "./RoomPage";

vi.mock("../api/rooms", () => ({
  getRoomSchedule: vi.fn(),
  getRoomAvailability: vi.fn(),
}));
const mockedSchedule = vi.mocked(getRoomSchedule);
const mockedAvailability = vi.mocked(getRoomAvailability);

function renderPage(path = "/rooms/LHN-TR%2B15") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes><Route path="/rooms/:room" element={<RoomPage />} /></Routes>
    </MemoryRouter>,
  );
}

describe("Room schedule page", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-09-15T07:43:00Z"));
    mockedSchedule.mockReset().mockResolvedValue(schedule());
    mockedAvailability.mockReset().mockResolvedValue(availability());
  });
  afterEach(() => vi.useRealTimers());

  it("loads an encoded plus room and shows current confirmed availability", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "LHN-TR+15" })).toBeInTheDocument();
    expect(mockedSchedule).toHaveBeenCalledWith(
      "LHN-TR+15", "2026-09-15", expect.any(AbortSignal),
    );
    expect(await screen.findByText("Free at 15:43")).toBeInTheDocument();
  });

  it("orders meetings and derives only safe free gaps", () => {
    const later = { ...meeting, course_code: "SC3000", scheduled_start: "13:00", scheduled_end: "14:00", effective_start: "13:00", effective_end: "14:00" };
    const timeline = buildTimeline([later, meeting], true);
    expect(timeline.map((item) => item.kind === "meeting" ? item.meeting.course_code : `${item.start}-${item.end}`)).toEqual([
      "SC2008", "12:20-13:00", "SC3000",
    ]);
  });

  it("explains an exception-adjusted effective interval", async () => {
    mockedSchedule.mockResolvedValue(schedule({
      status: "ok_with_adjustments",
      meetings: [{
        ...meeting,
        scheduled_start: "13:30", scheduled_end: "15:20",
        effective_start: "13:30", effective_end: "14:30",
        reason_codes: ["effective_interval_adjusted"],
        reasons: ["Official class-ending cutoff."],
      }],
    }));
    renderPage();
    expect(await screen.findByText(/Scheduled 13:30–15:20/)).toBeInTheDocument();
    expect(screen.getByText(/Ends early by calendar policy/)).toBeInTheDocument();
  });

  it("shows uncertain meetings and does not invent free gaps", async () => {
    mockedSchedule.mockResolvedValue(schedule({
      status: "uncertain",
      reason: "Population cannot be resolved.",
      meetings: [{
        ...meeting,
        applicability: "uncertain",
        uncertain_intervals: [{ start: "10:30", end: "12:00" }],
        confirmed_intervals: [],
        reason_codes: ["population_scope_unknown"],
        reasons: ["Students' Union Day rule may apply."],
      }],
    }));
    mockedAvailability.mockResolvedValue(availability({
      status: "uncertain", is_free: null,
      reasons: ["Students' Union Day rule may apply."],
      reason_codes: ["population_scope_unknown"],
    }));
    renderPage("/rooms/TR%2B15");
    expect(await screen.findByText("Free gaps are hidden because part of this timetable is uncertain.")).toBeInTheDocument();
    expect(screen.getAllByText(/Students' Union Day rule may apply/)).toHaveLength(2);
    expect(screen.queryByText("Confirmed gap in the regular timetable")).not.toBeInTheDocument();
  });

  it("surfaces a non-teaching date instead of showing an empty free day", async () => {
    mockedSchedule.mockResolvedValue(schedule({
      status: "regular_timetable_not_applicable",
      reason: "The regular class timetable does not apply during recess_week.",
      calendar: { ...calendar, period_type: "recess_week", teaching_week: null },
      meetings: [],
    }));
    mockedAvailability.mockResolvedValue(availability({
      status: "regular_timetable_not_applicable", is_free: null,
      reasons: ["Recess week."],
    }));
    renderPage();
    expect(await screen.findByText("Regular timetable not applicable")).toBeInTheDocument();
    expect(screen.queryByText(/No scheduled classes are listed/)).not.toBeInTheDocument();
  });

  it("navigates dates and maps an unknown-room response", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPage();
    await screen.findByText("Daily timetable");
    await user.click(screen.getByRole("button", { name: "Next day" }));
    await waitFor(() => expect(mockedSchedule).toHaveBeenLastCalledWith(
      "LHN-TR+15", "2026-09-16", expect.any(AbortSignal),
    ));
    mockedSchedule.mockRejectedValue(new ApiError(404, "unknown_room", "Room was not found."));
    await user.click(screen.getByRole("button", { name: /Refresh/ }));
    expect(await screen.findByText("Room not found.")).toBeInTheDocument();
  });
});
