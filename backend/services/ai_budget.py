"""The monthly AI budget in rupees: what Ask Nipuna may cost in a month. The Founder / CEO (or a Super Admin) approves the amount
after the developer's estimate; until then the dashboards say it is waiting (U16: it is an item in the Founder's inbox)."""
from repositories import settings as settings_repo
from services import audit
from services.context import current_user
from services.errors import ValidationError

SETTING = "ai_monthly_ceiling_inr"
MAX_INR = 10_000_000


def state() -> dict:
    amount = settings_repo.get(SETTING)
    return {"state": "Configuration Pending"} if amount is None else {"state": "Configured", "amount_inr": amount}


def approve(amount_inr: int) -> dict:
    if amount_inr < 1 or amount_inr > MAX_INR:
        raise ValidationError("Enter a monthly amount in rupees", {"amount_inr": [f"Must be between 1 and {MAX_INR:,}"]})
    before = settings_repo.get(SETTING)
    settings_repo.set_value(SETTING, amount_inr, current_user().user_id, "Approved monthly AI budget in rupees (Founder / CEO)")
    audit.record("AI_BUDGET_APPROVED", "app_setting", SETTING, old={"amount_inr": before}, new={"amount_inr": amount_inr})
    return state()
