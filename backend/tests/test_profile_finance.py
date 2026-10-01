"""Profile (identity, language, devices) and the read-only Fees & Receipts."""
from repositories import students as students_repo
from tests import helpers
from tests.services_fixtures import world  # noqa: F401

API = "/api/v1"
EDGE = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36 Edg/120.0"
ANDROID = "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"


class TestProfile:
    def test_a_student_sees_identity_with_the_mobile_masked(self, client, world):
        data = client.get(f"{API}/me/profile", headers=world.h(world.students.s1)).get_json()["data"]
        student = data["student"]
        assert student["student_code"] == world.students.s1.student_code and student["full_name"] == "Student One"
        assert student["mobile_masked"] == "+91 ●●●●●●0417" and "not identity proof" in student["mobile_note"]
        assert "9876500417" not in str(data)
        assert student["original_branch"]["branch_code"] == "NIT-GNT" and student["mfa_status"] == "Not Configured"
        assert student["recovery"]["email_on_file"] is True and student["activation_status"] == "Activated"
        assert data["user"]["student_id"] == world.students.s1.student_id

    def test_language_is_stored_on_the_student(self, client, world):
        h = world.h(world.students.s1)
        assert client.patch(f"{API}/me/profile", headers=h, json={"preferred_language": "te"}).get_json()["data"]["student"]["preferred_language"] == "te"
        assert students_repo.get_student(world.students.s1.student_id).preferred_language == "te"
        assert client.patch(f"{API}/me/profile", headers=h, json={"preferred_language": "fr"}).status_code == 400
        assert client.patch(f"{API}/me/profile", headers=world.h(world.people.t1), json={"preferred_language": "te"}).status_code == 403

    def test_staff_get_a_profile_too(self, client, world):
        data = client.get(f"{API}/me/profile", headers=world.h(world.people.t1)).get_json()["data"]
        assert data["student"] is None and data["scopes"][0]["role_code"] == "TRAINER" and data["user"]["full_name"] == "Trainer One"

    def test_devices_are_labelled_and_other_sessions_can_be_signed_out(self, client, world):
        student = world.students.s1
        for agent in (EDGE, ANDROID):
            assert client.post(f"{API}/auth/login", json={"login": student.student_code, "password": "Correct-horse-1"},
                               headers={"User-Agent": agent}).status_code == 200
        token = client.post(f"{API}/auth/login", json={"login": student.student_code, "password": "Correct-horse-1"},
                            headers={"User-Agent": ANDROID}).get_json()["data"]["token"]
        headers = {"Authorization": f"Bearer {token}", "User-Agent": ANDROID}
        devices = client.get(f"{API}/me/profile", headers=headers).get_json()["data"]["devices"]
        assert sorted(d["label"] for d in devices) == ["Chrome · Android", "Chrome · Android", "Edge · Windows"]
        assert [d["current"] for d in devices].count(True) == 1

        assert client.post(f"{API}/me/devices/sign-out-others", headers=headers).get_json()["data"]["signed_out"] == 2
        after = client.get(f"{API}/me/profile", headers=headers).get_json()["data"]["devices"]
        assert len(after) == 1 and after[0]["current"] is True

    def test_login_is_required(self, client):
        assert client.get(f"{API}/me/profile").status_code == 401


