import { apiGet } from "./client";
import type { LocationItem, LocationRoomsResponse } from "./types";

export function getLocations(signal?: AbortSignal) {
  return apiGet<{ locations: LocationItem[] }>("/locations", {}, signal);
}

export function getLocationRooms(
  locationId: string,
  query: { date: string; time: string; duration?: number },
  signal?: AbortSignal,
) {
  return apiGet<LocationRoomsResponse>(
    `/locations/${encodeURIComponent(locationId)}/rooms`, query, signal,
  );
}
