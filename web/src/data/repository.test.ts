import { afterEach, describe, expect, it, vi } from "vitest";
import { clearDataCache } from "./cache";
import { getAreaBusyness } from "./repository";

afterEach(() => { vi.unstubAllGlobals(); clearDataCache(); });

const locationsPayload = {
  schema_version: 1,
  locations: [
    { id: "the-arc", name: "The Arc", official_name: null, short_name: "Arc", aliases: [], room_count: 2, rooms: ["A1", "A2"] },
    { id: "north-spine", name: "North Spine", official_name: null, short_name: "North Spine", aliases: [], room_count: 1, rooms: ["N1"] },
  ],
};

function mockFetch(day: unknown) {
  return vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(
    url.endsWith("locations.json") ? locationsPayload : day,
  ), { status: 200 })));
}

describe("getAreaBusyness", () => {
  it("counts free/occupied/uncertain per location by reusing per-room evaluation", async () => {
    vi.stubGlobal("fetch", mockFetch({
      schema_version: 1, date: "2026-09-15", status: "ok", reason: "", reason_code: "", calendar: {},
      unparsed_rooms: ["A2"],
      rooms: {
        A1: { status: "ok", reason: "", schedule: [], occupied_blocks: [[540, 600, [1]]], uncertain_blocks: [] },
        N1: { status: "ok", reason: "", schedule: [], occupied_blocks: [], uncertain_blocks: [] },
      },
    }));

    const result = await getAreaBusyness({ date: "2026-09-15", time: "09:30" });

    expect(result).toEqual([
      { id: "the-arc", name: "The Arc", room_count: 2, free: 0, occupied: 1, uncertain: 1 },
      { id: "north-spine", name: "North Spine", room_count: 1, free: 1, occupied: 0, uncertain: 0 },
    ]);
  });

  it("never counts a room as free when the calendar day is not authoritative", async () => {
    vi.stubGlobal("fetch", mockFetch({
      schema_version: 1, date: "2026-09-29", status: "regular_timetable_not_applicable",
      reason: "The regular class timetable does not apply.", reason_code: "recess_week",
      calendar: {}, unparsed_rooms: [], rooms: {},
    }));

    const result = await getAreaBusyness({ date: "2026-09-29", time: "09:30" });

    expect(result.find((item) => item.id === "the-arc")).toEqual(
      { id: "the-arc", name: "The Arc", room_count: 2, free: 0, occupied: 0, uncertain: 2 },
    );
  });
});
