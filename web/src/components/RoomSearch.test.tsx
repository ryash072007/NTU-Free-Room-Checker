import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { searchRooms } from "../api/rooms";
import { RoomSearch } from "./RoomSearch";

vi.mock("../api/rooms", () => ({ searchRooms: vi.fn() }));
const mockedSearch = vi.mocked(searchRooms);

describe("Room autocomplete", () => {
  beforeEach(() => {
    mockedSearch.mockReset();
    mockedSearch.mockResolvedValue({
      rooms: [
        { id: "LHN-TR+15", name: "LHN-TR+15" },
        { id: "LHN-TR+16", name: "LHN-TR+16" },
      ],
      count: 2,
    });
  });
  it("debounces server-side exact/prefix search", async () => {
    render(<RoomSearch onSelect={vi.fn()} />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "LHN" } });
    expect(mockedSearch).not.toHaveBeenCalled();
    await waitFor(() => expect(mockedSearch).toHaveBeenCalledWith(
      "LHN", 8, expect.any(AbortSignal),
    ));
    expect(await screen.findByText("LHN-TR+15")).toBeInTheDocument();
  });

  it("supports arrow keys, Enter, and a room containing plus", async () => {
    const onSelect = vi.fn();
    render(<RoomSearch onSelect={onSelect} />);
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "TR+" } });
    await screen.findByText("LHN-TR+15");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith("LHN-TR+16");
  });
});
