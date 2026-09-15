"""DOM-level interaction with NTU's public class schedule form."""

import re
from dataclasses import dataclass

from playwright.sync_api import Page

from ntu_room_checker.scraper.models import AcademicTerm, ProgrammeOption

SCHEDULE_URL = "https://wish.wis.ntu.edu.sg/webexe/owa/AUS_SCHEDULE.class"
ACADEMIC_TERM_SELECTOR = 'select[name="acadsem"]'
PROGRAMME_SELECTOR = 'select[name="r_course_yr"]'
LOAD_BUTTON_SELECTOR = 'input[type="button"][value="Load Class Schedule"]'


@dataclass(slots=True)
class ScheduleLandingPage:
    page: Page
    timeout_ms: int = 60_000

    def load(self, academic_term: str | None = None) -> None:
        response = self.page.goto(
            SCHEDULE_URL, wait_until="domcontentloaded", timeout=self.timeout_ms
        )
        if response is not None and not response.ok:
            raise RuntimeError(f"NTU schedule page returned HTTP {response.status}")
        self.page.locator(PROGRAMME_SELECTOR).wait_for(timeout=self.timeout_ms)
        if academic_term and self.current_term().value != academic_term:
            with self.page.expect_navigation(
                wait_until="domcontentloaded", timeout=self.timeout_ms
            ):
                self.page.locator(ACADEMIC_TERM_SELECTOR).select_option(academic_term)
            self.page.locator(PROGRAMME_SELECTOR).wait_for(timeout=self.timeout_ms)

    def terms(self) -> list[AcademicTerm]:
        options = self.page.locator(f"{ACADEMIC_TERM_SELECTOR} option")
        terms: list[AcademicTerm] = []
        for index in range(options.count()):
            option = options.nth(index)
            value = (option.get_attribute("value") or "").strip()
            label = option.inner_text().strip()
            if not value:
                continue
            year, semester = value.split(";", maxsplit=1)
            terms.append(AcademicTerm(value, label, year, semester))
        return terms

    def current_term(self) -> AcademicTerm:
        selected_value = self.page.locator(ACADEMIC_TERM_SELECTOR).input_value()
        return next(term for term in self.terms() if term.value == selected_value)

    def programmes(self) -> list[ProgrammeOption]:
        options = self.page.locator(f"{PROGRAMME_SELECTOR} option")
        programmes: list[ProgrammeOption] = []
        for index in range(options.count()):
            option = options.nth(index)
            value = (option.get_attribute("value") or "").strip()
            label = re.sub(r"\s+", " ", option.inner_text()).strip()
            if value:
                programmes.append(ProgrammeOption(value=value, label=label))
        return programmes

    def load_programme(self, option: ProgrammeOption) -> Page:
        select = self.page.locator(PROGRAMME_SELECTOR)
        select.select_option(value=option.value)
        if select.input_value() != option.value:
            raise RuntimeError(f"Failed to select programme {option.value!r}")
        with self.page.expect_popup(timeout=self.timeout_ms) as popup_info:
            self.page.locator(LOAD_BUTTON_SELECTOR).click()
        result = popup_info.value
        result.wait_for_load_state("domcontentloaded", timeout=self.timeout_ms)
        result.locator("body").wait_for(timeout=self.timeout_ms)
        if "AUS_SCHEDULE.main_display1" not in result.url:
            result.close()
            raise RuntimeError(f"Unexpected result URL: {result.url}")
        return result
