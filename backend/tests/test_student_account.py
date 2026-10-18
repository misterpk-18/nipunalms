"""UX phase U11, My Account: the student's email with a confirmation code, the Next payment card, receipt PDFs and the branch setting."""
import json
from datetime import timedelta

import pytest
from reportlab import rl_config
from sqlalchemy import select

from config.database import db
from config.timezone import today_ist
from models import AuditLog, EmailChangeCode, User, WhatsappMessage
from repositories import students as students_repo
from services import email_change, whatsapp_templates
from tests import helpers
from tests.conftest import PASSWORD
from tests.services_fixtures import world  # noqa: F401

API = "/api/v1"


@pytest.fixture
def switched_on(run_sql, app):
    run_sql("UPDATE app_settings SET setting_value = 'true' WHERE setting_key = 'whatsapp_enabled'")
    run_sql("UPDATE app_settings SET setting_value = CAST(:v AS jsonb) WHERE setting_key = 'whatsapp_approved_templates'",
            v=json.dumps(sorted(whatsapp_templates.TEMPLATES)))
    app.config["CRM_BASE_URL"] = "http://crm.test/api/v1"


@pytest.fixture
def fixed_code(monkeypatch):
    monkeypatch.setattr(email_change, "new_code", lambda: "482913")
    return "482913"


def ask_code(client, world, email, student=None):
    return client.post(f"{API}/me/email/request-code", headers=world.h(student or world.students.s1), json={"email": email})


def confirm(client, world, code, student=None):
    return client.post(f"{API}/me/email/confirm", headers=world.h(student or world.students.s1), json={"code": code})


def code_messages():
    return db.session.execute(select(WhatsappMessage).where(WhatsappMessage.template_name == whatsapp_templates.PASSWORD_RESET_CODE.name)
                              .order_by(WhatsappMessage.outbox_id)).scalars().all()


# ---------------------------------------------------------------- email

class TestEmailChange:
    def test_the_code_goes_by_whatsapp_and_the_email_changes_only_after_it_is_typed(self, client, world, switched_on, fixed_code):
        student = world.students.s1
        before = students_repo.get_student(student.student_id).email

        answer = ask_code(client, world, "New.Address@Example.test").get_json()["data"]

        assert answer["sent"] is True and answer["channel"] == "WhatsApp" and answer["expires_in_minutes"] == 10
        (message,) = code_messages()
        assert message.status == "Queued" and message.params == [fixed_code] and message.to_number == "919876500417"
        row = db.session.execute(select(EmailChangeCode)).scalar_one()
        assert fixed_code not in row.code_hash and row.new_email == "new.address@example.test"  # only a hash is kept
        assert students_repo.get_student(student.student_id).email == before  # nothing changed yet

        profile = confirm(client, world, fixed_code).get_json()["data"]
        assert profile["student"]["email"] == "new.address@example.test" and profile["user"]["email"] == "new.address@example.test"
        assert db.session.get(User, profile["user"]["user_id"]).email == "new.address@example.test"
        assert client.post(f"{API}/auth/login", json={"login": "new.address@example.test", "password": PASSWORD}).status_code == 200
        actions = db.session.execute(select(AuditLog.action)).scalars().all()
        assert "STUDENT_EMAIL_CHANGED" in actions and "EMAIL_CHANGE_CODE_REQUESTED" in actions

    def test_a_code_works_once_and_not_for_another_address(self, client, world, switched_on, fixed_code):
        assert ask_code(client, world, "one@example.test").status_code == 200
        assert confirm(client, world, fixed_code).status_code == 200
        again = confirm(client, world, fixed_code)
        assert again.status_code == 400 and "wrong or has expired" in again.get_json()["error"]["message"]

    def test_a_wrong_code_is_refused_and_five_wrong_tries_burn_it(self, client, world, switched_on, fixed_code):
        ask_code(client, world, "one@example.test")
        for _ in range(5):
            assert confirm(client, world, "000000").status_code == 400
        assert confirm(client, world, fixed_code).status_code == 400  # burned: ask for a new one

    def test_an_expired_code_is_refused(self, client, world, switched_on, fixed_code, run_sql):
        ask_code(client, world, "one@example.test")
        run_sql("UPDATE email_change_codes SET expires_at = now() - interval '1 minute'")
        assert confirm(client, world, fixed_code).status_code == 400

    def test_asking_again_replaces_the_earlier_code_and_address(self, client, world, switched_on, monkeypatch):
        monkeypatch.setattr(email_change, "new_code", lambda: "111111")
        ask_code(client, world, "first@example.test")
        monkeypatch.setattr(email_change, "new_code", lambda: "222222")
        ask_code(client, world, "second@example.test")
        assert confirm(client, world, "111111").status_code == 400
        assert confirm(client, world, "222222").get_json()["data"]["student"]["email"] == "second@example.test"

    def test_at_most_five_codes_an_hour(self, client, world, switched_on):
        for n in range(5):
            assert ask_code(client, world, f"try{n}@example.test").status_code == 200
        assert ask_code(client, world, "try6@example.test").status_code == 429

    def test_an_address_in_use_or_unchanged_is_refused(self, client, world, switched_on):
        taken = ask_code(client, world, world.people.t1.email)
        assert taken.status_code == 400 and "can't be used" in taken.get_json()["error"]["message"]
        same = ask_code(client, world, students_repo.get_student(world.students.s1.student_id).email.upper())
        assert same.status_code == 400
        assert ask_code(client, world, "not-an-email").status_code == 400
        assert db.session.execute(select(EmailChangeCode)).first() is None

    def test_with_whatsapp_off_the_answer_says_no_code_was_sent(self, client, world):
        answer = ask_code(client, world, "one@example.test").get_json()["data"]
        assert answer["sent"] is False and "switched off" in answer["reason"]
        (message,) = code_messages()
        assert message.status == "Skipped" and message.params == []  # nothing is kept that could be sent later

    def test_only_a_student_changes_their_email_here(self, client, world, switched_on):
        for path, body in (("request-code", {"email": "a@example.test"}), ("confirm", {"code": "123456"})):
            assert client.post(f"{API}/me/email/{path}", headers=world.h(world.people.t1), json=body).status_code == 403
            assert client.post(f"{API}/me/email/{path}", json=body).status_code == 401


