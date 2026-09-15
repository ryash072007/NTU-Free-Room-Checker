import { useEffect, useId, useState } from "react";
import { searchRooms } from "../api/rooms";
import type { RoomSearchItem } from "../api/types";
import { useDebouncedValue } from "../hooks/useDebouncedValue";

export function RoomSearch({ onSelect, autoFocus = false }: {
  onSelect: (room: string) => void;
  autoFocus?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<RoomSearchItem[]>([]);
  const [active, setActive] = useState(-1);
  const [loading, setLoading] = useState(false);
  const debounced = useDebouncedValue(query, 250);
  const listId = useId();

  useEffect(() => {
    if (!debounced.trim()) {
      setResults([]);
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    searchRooms(debounced, 8, controller.signal)
      .then((response) => {
        setResults(response.rooms);
        setActive(response.rooms.length ? 0 : -1);
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) setResults([]);
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [debounced]);

  const choose = (room: RoomSearchItem) => {
    setQuery(room.name);
    setResults([]);
    onSelect(room.name);
  };

  return (
    <div className="room-search">
      <label htmlFor={`${listId}-input`}>Room name</label>
      <div className="search-field">
        <span aria-hidden="true">⌕</span>
        <input
          id={`${listId}-input`}
          autoFocus={autoFocus}
          value={query}
          placeholder="Try LHN, TR+15, LT…"
          role="combobox"
          aria-autocomplete="list"
          aria-controls={listId}
          aria-expanded={results.length > 0}
          aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setActive((value) => Math.min(value + 1, results.length - 1));
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              setActive((value) => Math.max(value - 1, 0));
            } else if (event.key === "Enter" && active >= 0) {
              event.preventDefault();
              choose(results[active]);
            } else if (event.key === "Escape") {
              setResults([]);
              setActive(-1);
            }
          }}
        />
        {loading && <span className="inline-loader" aria-label="Searching rooms" />}
      </div>
      {results.length > 0 && (
        <ul id={listId} role="listbox" className="search-results">
          {results.map((room, index) => (
            <li
              id={`${listId}-${index}`}
              key={room.id}
              role="option"
              aria-selected={index === active}
            >
              <button type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => choose(room)}>
                <strong>{room.name}</strong><span>View schedule →</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
