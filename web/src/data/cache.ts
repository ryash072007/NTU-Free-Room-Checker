const cache = new Map<string, Promise<unknown>>();

export function cachedJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  let pending = cache.get(url) as Promise<T> | undefined;
  if (!pending) {
    pending = fetch(url, { headers: { Accept: "application/json" } }).then(async (response) => {
      if (!response.ok) throw new Error(`Static data request failed (${response.status})`);
      return await response.json() as T;
    }).catch((error) => { cache.delete(url); throw error; });
    cache.set(url, pending);
  }
  if (!signal) return pending;
  if (signal.aborted) return Promise.reject(new DOMException("Aborted", "AbortError"));
  return Promise.race([pending, new Promise<T>((_, reject) => signal.addEventListener(
    "abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true },
  ))]);
}

export function clearDataCache() { cache.clear(); }
