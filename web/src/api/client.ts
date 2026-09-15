import type { ApiErrorPayload } from "./types";

const configuredBase = import.meta.env.VITE_API_BASE_URL?.trim();
export const API_BASE_URL = (configuredBase || "/api/v1").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

export async function apiGet<T>(
  path: string,
  parameters: Record<string, string | number | boolean | undefined> = {},
  signal?: AbortSignal,
): Promise<T> {
  const query = new URLSearchParams();
  Object.entries(parameters).forEach(([key, value]) => {
    if (value !== undefined) query.set(key, String(value));
  });
  const suffix = query.size ? `?${query.toString()}` : "";
  const response = await fetch(`${API_BASE_URL}${path}${suffix}`, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    let payload: ApiErrorPayload = {};
    try {
      payload = (await response.json()) as ApiErrorPayload;
    } catch {
      // A useful status-based message is supplied below.
    }
    throw new ApiError(
      response.status,
      payload.error?.code || "request_failed",
      payload.error?.message || `Request failed (${response.status}).`,
    );
  }
  return (await response.json()) as T;
}
