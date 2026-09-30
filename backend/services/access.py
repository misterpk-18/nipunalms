"""How long a student can watch recordings and open materials (Modules 17 §8 and 18 §5).

The clock is one calendar year from the enrolment's confirmed Joining Date, through the end of the anniversary day in
IST. One student-requested extension reaches the second anniversary of that same Joining Date, never one year from the
request, and repeated requests do not add years. Recordings and materials are separate clocks: an approved extension
covers the scope it was granted for (Recording, Material or Both). Before the student has joined there is no date, so
access shows as pending instead of an invented expiry.
"""
from dataclasses import dataclass
from datetime import date

from models import AccessExtensionRequest, Enrolment
from repositories import access_extensions as extensions_repo
from repositories import settings as settings_repo

KINDS = ("Recording", "Material")


def anniversary(joining_date: date, years: int) -> date:
    """The same calendar day `years` later; a 29 February Joining Date uses 1 March in a non-leap year."""
    try:
        return joining_date.replace(year=joining_date.year + years)
    except ValueError:
        return date(joining_date.year + years, 3, 1)


def _covers(request: AccessExtensionRequest, kind: str) -> bool:
    return request.scope == "Both" or request.scope == kind


@dataclass(frozen=True)
class AccessWindow:
    """The access dates of one enrolment: the standard first and second anniversaries and the current expiry per kind."""

    joining_date: date | None
    first_expiry: date | None
    second_expiry: date | None
    expiry: dict[str, date | None]  # kind -> current expiry (extensions applied); None until the student has joined

    def state(self, kind: str, today: date) -> str:
        """Pending (no Joining Date yet), Available or Expired."""
        expiry = self.expiry[kind]
        if expiry is None:
            return "Pending"
        return "Expired" if today > expiry else "Available"

    def extended(self, kind: str) -> bool:
        """The routine extra year has been used for this kind."""
        expiry = self.expiry[kind]
        return expiry is not None and self.second_expiry is not None and expiry >= self.second_expiry

    def describe(self, kind: str, today: date) -> dict:
        return {"state": self.state(kind, today), "expiry": self.expiry[kind], "extended": self.extended(kind)}


def window_for(enrolment: Enrolment, approved: list[AccessExtensionRequest] | None = None) -> AccessWindow:
    """Access dates for an enrolment. `approved` = its Approved extension requests (looked up when not given)."""
    if enrolment.joining_date is None:
        return AccessWindow(None, None, None, {kind: None for kind in KINDS})
    if approved is None:
        approved = extensions_repo.approved_for_enrolment(enrolment.enrolment_id)
    first = anniversary(enrolment.joining_date, settings_repo.get_int("access_default_years", 1))
    second = anniversary(enrolment.joining_date, settings_repo.get_int("access_max_years", 2))
    expiry = {}
    for kind in KINDS:
        dates = [first] + [r.approved_expiry for r in approved if _covers(r, kind) and r.approved_expiry]
        expiry[kind] = max(dates)
    return AccessWindow(enrolment.joining_date, first, second, expiry)


def windows_for(enrolments: list[Enrolment]) -> dict[int, AccessWindow]:
    """window_for() for several enrolments with one extension query."""
    approved = extensions_repo.approved_for_enrolments([e.enrolment_id for e in enrolments])
    return {e.enrolment_id: window_for(e, approved.get(e.enrolment_id, [])) for e in enrolments}
