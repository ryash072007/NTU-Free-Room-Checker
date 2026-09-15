"""Fault-tolerant orchestration of sequential programme scrapes."""

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

from ntu_room_checker.scraper.browser import browser_page
from ntu_room_checker.scraper.models import ProgrammeOption
from ntu_room_checker.scraper.parser import parse_schedule_html
from ntu_room_checker.scraper.schedule_page import SCHEDULE_URL, ScheduleLandingPage
from ntu_room_checker.scraper.storage import ScheduleStorage

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ScrapeConfig:
    db_path: Path
    headless: bool = True
    programme: str | None = None
    limit: int | None = None
    resume: bool = False
    academic_term: str | None = None
    delay_seconds: float = 1.0
    retries: int = 3
    timeout_ms: int = 60_000
    debug_dir: Path | None = None


def _filter_programmes(
    programmes: list[ProgrammeOption], requested: str | None
) -> list[ProgrammeOption]:
    if requested is None:
        return programmes
    exact_value = [item for item in programmes if item.value == requested]
    if exact_value:
        return exact_value
    exact_label = [item for item in programmes if item.label.casefold() == requested.casefold()]
    if exact_label:
        return exact_label
    raise ValueError(
        f"No programme with value or exact label {requested!r}. "
        "Use the value shown by --list-programmes."
    )


def discover(*, headless: bool, timeout_ms: int) -> tuple[object, list[ProgrammeOption]]:
    with browser_page(headless=headless) as page:
        landing = ScheduleLandingPage(page, timeout_ms)
        landing.load()
        return landing.current_term(), landing.programmes()


def run_scrape(config: ScrapeConfig) -> tuple[int, str]:
    with browser_page(headless=config.headless) as page:
        landing = ScheduleLandingPage(page, config.timeout_ms)
        landing.load(config.academic_term)
        term = landing.current_term()
        programmes = _filter_programmes(landing.programmes(), config.programme)
        if config.limit is not None:
            programmes = programmes[: config.limit]
        if not programmes:
            raise ValueError("No programme selections remain after filtering")

        with ScheduleStorage(config.db_path) as storage:
            run_id = storage.start_run(SCHEDULE_URL, term, resume=config.resume)
            storage.register_programmes(run_id, programmes)
            remaining = storage.remaining_programmes(run_id)
            total = len(remaining)
            LOGGER.info(
                "Scrape run %s: %s, %d programme selection(s) remaining",
                run_id, term.label, total,
            )
            for position, selection in enumerate(remaining, start=1):
                option = ProgrammeOption(selection["option_value"], selection["option_label"])
                LOGGER.info("[%d/%d] %s", position, total, option.label)
                last_error: Exception | None = None
                for attempt in range(1, config.retries + 1):
                    result = None
                    try:
                        storage.mark_selection_running(selection["id"])
                        # A fresh landing-page load avoids stale state in this OWA form.
                        landing.load(term.value)
                        result = landing.load_programme(option)
                        html = result.content()
                        entries = parse_schedule_html(html)
                        count = storage.save_entries(run_id, selection["id"], entries)
                        module_count = len({entry.course_code for entry in entries})
                        LOGGER.info("  %d modules; %d schedule entries saved", module_count, count)
                        last_error = None
                        break
                    except Exception as error:  # isolate a failure to one selection
                        last_error = error
                        LOGGER.warning(
                            "  attempt %d/%d failed: %s", attempt, config.retries, error
                        )
                        if config.debug_dir is not None and result is not None:
                            config.debug_dir.mkdir(parents=True, exist_ok=True)
                            slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", option.value).strip("_")
                            (config.debug_dir / f"failed_{slug}.html").write_text(
                                result.content(), encoding="utf-8"
                            )
                        if attempt < config.retries:
                            time.sleep(config.delay_seconds)
                    finally:
                        if result is not None:
                            result.close()
                if last_error is not None:
                    storage.mark_selection_failed(selection["id"], repr(last_error))
                    LOGGER.error("  selection failed; continuing")
                if position < total:
                    time.sleep(config.delay_seconds)
            return run_id, storage.finish_run(run_id)
