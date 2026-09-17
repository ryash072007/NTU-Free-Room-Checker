import { describe, expect, it } from "vitest";
import { evaluateRoom, locationItem } from "./evaluator";
import type { StaticDay } from "./types";

const day: StaticDay = {
  schema_version: 1, date: "2026-09-15", status: "ok", reason: "", reason_code: "",
  calendar: {} as StaticDay["calendar"], unparsed_rooms: [],
  rooms: { "LHN-TR+15": { status: "ok", reason: "", schedule: [
    { course_code: "X", course_title: "X", index_number: "1", class_type: "TUT", group: "1",
      scheduled_start: "10:30", scheduled_end: "12:20", effective_start: "10:30", effective_end: "12:20",
      applicability: "applicable", remark: "", teaching_weeks: [], confirmed_intervals: [{ start: "10:30", end: "12:20" }], uncertain_intervals: [], reason_codes: [], reasons: [] },
  ], occupied_blocks: [[630, 1100, [1, 2, 3, 4]]], uncertain_blocks: [] } },
};

describe("static availability evaluator", () => {
  it("treats a coalesced ten-minute transition as occupied", () => {
    const value = evaluateRoom("LHN-TR+15", day, "12:25", 5);
    expect(value.status).toBe("occupied");
    expect(value.reason_codes).toContain("room_transition_buffer");
  });

  it("reports the end of a coalesced occupied block", () => {
    const value = evaluateRoom("LHN-TR+15", day, "15:00", 30);
    expect(value.occupied_intervals[0].end).toBe("18:20");
  });

  it("never turns an unparsed meeting into free evidence", () => {
    expect(evaluateRoom("UNKNOWN-DATA", { ...day, unparsed_rooms: ["UNKNOWN-DATA"] }, "12:00", 1).status).toBe("uncertain");
  });

  it("merges class_types and capacity catalog data into a location room item", () => {
    const item = locationItem("LHN-TR+15", day, "15:00", 30, {
      id: "LHN-TR+15", name: "LHN-TR+15", class_types: ["TUT"], capacity: 48,
      bookable_by_staff: true, bookable_by_student_orgs: false,
    });
    expect(item.class_types).toEqual(["TUT"]);
    expect(item.capacity).toBe(48);
    expect(item.bookable_by_staff).toBe(true);
    expect(item.bookable_by_student_orgs).toBe(false);
  });

  it("defaults catalog fields conservatively when no catalog entry is given", () => {
    const item = locationItem("LHN-TR+15", day, "15:00", 30);
    expect(item.class_types).toEqual([]);
    expect(item.capacity).toBeNull();
    expect(item.bookable_by_staff).toBeNull();
    expect(item.bookable_by_student_orgs).toBeNull();
  });
});
