"""db 096: BranchUpserted and BranchFinanceSnapshot from the CRM (round-2 decisions D3 and D4), and the dashboard
figures the snapshots feed."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from config.database import db
from tests import helpers
from tests.library_helpers import API, auth
from tests.test_exception_queue import world  # noqa: F401  (the two-branch world the dashboard tests use)

NEW_BRANCH = {"branch_code": "NIT-TEN", "branch_name": "Tenali", "city": "Tenali", "receipt_prefix": "TEN",
              "email": "tenali@example.test", "address": "Main Road", "phone": "+91 90000 00000", "is_active": True}


def _branch(code: str) -> dict:
    row = db.session.execute(text("SELECT branch_name, short_code, mailbox, is_active, source_version FROM branches"
                                  " WHERE branch_code = :c"), {"c": code}).mappings().one_or_none()
    return dict(row) if row else None


def snapshot(branch_code="NIT-GNT", *, as_of=None, period=True, **overrides) -> dict:
    data = {
        "branch_code": branch_code,
        "as_of": (as_of or datetime.now(timezone.utc)).isoformat(),
        "period": {"label": "Oct 2026", "start": "2026-10-01", "end": "2026-10-31"} if period else None,
        "collections": {"verified": "120000.00", "target": "500000.00"},
        "paid_admissions": {"count": 12, "target": 40},
        "overdue": {"amount": "45000.00", "count": 7, "by_age_band": [{"band": "1-30 days", "amount": "30000.00", "count": 5},
                                                                     {"band": "31-60 days", "amount": "15000.00", "count": 2}]},
        "verifications": {"pending_count": 3, "pending_amount": "15000.00", "overdue_count": 1, "oldest_at": "2026-10-01T09:00:00+05:30"},
        "followups": {"overdue_count": 5, "broken_promises": 2},
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------- BranchUpserted

def test_a_new_crm_branch_is_created_from_the_crms_own_columns(client, catalog, crm_event):
    response = crm_event("BranchUpserted", NEW_BRANCH)

    assert response.status_code == 201, response.get_json()
    assert response.get_json()["data"]["result"]["created"] is True
    assert _branch("NIT-TEN") == {"branch_name": "Tenali", "short_code": "TEN", "mailbox": "tenali@example.test",
                                  "is_active": True, "source_version": 1}
    # an admission can now be served there, and a person's own email is still the person's
    qualified = crm_event("AdmissionQualified", helpers.admission_data(service="NIT-TEN", email="ravi@example.test"))
    assert qualified.status_code == 201, qualified.get_json()
    assert db.session.execute(text("SELECT email FROM students")).scalar_one() == "ravi@example.test"


def test_an_existing_branch_is_updated_and_keeps_its_short_code(client, crm_event):
    renamed = crm_event("BranchUpserted", {"branch_code": "NIT-GNT", "branch_name": "Guntur Main", "city": "Guntur",
                                           "receipt_prefix": "GNT", "email": None, "is_active": True}, source_version=2)
    assert renamed.status_code == 201, renamed.get_json()
    assert renamed.get_json()["data"]["result"]["created"] is False
    gnt = _branch("NIT-GNT")
    assert (gnt["branch_name"], gnt["short_code"], gnt["source_version"]) == ("Guntur Main", "GNT", 2)
    assert gnt["mailbox"]  # null keeps the LMS's mailbox

    moved = crm_event("BranchUpserted", {**NEW_BRANCH, "branch_code": "NIT-GNT", "receipt_prefix": "GTR"}, source_version=3)
    assert moved.status_code == 422 and "keeps short code GNT" in moved.get_json()["error"]["message"]

    stale = crm_event("BranchUpserted", {"branch_code": "NIT-GNT", "branch_name": "Old", "city": "Guntur"}, source_version=1,
                      event_id="evt-old")
    assert stale.get_json()["data"]["status"] == "Ignored — stale" and _branch("NIT-GNT")["branch_name"] == "Guntur Main"


def test_a_new_branch_needs_a_short_code_and_mailbox_that_are_free(client, crm_event):
    missing = crm_event("BranchUpserted", {"branch_code": "NIT-TEN", "branch_name": "Tenali", "city": "Tenali"})
    assert missing.status_code == 422 and "needs short_code and mailbox" in missing.get_json()["error"]["message"]

    taken = crm_event("BranchUpserted", {**NEW_BRANCH, "receipt_prefix": "GNT"})
    assert taken.status_code == 422 and "already used" in taken.get_json()["error"]["message"]
    assert _branch("NIT-TEN") is None


def test_a_branch_can_be_deactivated(client, crm_event):
    assert crm_event("BranchUpserted", NEW_BRANCH).status_code == 201
    assert crm_event("BranchUpserted", {**NEW_BRANCH, "is_active": False}, source_version=2).status_code == 201
    assert _branch("NIT-TEN")["is_active"] is False


# ---------------------------------------------------------------- BranchFinanceSnapshot

def test_a_snapshot_replaces_the_previous_one_and_older_ones_are_ignored(client, crm_event):
    assert crm_event("BranchFinanceSnapshot", snapshot()).status_code == 201
    newer = snapshot(collections={"verified": "130000.00", "target": "500000.00"})
    assert crm_event("BranchFinanceSnapshot", newer, source_version=3).status_code == 201
    older = crm_event("BranchFinanceSnapshot", snapshot(), source_version=2)

    assert older.get_json()["data"]["status"] == "Ignored — stale"
    row = db.session.execute(text("SELECT collections_verified, source_version, overdue_by_age_band FROM branch_finance_snapshots")).one()
    assert (str(row[0]), row[1]) == ("130000.00", 3)
    assert row[2][0] == {"band": "1-30 days", "amount": "30000.00", "count": 5}


def test_a_snapshot_needs_a_known_branch_and_a_period_for_its_targets(client, crm_event):
    unknown = crm_event("BranchFinanceSnapshot", snapshot("NIT-XYZ"))
    assert unknown.status_code == 422 and "Unknown branch" in unknown.get_json()["error"]["message"]

    no_period = crm_event("BranchFinanceSnapshot", snapshot(period=False))
    assert no_period.status_code == 422 and "needs its period" in no_period.get_json()["error"]["message"]

    untargeted = snapshot(period=False, collections={"verified": "0.00", "target": None}, paid_admissions={"count": 0, "target": None})
    assert crm_event("BranchFinanceSnapshot", untargeted).status_code == 201

    invalid = crm_event("BranchFinanceSnapshot", {**snapshot(), "followups": {"overdue_count": -1}})
    assert invalid.status_code == 400 and "followups" in invalid.get_json()["error"]["details"]


# ---------------------------------------------------------------- dashboards

def _crm(client, login, who, path) -> dict:
    response = client.get(f"{API}{path}", headers=auth(login, who))
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]["crm"]


def test_branch_dashboard_shows_the_branchs_snapshot(client, login, world, crm_event):
    crm_event("BranchFinanceSnapshot", snapshot("NIT-GNT"))
    crm_event("BranchFinanceSnapshot", snapshot("NIT-VIJ", collections={"verified": "1.00", "target": "2.00"}))

    crm = _crm(client, login, world.people.bm_g, "/branch/summary")

    collections = crm["verified_collections"]
    assert (collections["state"], collections["value"], collections["target"], collections["unit"]) == \
        ("Configured", "120000.00", "500000.00", "INR")  # Guntur only: the manager's branch
    assert collections["period"] == {"label": "Oct 2026", "start": "2026-10-01", "end": "2026-10-31"}
    assert collections["stale"] is False and collections["missing_branches"] == []
    assert (crm["new_paid_admissions"]["value"], crm["new_paid_admissions"]["target"]) == (12, 40)
    assert crm["overdue_followups"]["value"] == 7
    assert crm["overdue_followups"]["detail"] == {"followups_overdue": 5, "broken_promises": 2}


def test_company_wide_figures_sum_the_branches_and_name_the_missing_ones(client, login, world, crm_event):
    crm_event("BranchFinanceSnapshot", snapshot("NIT-GNT"))

    partial = _crm(client, login, world.people.founder, "/founder/summary")
    assert partial["overdue_amount"]["state"] == "Partial Data"
    assert [b["branch_code"] for b in partial["overdue_amount"]["missing_branches"]] == ["NIT-VIJ"]
    assert partial["verified_collections"]["target"] == "500000.00"

    crm_event("BranchFinanceSnapshot", snapshot("NIT-VIJ", collections={"verified": "80000.00", "target": None}, period=False,
                                                paid_admissions={"count": 3, "target": None}))
    full = _crm(client, login, world.people.founder, "/founder/summary")
    assert full["overdue_amount"]["state"] == "Configured"
    assert full["overdue_amount"]["value"] == "90000.00"
    assert full["overdue_amount"]["detail"]["by_age_band"] == [{"band": "1-30 days", "amount": "60000.00", "count": 10},
                                                               {"band": "31-60 days", "amount": "30000.00", "count": 4}]
    collections = full["verified_collections"]
    assert collections["value"] == "200000.00" and collections["target"] is None and collections["period"] is None  # a partial target is no target

    verifications = _crm(client, login, world.people.sa, "/admin/summary")["overdue_payment_verifications"]
    assert (verifications["value"], verifications["detail"]["pending_count"], verifications["detail"]["pending_amount"]) == (2, 6, "30000.00")


def test_an_old_snapshot_is_flagged_stale(client, login, world, crm_event):
    crm_event("BranchFinanceSnapshot", snapshot("NIT-GNT", as_of=datetime.now(timezone.utc) - timedelta(hours=3)))

    assert _crm(client, login, world.people.bm_g, "/branch/summary")["verified_collections"]["stale"] is True
