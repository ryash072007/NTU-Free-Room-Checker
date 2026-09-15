"""Parse NTU result HTML without relying on browser state."""

import re
from collections.abc import Iterable

from bs4 import BeautifulSoup, Tag

from ntu_room_checker.scraper.models import ScheduleEntry

SCHEDULE_HEADERS = ("INDEX", "TYPE", "GROUP", "DAY", "TIME", "VENUE", "REMARK")


def _text(cell: Tag) -> str:
    # Preserve punctuation/casing while removing indentation introduced by HTML.
    return " ".join(cell.stripped_strings)


def _expanded_rows(table: Tag) -> list[list[str]]:
    """Return a rectangular grid, expanding HTML rowspan and colspan values."""
    rows: list[list[str]] = []
    spans: dict[int, tuple[str, int]] = {}
    for tr in table.find_all("tr", recursive=False) or table.select(":scope > tbody > tr"):
        row: list[str] = []
        column = 0
        cells = tr.find_all(["th", "td"], recursive=False)
        for cell in cells:
            while column in spans:
                value, remaining = spans[column]
                row.append(value)
                if remaining == 1:
                    del spans[column]
                else:
                    spans[column] = (value, remaining - 1)
                column += 1
            value = _text(cell)
            rowspan = max(1, int(cell.get("rowspan", 1)))
            colspan = max(1, int(cell.get("colspan", 1)))
            for _ in range(colspan):
                row.append(value)
                if rowspan > 1:
                    spans[column] = (value, rowspan - 1)
                column += 1
        while column in spans:
            value, remaining = spans[column]
            row.append(value)
            if remaining == 1:
                del spans[column]
            else:
                spans[column] = (value, remaining - 1)
            column += 1
        rows.append(row)
    return rows


def _module_metadata(table: Tag) -> dict[str, str] | None:
    rows = _expanded_rows(table)
    if not rows or len(rows[0]) < 2:
        return None
    code = rows[0][0].strip()
    if not re.fullmatch(r"[A-Z]{1,6}[A-Z0-9]*\d[A-Z0-9]*", code, re.IGNORECASE):
        return None
    remark = ""
    for row in rows[1:]:
        if row and row[0].rstrip(":").strip().lower() == "remark":
            remark = row[1].strip() if len(row) > 1 else ""
            break
    return {
        "course_code": code,
        "course_title": rows[0][1].strip(),
        "academic_units": rows[0][2].strip() if len(rows[0]) > 2 else "",
        "course_remark": remark,
    }


def parse_schedule_html(html: str) -> list[ScheduleEntry]:
    """Parse all module/class rows from one NTU programme result page."""
    soup = BeautifulSoup(html, "html.parser")
    entries: list[ScheduleEntry] = []
    current_module: dict[str, str] | None = None

    for table_index, table in enumerate(soup.find_all("table")):
        metadata = _module_metadata(table)
        if metadata is not None:
            current_module = metadata
            continue

        rows = _expanded_rows(table)
        if not rows or tuple(value.upper() for value in rows[0][:7]) != SCHEDULE_HEADERS:
            continue
        if current_module is None:
            continue

        inherited = ["", "", ""]
        for row_index, row in enumerate(rows[1:], start=1):
            padded = (row + [""] * 7)[:7]
            if not any(value.strip() for value in padded):
                continue
            for index in range(3):
                if padded[index].strip():
                    inherited[index] = padded[index].strip()
                else:
                    padded[index] = inherited[index]
            raw = dict(zip(SCHEDULE_HEADERS, padded, strict=True))
            raw.update({"source_table_index": table_index, "source_row_index": row_index})
            entries.append(
                ScheduleEntry(
                    **current_module,
                    index_number=padded[0],
                    class_type=padded[1],
                    group_name=padded[2],
                    day=padded[3],
                    time=padded[4],
                    venue=padded[5],
                    remark=padded[6],
                    raw_fields=raw,
                )
            )
    return entries
