import { afterEach, describe, expect, it, vi } from "vitest";
import { clearDataCache } from "../data/cache";
import { getRoomSchedule } from "./rooms";

afterEach(() => { vi.unstubAllGlobals(); clearDataCache(); });

describe("static data repository", () => {
  it("loads room schedules from date-scoped static assets without API calls", async () => {
    const fetchMock = vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(
      url.endsWith("rooms.json") ? { schema_version: 1, rooms: [{ id: "LHN-TR+15", name: "LHN-TR+15" }] } :
        { schema_version: 1, date: "2026-09-15", status: "ok", reason: "", reason_code: "", calendar: {}, rooms: {}, unparsed_rooms: [] },
    ), { status: 200 })));
    vi.stubGlobal("fetch", fetchMock);
    await getRoomSchedule("LHN-TR+15", "2026-09-15");
    await getRoomSchedule("LHN-TR+15", "2026-09-15");
    expect(fetchMock.mock.calls.map((call) => call[0])).toContain("/data/days/2026-09-15.json");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls.some((call) => String(call[0]).includes("/api/"))).toBe(false);
  });
});
