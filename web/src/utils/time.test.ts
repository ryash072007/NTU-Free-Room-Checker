import { describe, expect, it } from "vitest";
import { formatDuration, roundedSingaporeDateTime, shiftIsoDate, singaporeDateTime } from "./time";

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
    expect(formatDuration(150)).toBe("2h 30m");
    expect(shiftIsoDate("2026-09-30", 1)).toBe("2026-10-01");
  });
});
