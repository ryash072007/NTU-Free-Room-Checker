import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiGet } from "./client";
import { getRoomSchedule } from "./rooms";

afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
  it("URL-encodes plus signs in room identifiers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await getRoomSchedule("LHN-TR+15", "2026-09-15");
    expect(fetchMock.mock.calls[0][0]).toContain("/rooms/LHN-TR%2B15/schedule");
  });

  it("turns the structured API error envelope into an ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: { code: "unknown_room", message: "Room was not found." },
    }), { status: 404 })));
    await expect(apiGet("/rooms/nope")).rejects.toEqual(
      expect.objectContaining<Partial<ApiError>>({ status: 404, code: "unknown_room" }),
    );
  });
});
