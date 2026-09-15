import { describe, expect, it } from "vitest";
import {
  ROOM_TRANSITION_MINUTES,
  formatDuration,
  roundedSingaporeDateTime,
  shiftIsoDate,
  singaporeDateTime,
} from "./time";

describe("Singapore time utilities", () => {
  it("uses Asia/Singapore instead of the browser timezone", () => {
    expect(singaporeDateTime(new Date("2026-09-15T16:31:00Z"))).toEqual({
      date: "2026-09-16", time: "00:31",
    });
  });

  it("rounds now up to a five-minute Singapore-local boundary", () => {
    expect(roundedSingaporeDateTime(new Date("2026-09-15T07:43:00Z"))).toEqual({
      date: "2026-09-15", time: "15:45",
    });
  });

  it("formats durations and shifts dates across month boundaries", () => {
    expect(ROOM_TRANSITION_MINUTES).toBe(10);
    expect(formatDuration(150)).toBe("2h 30m");
    expect(shiftIsoDate("2026-09-30", 1)).toBe("2026-10-01");
  });

  it("handles 5-minute rounding and midnight/year rollover in Singapore time", () => {
    // 23:54 SGT -> rounds to 23:55
    expect(roundedSingaporeDateTime(new Date("2026-09-15T15:54:00Z"))).toEqual({
      date: "2026-09-15", time: "23:55",
    });
    // 23:56 SGT -> next 5-minute boundary moves to next day 00:00
    expect(roundedSingaporeDateTime(new Date("2026-09-15T15:56:00Z"))).toEqual({
      date: "2026-09-16", time: "00:00",
    });
    // Year-end rollover: 2026-12-31 23:56 SGT -> 2027-01-01 00:00
    expect(roundedSingaporeDateTime(new Date("2026-12-31T15:56:00Z"))).toEqual({
      date: "2027-01-01", time: "00:00",
    });
  });

  it("handles leap year and month-end date shifts", () => {
    expect(shiftIsoDate("2026-12-31", 1)).toBe("2027-01-01");
    // Leap year 2028
    expect(shiftIsoDate("2028-02-28", 1)).toBe("2028-02-29");
    expect(shiftIsoDate("2028-02-29", 1)).toBe("2028-03-01");
    // Non-leap year 2027
    expect(shiftIsoDate("2027-02-28", 1)).toBe("2027-03-01");
  });
});