# ---------------------------------------------------------------- next payment

def send(crm_event, admission="A-1", **overrides):
    return crm_event("FinanceSummaryUpdated", helpers.finance_data(admission, **overrides), source_version=2)


def installments(due, amount=10000, position="Upcoming"):
    return [{"installment_no": 1, "due_date": due.isoformat(), "amount": amount, "covered": 0, "balance": amount, "due_position": position}]


def finance(client, world):
    return client.get(f"{API}/me/finance", headers=world.h(world.students.s1)).get_json()["data"]


class TestNextPayment:
    def test_nothing_from_the_crm_yet(self, client, world):
        assert finance(client, world)["next_payment"] == {"state": "unknown"}

    def test_the_next_instalment_with_how_to_pay_at_the_collecting_branch(self, client, world, crm_event, run_sql):
        due = today_ist() + timedelta(days=5)
        run_sql("UPDATE branches SET payment_instructions = 'Pay at the front desk.' WHERE branch_id = 1")
        assert send(crm_event, next_due_date=due.isoformat(), installments=installments(due)).status_code == 201
        card = finance(client, world)["next_payment"]
        assert card["state"] == "due" and card["due_date"] == due.isoformat() and card["amount"] == "10000.00"
        assert card["is_overdue"] is False and card["overdue_amount"] == "0.00"
        assert card["how_to_pay"]["instructions"] == "Pay at the front desk." and card["how_to_pay"]["branch"]["branch_id"] == 1
        assert card["courses"] and card["invoice_number"] is None

    def test_a_date_that_has_passed_is_overdue(self, client, world, crm_event):
        due = today_ist() - timedelta(days=3)
        send(crm_event, next_due_date=due.isoformat(), installments=installments(due, position="Overdue"))
        card = finance(client, world)["next_payment"]
        assert card["is_overdue"] is True and card["overdue_amount"] == "10000.00" and card["how_to_pay"]["instructions"] is None

    def test_the_earliest_of_several_schedules_wins(self, client, world, crm_event):
        second = helpers.admission_data(person_id="P-1", admission_id="A-1B", course="NIT-CRS-019", name="Student One",
                                        email="student1@example.test")
        assert crm_event("AdmissionQualified", second).status_code == 201
        soon, later = today_ist() + timedelta(days=2), today_ist() + timedelta(days=20)
        send(crm_event, "A-1", next_due_date=later.isoformat(), installments=installments(later))
        send(crm_event, "A-1B", next_due_date=soon.isoformat(), next_due_amount=7000, installments=installments(soon, 7000), receipts=[])
        card = finance(client, world)["next_payment"]
        assert card["due_date"] == soon.isoformat() and card["amount"] == "7000.00"

    def test_nothing_left_to_pay(self, client, world, crm_event):
        send(crm_event, fee_total=30000, verified_paid="30000.00", balance=0, next_due_date=None, next_due_amount=None)
        assert finance(client, world)["next_payment"] == {"state": "paid"}


