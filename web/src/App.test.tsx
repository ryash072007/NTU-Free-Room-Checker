import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getLocations } from "./api/locations";
import { findFreeRooms } from "./api/rooms";
import App from "./App";
import { freeRooms } from "./test/fixtures";

vi.mock("./api/locations", () => ({ getLocations: vi.fn(), getLocationRooms: vi.fn() }));
vi.mock("./api/rooms", () => ({ findFreeRooms: vi.fn(), getRoomSchedule: vi.fn(), getRoomAvailability: vi.fn(), searchRooms: vi.fn() }));

describe("application routes and navigation", () => {
  beforeEach(() => {
    vi.mocked(getLocations).mockResolvedValue({ locations: [] });
    vi.mocked(findFreeRooms).mockResolvedValue(freeRooms({ rooms: [], uncertain_rooms: [] }));
  });

  it.each(["/", "/locations"])("renders Browse Rooms at %s", async (route) => {
    render(<MemoryRouter initialEntries={[route]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Browse rooms" })).toBeInTheDocument();
  });

  it("has exactly the two product navigation flows", async () => {
    render(<MemoryRouter initialEntries={["/"]}><App /></MemoryRouter>);
    const nav = screen.getByRole("navigation", { name: "Primary navigation" });
    expect(withinNav(nav).map((link) => link.textContent)).toEqual(["Browse Rooms", "Room Schedule"]);
    expect(screen.queryByText("Find a room")).not.toBeInTheDocument();
  });
});

function withinNav(nav: HTMLElement): HTMLAnchorElement[] {
  return Array.from(nav.querySelectorAll("a"));
}
