"""CRM event payloads are kept for a year, then emptied: the person's name, phone and email go, the record of the event stays."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from config.database import db
from models import CrmEvent
from services import crm as crm_service
from services.jobs import JOBS
from tests import helpers

EVENTS = "/api/v1/integrations/crm/events"


def age(event_id: str, days: int) -> None:
    db.session.execute(update(CrmEvent).where(CrmEvent.event_id == event_id).values(received_at=datetime.now(timezone.utc) - timedelta(days=days)))
    db.session.commit()


def event(event_id: str) -> CrmEvent:
    db.session.expire_all()
    return db.session.execute(select(CrmEvent).where(CrmEvent.event_id == event_id)).scalar_one()


def test_a_year_old_applied_event_loses_its_payload_and_keeps_its_record(catalog, crm_event):
    assert crm_event("AdmissionQualified", helpers.admission_data(), event_id="evt-old").status_code == 201
    assert crm_event("AdmissionQualified", helpers.admission_data(person_id="P-2", admission_id="A-2"), event_id="evt-new").status_code == 201
    age("evt-old", 400)
    before = event("evt-old")
    assert before.payload["person"]["full_name"] and before.status == "Applied"

    assert crm_service.purge_old_payloads() == {"payloads_emptied": 1}
    old, new = event("evt-old"), event("evt-new")
    assert old.payload == {} and old.status == "Applied" and old.result == before.result and old.source_version == before.source_version
    assert new.payload["person"]["full_name"]  # a recent event is untouched
    assert crm_service.purge_old_payloads() == {"payloads_emptied": 0}  # nothing more to do


def test_a_failed_event_keeps_its_payload_because_a_retry_needs_it(catalog, crm_event):
    data = helpers.admission_data(course="NIT-CRS-501", enrolments=[{"course_code": "NIT-CRS-501"}])  # its course has not arrived
    assert crm_event("AdmissionQualified", data, event_id="evt-failed").status_code == 422
    age("evt-failed", 400)
    assert crm_service.purge_old_payloads() == {"payloads_emptied": 0}
    assert event("evt-failed").status == "Failed" and event("evt-failed").payload["admission"]["crm_admission_id"] == "A-100"


def test_the_event_list_still_works_and_a_year_old_resend_is_refused(catalog, crm_event, client, make_user, login):
    admin = login(make_user(roles=[("SUPER_ADMIN", None)]).email)
    assert crm_event("AdmissionQualified", helpers.admission_data(), event_id="evt-old").status_code == 201
    age("evt-old", 400)
    crm_service.purge_old_payloads()
    listed = client.get(EVENTS, headers=admin)
    assert listed.status_code == 200 and any(e["event_id"] == "evt-old" and e["payload"] == {} for e in listed.get_json()["data"])
    # the event id is still known, but with its payload gone a resend can no longer be told apart from a different event
    assert crm_event("AdmissionQualified", helpers.admission_data(), event_id="evt-old").status_code == 409


def test_the_purge_is_a_registered_job(catalog, crm_event):
    assert "crm-payload-purge" in JOBS
    assert crm_event("AdmissionQualified", helpers.admission_data(), event_id="evt-old").status_code == 201
    age("evt-old", 400)
    assert JOBS["crm-payload-purge"]() == {"payloads_emptied": 1}
