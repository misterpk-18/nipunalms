"""Builders for CRM event payloads and small assertions shared by the tests."""

# label, course code, track code (None = the course as a whole) — an Active version for each
CURRICULA = [
    ("Parent Programme v2026.1", "NIT-CRS-018", None),
    ("Track CV 3.2", "NIT-CRS-018", "NIT-CRS-018/T1"),
    ("Track CV 2.4", "NIT-CRS-018", "NIT-CRS-018/T2"),
    ("Track CV 1.1", "NIT-CRS-018", "NIT-CRS-018/T3"),
    ("CV 1.3", "NIT-CRS-019", None),
    ("CV 5.1", "NIT-CRS-047", None),
]


def catalog_courses() -> list[dict]:
    """CourseUpserted payloads, in an order that satisfies references (the booster course first)."""
    return [
        {"course_code": "NIT-CRS-019", "title": "Microsoft Power BI Data Analytics", "category": "Data & Analytics"},
        {"course_code": "NIT-CRS-047", "title": "Java Full Stack Developer", "category": "Software Development"},
        {"course_code": "NIT-CRS-052", "title": "Python Full Stack Developer", "category": "Software Development"},
        {
            "course_code": "NIT-CRS-018", "title": "Data Science with Python, SQL, Machine Learning & Applied AI",
            "category": "Data & Analytics", "is_combo": True,
            "components": [
                {"track_code": "NIT-CRS-018/T1", "track_name": "Python & SQL Foundations", "sort_order": 1},
                {"track_code": "NIT-CRS-018/T2", "track_name": "Machine Learning", "sort_order": 2},
                {"track_code": "NIT-CRS-018/T3", "track_name": "Applied AI", "sort_order": 3},
                {"track_code": "NIT-CRS-019", "track_name": "Microsoft Power BI Data Analytics", "role": "Included booster",
                 "sort_order": 4, "component_course_code": "NIT-CRS-019"},
            ],
        },
    ]


def admission_data(*, person_id="P-100", admission_id="A-100", name="Anvitha K.", email="anvitha.sample@example.test",
                   course="NIT-CRS-047", enrolments=None, service="NIT-GNT", collecting="NIT-GNT", original="NIT-GNT",
                   **person_extra) -> dict:
    """AdmissionQualified data. Default: one standalone Java Full Stack enrolment at Guntur."""
    return {
        "person": {"crm_person_id": person_id, "full_name": name, "email": email, "mobile": "9876543210", **person_extra},
        "admission": {
            "crm_admission_id": admission_id, "admission_code": f"ADM-GNT-2026-{admission_id[-3:].zfill(6)}",
            "course_code": course, "original_branch_code": original, "service_branch_code": service,
            "collecting_branch_code": collecting, "mode": "Classroom", "admission_date": "2026-09-28",
        },
        "enrolments": enrolments if enrolments is not None else [{"course_code": course}],
    }


def combo_admission_data(**kwargs) -> dict:
    """The prototype combo: 018 with its four tracks, plus a complimentary Python Full Stack (NIT-CRS-052)."""
    return admission_data(
        course="NIT-CRS-018",
        enrolments=[
            {"course_code": "NIT-CRS-018", "kind": "Combo"},
            {"course_code": "NIT-CRS-052", "kind": "Complimentary", "parent_course_code": "NIT-CRS-018",
             "benefit_gate": {"met": True, "note": "Promotional offer, qualifying payment verified"}},
        ],
        **kwargs,
    )


def finance_data(crm_admission_id="A-100", **overrides) -> dict:
    data = {
        "crm_admission_id": crm_admission_id, "fee_total": 30000, "verified_paid": "10000.00", "balance": 20000,
        "next_due_date": "2026-10-15", "next_due_amount": 10000,
        "receipts": [{"receipt_number": "GNT-R-2627-00001", "date": "2026-09-28", "amount": 10000}],
    }
    return {**data, **overrides}