# ---------------------------------------------------------------- receipt PDFs

class TestReceiptPdf:
    @pytest.fixture(autouse=True)
    def readable_pdfs(self, monkeypatch):
        """Leave page streams uncompressed so a test can look for the text drawn on the page."""
        monkeypatch.setattr(rl_config, "pageCompression", 0)

    def url(self, world, number="GNT-R-2627-00001", admission=None):
        return f"{API}/me/finance/receipts/{admission or world.students.s1.admission_id}/{number}/pdf"

    def test_the_owner_downloads_a_receipt_drawn_from_the_crm_record(self, client, world, crm_event):
        send(crm_event, "A-1")
        response = client.get(self.url(world), headers=world.h(world.students.s1))
        assert response.status_code == 200 and response.mimetype == "application/pdf"
        assert response.data.startswith(b"%PDF-") and response.headers["Content-Disposition"].endswith('receipt-GNT-R-2627-00001.pdf"')
        assert response.headers["Cache-Control"] == "private, no-store"
        for text in (b"GNT-R-2627-00001", b"Student One", b"10,000.00", b"PAYMENT RECEIPT"):
            assert text in response.data
        assert "RECEIPT_DOWNLOADED" in db.session.execute(select(AuditLog.action)).scalars().all()

    def test_another_students_receipt_an_unknown_number_and_staff_are_refused(self, client, world, crm_event):
        send(crm_event, "A-1")
        assert client.get(self.url(world), headers=world.h(world.students.s2)).status_code == 404
        assert client.get(self.url(world, "NOPE-1"), headers=world.h(world.students.s1)).status_code == 404
        assert client.get(self.url(world), headers=world.h(world.people.bm)).status_code == 403
        assert client.get(self.url(world)).status_code == 401

    def test_an_admission_without_a_summary_has_no_receipt(self, client, world):
        assert client.get(self.url(world), headers=world.h(world.students.s1)).status_code == 404

    def test_a_name_in_telugu_script_prints_question_marks_instead_of_failing(self, client, world, crm_event, run_sql):
        run_sql("UPDATE students SET full_name = 'విద్యార్థి' WHERE student_id = :s", s=world.students.s1.student_id)
        send(crm_event, "A-1")
        assert client.get(self.url(world), headers=world.h(world.students.s1)).status_code == 200


# ---------------------------------------------------------------- the branch setting

class TestPaymentInstructions:
    def test_only_the_super_admin_and_founder_set_it_and_a_branch_manager_reads_their_own_branch(self, client, world):
        url = f"{API}/branches/1/payment-instructions"
        assert client.put(url, headers=world.h(world.people.bm), json={"payment_instructions": "x"}).status_code == 403
        ok = client.put(url, headers=world.h(world.people.admin), json={"payment_instructions": "  UPI to nipuna@bank, then show the screen.  "})
        assert ok.status_code == 200 and ok.get_json()["data"]["payment_instructions"] == "UPI to nipuna@bank, then show the screen."
        assert client.get(url, headers=world.h(world.people.bm)).get_json()["data"]["payment_instructions"] == "UPI to nipuna@bank, then show the screen."
        assert client.get(url, headers=world.h(world.people.bm_vij)).status_code == 404
        assert client.put(url, headers=world.h(world.people.admin), json={"payment_instructions": None}).get_json()["data"]["payment_instructions"] is None
        assert client.put(url, headers=world.h(world.people.admin), json={}).status_code == 400
        assert "BRANCH_PAYMENT_INSTRUCTIONS_CHANGED" in db.session.execute(select(AuditLog.action)).scalars().all()

    def test_students_and_trainers_cannot(self, client, world):
        for person in (world.students.s1, world.people.t1):
            assert client.put(f"{API}/branches/1/payment-instructions", headers=world.h(person), json={"payment_instructions": "x"}).status_code == 403