class TestFinance:
    def send(self, crm_event, world, admission="A-1", **overrides):
        return crm_event("FinanceSummaryUpdated", helpers.finance_data(admission, **overrides), source_version=2)

    def test_a_student_sees_only_their_own_summary_read_only(self, client, world, crm_event):
        assert self.send(crm_event, world, "A-1").status_code in (200, 201)
        assert self.send(crm_event, world, "A-2", fee_total=50000, verified_paid="0.00", balance=50000, receipts=[]).status_code in (200, 201)
        data = client.get(f"{API}/me/finance", headers=world.h(world.students.s1)).get_json()["data"]
        assert data["source"].startswith("CRM") and "not a receipt" in data["note"]
        [entry] = data["admissions"]
        assert entry["summary"]["fee_total"] == "30000.00" and entry["summary"]["verified_paid"] == "10000.00"
        assert entry["summary"]["balance"] == "20000.00" and entry["summary"]["installments_scope"] == "admission"
        assert entry["summary"]["receipts"][0]["receipt_number"] == "GNT-R-2627-00001" and entry["summary"]["as_of"]
        [schedule] = data["schedules"]  # an admission's own schedule
        assert schedule["schedule_key"] == entry["schedule_key"] and schedule["next_due_date"] == "2026-10-15"
        assert client.put(f"{API}/me/finance", headers=world.h(world.students.s1), json={}).status_code == 405

    def test_a_shared_invoice_schedule_is_shown_and_summed_once(self, client, world, crm_event):
        """F3: two courses on one CRM invoice: each summary carries the invoice's schedule; it counts once."""
        second = helpers.admission_data(person_id="P-1", admission_id="A-1B", course="NIT-CRS-019", name="Student One",
                                        email="student1@example.test")
        assert crm_event("AdmissionQualified", second).status_code == 201
        installments = [{"installment_no": 1, "due_date": "2026-09-15", "amount": 26000, "covered": 20000, "balance": 6000,
                         "due_position": "Overdue"},
                        {"installment_no": 2, "due_date": "2026-10-15", "amount": 26000, "covered": 0, "balance": 26000,
                         "due_position": "Upcoming"}]
        shared = dict(invoice_numbers=["INV-GNT-2627-0005"], installments_scope="invoice", invoice_course_count=2,
                      installments=installments, next_due_date="2026-09-15", next_due_amount=6000)
        assert self.send(crm_event, world, "A-1", **shared).status_code == 201
        assert self.send(crm_event, world, "A-1B", fee_total=22000, verified_paid=10000, balance=12000, receipts=[], **shared).status_code == 201

        data = client.get(f"{API}/me/finance", headers=world.h(world.students.s1)).get_json()["data"]
        assert sorted(e["summary"]["balance"] for e in data["admissions"]) == ["12000.00", "20000.00"]  # per course
        assert all("installments" not in e["summary"] and "next_due_amount" not in e["summary"] for e in data["admissions"])
        [schedule] = data["schedules"]
        assert schedule["invoice_number"] == "INV-GNT-2627-0005" and schedule["installments_scope"] == "invoice"
        assert schedule["invoice_course_count"] == 2 and len(schedule["installments"]) == 2
        assert sorted(a["course"]["course_code"] for a in schedule["admissions"]) == ["NIT-CRS-019", "NIT-CRS-047"]
        assert (schedule["next_due_amount"], schedule["overdue_amount"]) == ("6000.00", "6000.00")

        listed = client.get(f"{API}/finance-summaries", headers=world.h(world.people.bm),
                            query_string={"student_id": world.students.s1.student_id}).get_json()
        assert listed["meta"]["totals"] == {"admissions": 2, "balance": "32000.00", "schedules": 1,
                                            "overdue_amount": "6000.00", "next_due_amount": "6000.00"}
        assert len({r["schedule_key"] for r in listed["data"]}) == 1

        detail = client.get(f"{API}/finance-summaries/{world.students.s1.admission_id}", headers=world.h(world.people.bm)).get_json()["data"]
        assert detail["schedule"]["invoice_number"] == "INV-GNT-2627-0005" and len(detail["schedule"]["admissions"]) == 2

    def test_the_installments_scope_is_validated(self, world, crm_event):
        assert self.send(crm_event, world, "A-1", installments_scope="course").status_code == 400
        assert self.send(crm_event, world, "A-1", invoice_course_count=-1).status_code == 400

    def test_an_admission_without_a_summary_is_listed_as_not_received(self, client, world):
        [entry] = client.get(f"{API}/me/finance", headers=world.h(world.students.s1)).get_json()["data"]["admissions"]
        assert entry["summary"] is None

    def test_the_branch_manager_reads_their_branch_only(self, client, world, crm_event):
        self.send(crm_event, world, "A-1")
        self.send(crm_event, world, "A-2")
        self.send(crm_event, world, "A-VIJ")
        codes = lambda p: sorted(r["admission"]["crm_admission_id"] for r in client.get(f"{API}/finance-summaries", headers=world.h(p)).get_json()["data"])
        assert codes(world.people.bm) == ["A-1", "A-2", "A-VIJ"]           # A-VIJ is serviced at Vijayawada but collected at Guntur
        assert codes(world.people.bm_vij) == ["A-VIJ"]
        assert codes(world.people.admin) == ["A-1", "A-2", "A-VIJ"]
        admission_id = world.students.s1.admission_id
        assert client.get(f"{API}/finance-summaries/{admission_id}", headers=world.h(world.people.bm)).status_code == 200
        assert client.get(f"{API}/finance-summaries/{admission_id}", headers=world.h(world.people.bm_vij)).status_code == 404

    def test_other_roles_have_no_finance_access(self, client, world):
        for person in (world.people.ac, world.people.t1, world.students.s1):
            assert client.get(f"{API}/finance-summaries", headers=world.h(person)).status_code == 403
        assert client.get(f"{API}/me/finance", headers=world.h(world.people.bm)).status_code == 403
