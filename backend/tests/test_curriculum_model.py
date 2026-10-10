"""Module 14 curriculum model: topic classes and fields, dependencies, verified hours and the completion profile, required
assessments, combo pins and equivalence, individual academic mappings and credits, variations and the
reusable library."""
import pytest
from sqlalchemy import select

from config.database import db
from models import Enrolment, EnrolmentTrack, ExceptionRecoveryStep, LearningCredit
from repositories import catalog as catalog_repo
from tests import helpers
from tests.test_delivery import PROFILE, call, complete_draft, data

API = "/api/v1"


@pytest.fixture
def people(make_user):
    return {
        "ac": make_user(roles=[("ACADEMIC_COORDINATOR", 1)], full_name="AC Guntur"),
        "ac2": make_user(roles=[("ACADEMIC_COORDINATOR", 1)], full_name="AC Guntur 2"),
        "bm": make_user(roles=[("BRANCH_MANAGER", 1)]),
        "t1": make_user(roles=[("TRAINER", 1)]),
        "admin": make_user(roles=[("SUPER_ADMIN", None)]),
        "founder": make_user(roles=[("FOUNDER_CEO", None)]),
    }


def course_id(code):
    return catalog_repo.get_course_by_code(code).course_id


def draft(client, login, who, code="NIT-CRS-052", label="CV 3.0", component_id=None, topics=("Syntax", "Loops")):
    vid = data(call(client, login, who, "post", "/curriculum-versions",
                    json={"course_id": course_id(code), "component_id": component_id, "version_label": label}), 201)["curriculum_version_id"]
    module_id = None
    if topics:
        module_id = data(call(client, login, who, "post", f"/curriculum-versions/{vid}/modules", json={"title": "Basics"}), 201)["module_id"]
        for title in topics:
            call(client, login, who, "post", f"/curriculum-modules/{module_id}/topics", json={"title": title})
    return vid, module_id


def publish(client, login, people, vid, *, fill=True):
    if fill:
        complete_draft(client, login, people["ac"], vid)
    data(call(client, login, people["ac"], "post", f"/curriculum-versions/{vid}/submit"), 200)
    data(call(client, login, people["founder"], "post", f"/curriculum-versions/{vid}/approve"), 200)
    return data(call(client, login, people["founder"], "post", f"/curriculum-versions/{vid}/activate"), 200)


# ---------------------------------------------------------------- topics, hours, profile

def test_a_version_is_submitted_only_when_its_required_learning_is_described(client, login, catalog, people):
    """Module 14 §5: verified outcomes, hours, evidence and weights, and a completion profile; missing rules never pass."""
    vid, module_id = draft(client, login, people["ac"])
    blockers = data(call(client, login, people["ac"], "get", f"/curriculum-versions/{vid}"), 200)["blockers"]
    assert any("without an outcome" in b for b in blockers) and any("Verify the standard instructional hours" in b for b in blockers)
    assert any("completion profile" in b for b in blockers)
    assert call(client, login, people["ac"], "post", f"/curriculum-versions/{vid}/submit").status_code == 422
    assert call(client, login, people["ac"], "post", f"/curriculum-versions/{vid}/hours-verification").status_code == 422  # no estimates yet

    complete_draft(client, login, people["ac"], vid)
    detail = data(call(client, login, people["ac"], "get", f"/curriculum-versions/{vid}"), 200)
    assert detail["blockers"] == [] and detail["totals"]["instructional_minutes"] == 180 and detail["totals"]["total_minutes"] == 240
    assert detail["totals"]["hours_verified"] is True and detail["completion_profile"]["pass_mark_pct"] == 50

    # Changing the teaching plan's minutes needs the hours verified again
    topic_id = detail["modules"][0]["topics"][0]["topic_id"]
    data(call(client, login, people["ac"], "patch", f"/curriculum-topics/{topic_id}", json={"instructional_minutes": 60}), 200)
    assert data(call(client, login, people["ac"], "get", f"/curriculum-versions/{vid}"), 200)["totals"]["hours_verified"] is False


def test_topic_classes_keep_recommended_and_optional_out_of_required_learning(client, login, catalog, people):
    vid, module_id = draft(client, login, people["ac"], topics=("Syntax",))
    added = data(call(client, login, people["ac"], "post", f"/curriculum-modules/{module_id}/topics",
                      json={"title": "Style guide", "topic_class": "Recommended"}), 201)
    assert (added["topic_class"], added["is_required"]) == ("Recommended", False)
    legacy = data(call(client, login, people["ac"], "post", f"/curriculum-modules/{module_id}/topics",
                       json={"title": "History", "is_required": False}), 201)
    assert legacy["topic_class"] == "Optional"
    changed = data(call(client, login, people["ac"], "patch", f"/curriculum-topics/{legacy['topic_id']}", json={"topic_class": "Required"}), 200)
    assert changed["is_required"] is True
    counts = data(call(client, login, people["ac"], "get", f"/curriculum-versions/{vid}"), 200)["counts"]
    assert counts["required_topics"] == 2


def test_dependencies_stay_inside_the_version_and_never_loop(client, login, catalog, people):
    vid, module_id = draft(client, login, people["ac"], topics=("A", "B", "C"))
    topics = data(call(client, login, people["ac"], "get", f"/curriculum-versions/{vid}"), 200)["modules"][0]["topics"]
    a, b, c = (t["topic_id"] for t in topics)
    assert data(call(client, login, people["ac"], "patch", f"/curriculum-topics/{b}", json={"depends_on": [a]}), 200)["depends_on"] == [a]
    data(call(client, login, people["ac"], "patch", f"/curriculum-topics/{c}", json={"depends_on": [b]}), 200)
    loop = call(client, login, people["ac"], "patch", f"/curriculum-topics/{a}", json={"depends_on": [c]})
    assert loop.status_code == 400 and "loop" in str(loop.get_json())
    other_vid, other_module = draft(client, login, people["ac"], code="NIT-CRS-047", label="CV 9.0", topics=("X",))
    foreign = data(call(client, login, people["ac"], "get", f"/curriculum-versions/{other_vid}"), 200)["modules"][0]["topics"][0]["topic_id"]
    assert call(client, login, people["ac"], "patch", f"/curriculum-topics/{a}", json={"depends_on": [foreign]}).status_code == 400


def test_required_assessments_belong_to_the_draft_and_are_copied(client, login, catalog, people):
    vid, module_id = draft(client, login, people["ac"])
    body = {"kind": "Assignment", "title": "Loops lab", "outcome": "Writes loops", "weight": 2, "pass_rule": "Accepted by the trainer",
            "module_id": module_id}
    requirement = data(call(client, login, people["ac"], "post", f"/curriculum-versions/{vid}/assessment-requirements", json=body), 201)
    assert call(client, login, people["t1"], "post", f"/curriculum-versions/{vid}/assessment-requirements", json=body).status_code == 403
    publish(client, login, people, vid)
    assert call(client, login, people["ac"], "delete", f"/assessment-requirements/{requirement['requirement_id']}").status_code == 422
    copy = data(call(client, login, people["ac"], "post", "/curriculum-versions",
                     json={"course_id": course_id("NIT-CRS-052"), "version_label": "CV 3.1", "copy_from_version_id": vid}), 201)
    detail = data(call(client, login, people["ac"], "get", f"/curriculum-versions/{copy['curriculum_version_id']}"), 200)
    assert [r["title"] for r in detail["assessment_requirements"]] == ["Loops lab"]
    assert detail["modules"][0]["topics"][0]["outcome"].startswith("Can apply") and detail["totals"]["hours_verified"] is False


# ---------------------------------------------------------------- combos

def test_a_combo_parent_pins_its_tracks_and_borrowing_needs_an_equivalence_review(client, login, catalog, people, run_sql):
    combo = catalog_repo.get_course_by_code("NIT-CRS-018")
    t1 = next(c for c in combo.components if c.track_code == "NIT-CRS-018/T1")
    booster = next(c for c in combo.components if c.role == "Included booster")
    vid, _ = draft(client, login, people["ac"], code="NIT-CRS-018", label="Parent Programme v2027.1", topics=())
    blockers = data(call(client, login, people["ac"], "get", f"/curriculum-versions/{vid}"), 200)["blockers"]
    assert any("Pin a version for every track" in b for b in blockers)
    versions = catalog.versions
    data(call(client, login, people["ac"], "put", f"/curriculum-versions/{vid}/components",
              json={"component_id": t1.component_id, "component_version_id": versions["Track CV 3.2"]}), 200)
    wrong = call(client, login, people["ac"], "put", f"/curriculum-versions/{vid}/components",
                 json={"component_id": t1.component_id, "component_version_id": versions["CV 5.1"]})
    assert wrong.status_code == 400                                                             # another course's version
    run_sql("UPDATE course_components SET equivalence_note = NULL, equivalence_reviewed_by = NULL, equivalence_reviewed_at = NULL "
            "WHERE component_id = :c", c=booster.component_id)
    refused = call(client, login, people["ac"], "put", f"/curriculum-versions/{vid}/components",
                   json={"component_id": booster.component_id, "component_version_id": versions["CV 1.3"]})
    assert refused.status_code == 422 and "equivalence" in refused.get_json()["error"]["message"]
    assert call(client, login, people["ac"], "post", f"/course-components/{booster.component_id}/equivalence", json={}).status_code == 400
    data(call(client, login, people["ac"], "post", f"/course-components/{booster.component_id}/equivalence",
              json={"note": "Same outcomes, scope, depth and assessment"}), 200)
    data(call(client, login, people["ac"], "put", f"/curriculum-versions/{vid}/components",
              json={"component_id": booster.component_id, "component_version_id": versions["CV 1.3"]}), 200)
    detail = data(call(client, login, people["ac"], "get", f"/curriculum-versions/{vid}"), 200)
    assert len(detail["components"]) == 2 and detail["totals"]["booster"]["track_code"] == "NIT-CRS-019"


def test_a_booster_without_an_equivalence_review_has_no_version_yet_but_is_allocatable(client, login, catalog, crm_event, people, run_sql):
    booster = catalog_repo.get_component_by_track_code("NIT-CRS-019")
    run_sql("UPDATE course_components SET equivalence_note = NULL, equivalence_reviewed_by = NULL, equivalence_reviewed_at = NULL "
            "WHERE component_id = :c", c=booster.component_id)
    crm_event("AdmissionQualified", helpers.combo_admission_data())
    combo = db.session.execute(select(Enrolment).where(Enrolment.kind == "Combo")).scalar_one()
    assert combo.status == "Allocation Pending"
    assert {t.component.track_code: t.curriculum_version_id is not None for t in combo.tracks}["NIT-CRS-019"] is False
    queue = client.get(f"{API}/exceptions", headers=login(people["ac"].email)).get_json()["data"]
    assert [r["source"] for r in queue if r["reference"] == combo.enrolment_code] == ["ALLOCATION"]


# ---------------------------------------------------------------- academic mappings and credit

def test_a_student_moves_versions_only_through_an_approved_mapping_with_credit(client, login, catalog, make_student, make_batch,
                                                                               people, run_sql):
    """Module 14 §8: comparison, migration plan, student acceptance, the receiving coordinator's independent approval; credit
    under an approved equivalence rule counts as covered learning, never as attendance."""
    student = make_student(course="NIT-CRS-047")
    enrolment_id = student.enrolments[0]["enrolment_id"]
    new_vid, _ = draft(client, login, people["ac"], code="NIT-CRS-047", label="CV 6.0", topics=("Streams", "Records"))
    publish(client, login, people, new_vid)                                                   # activation leaves running enrolments alone
    assert db.session.get(Enrolment, enrolment_id).curriculum_version_id == catalog.versions["CV 5.1"]

    batch = make_batch(1, course_code="NIT-CRS-047", trainers=[people["t1"]], state="Running", curriculum_version_id=new_vid)
    review = data(call(client, login, people["ac"], "get", f"/batches/{batch.batch_id}/allocation-review?enrolment_id={enrolment_id}"), 200)
    assert review["result"] == "Ready to allocate" and not any(c["key"] == "curriculum" for c in review["checks"])  # the version never blocks a seat

    streams = data(call(client, login, people["ac"], "get", f"/curriculum-versions/{new_vid}"), 200)["modules"][0]["topics"][0]["topic_id"]
    body = {"to_version_id": new_vid, "comparison": "Outcomes 1-4 met in CV 5.1; streams covered by the old lab; records remain",
            "migration_plan": "Join the CV 6.0 batch from Monday; records in week 2", "trainer_evidence": "Lab 3 accepted",
            "credits": [{"topic_id": streams, "original_evidence": "CV 5.1 lab 3, accepted 12 Sep"}]}
    no_rule = call(client, login, people["t1"], "post", f"/enrolments/{enrolment_id}/academic-mappings", json=body)
    assert no_rule.status_code == 422 and "equivalence rule" in no_rule.get_json()["error"]["message"]

    rule = data(call(client, login, people["ac"], "post", "/equivalence-rules",
                     json={"from_version_id": catalog.versions["CV 5.1"], "to_version_id": new_vid, "description": "Streams lab carries over"}), 201)
    assert call(client, login, people["ac"], "post", f"/equivalence-rules/{rule['rule_id']}/decision", json={"decision": "Approved"}).status_code == 403
    data(call(client, login, people["founder"], "post", f"/equivalence-rules/{rule['rule_id']}/decision", json={"decision": "Approved"}), 200)

    mapping = data(call(client, login, people["t1"], "post", f"/enrolments/{enrolment_id}/academic-mappings",
                        json={**body, "rule_id": rule["rule_id"]}), 201)
    assert call(client, login, people["t1"], "post", f"/enrolments/{enrolment_id}/academic-mappings",
                json={**body, "rule_id": rule["rule_id"]}).status_code == 409
    decide = f"/academic-mappings/{mapping['mapping_id']}/decision"
    assert call(client, login, people["t1"], "post", decide, json={"decision": "Approved"}).status_code == 403
    assert call(client, login, people["ac"], "post", decide, json={"decision": "Approved"}).status_code == 400   # acceptance needed
    approved = data(call(client, login, people["ac"], "post", decide,
                         json={"decision": "Approved", "student_acceptance": "Student agreed by phone on 3 Oct, logged in SR-1"}), 200)
    assert approved["status"] == "Approved" and len(approved["credits"]) == 1
    assert db.session.get(Enrolment, enrolment_id).curriculum_version_id == new_vid
    assert db.session.execute(select(LearningCredit.topic_id)).scalar_one() == streams
    progress = data(call(client, login, student.student_code, "get", f"/progress/enrolments/{enrolment_id}"), 200)
    assert progress["required_learning"]["covered_topics"] == 1 and progress["attendance"]["present"] == 0  # credit is not attendance
    data(call(client, login, people["ac"], "post", f"/batches/{batch.batch_id}/allocations", json={"enrolment_id": enrolment_id}), 201)
    assert db.session.get(Enrolment, enrolment_id).curriculum_version_id == new_vid


def test_the_preparer_never_approves_their_own_mapping(client, login, catalog, make_student, people):
    student = make_student(course="NIT-CRS-047")
    enrolment_id = student.enrolments[0]["enrolment_id"]
    new_vid, _ = draft(client, login, people["ac"], code="NIT-CRS-047", label="CV 6.0")
    publish(client, login, people, new_vid)
    mapping = data(call(client, login, people["ac"], "post", f"/enrolments/{enrolment_id}/academic-mappings",
                        json={"to_version_id": new_vid, "comparison": "c", "migration_plan": "p"}), 201)
    own = call(client, login, people["ac"], "post", f"/academic-mappings/{mapping['mapping_id']}/decision",
               json={"decision": "Approved", "student_acceptance": "In writing"})
    assert own.status_code == 422 and "independent" in own.get_json()["error"]["message"]
    assert call(client, login, people["ac2"], "post", f"/academic-mappings/{mapping['mapping_id']}/decision",
                json={"decision": "Approved", "student_acceptance": "In writing"}).status_code == 200


# ---------------------------------------------------------------- variations and library

def test_local_variations_are_recorded_and_a_required_topic_constraint_needs_central_approval(client, login, catalog, people):
    vid = catalog.versions["CV 5.1"]
    local = data(call(client, login, people["ac"], "post", "/curriculum-variations",
                      json={"curriculum_version_id": vid, "branch_id": 1, "kind": "Teaching language", "description": "Taught in Telugu"}), 201)
    assert local["status"] == "Approved"
    published, _ = draft(client, login, people["ac"], code="NIT-CRS-052", label="CV 3.0", topics=("Syntax",))
    result = publish(client, login, people, published)
    topic_id = data(call(client, login, people["ac"], "get", f"/curriculum-versions/{published}"), 200)["modules"][0]["topics"][0]["topic_id"]
    body = {"curriculum_version_id": published, "branch_id": 1, "kind": "Required topic constraint", "topic_id": topic_id,
            "description": "No lab machines until November"}
    assert call(client, login, people["ac"], "post", "/curriculum-variations", json=body).status_code == 400  # remedial plan needed
    constraint = data(call(client, login, people["ac"], "post", "/curriculum-variations",
                           json={**body, "remedial_plan": "Cloud lab accounts and two extra sessions"}), 201)
    assert constraint["status"] == "Pending" and result["status"] == "Active"
    assert call(client, login, people["ac2"], "post", f"/curriculum-variations/{constraint['variation_id']}/decision",
                json={"decision": "Approved"}).status_code == 403
    assert data(call(client, login, people["founder"], "post", f"/curriculum-variations/{constraint['variation_id']}/decision",
                     json={"decision": "Approved"}), 200)["status"] == "Approved"


def test_library_modules_are_versioned_and_curricula_keep_the_version_they_copied(client, login, catalog, people):
    """Module 14 §9: stable identity, explicit versions, independent review; running versions stay on what they copied."""
    vid, module_id = draft(client, login, people["ac"], topics=("Syntax",))
    library = data(call(client, login, people["ac"], "post", f"/curriculum-modules/{module_id}/library"), 201)
    first = library["versions"][0]
    assert library["module_code"].startswith("LIB-") and first["status"] == "Pending"
    assert call(client, login, people["ac"], "post", f"/curriculum-library-versions/{first['library_version_id']}/decision",
                json={"decision": "Approved"}).status_code == 422                               # not the proposer
    data(call(client, login, people["ac2"], "post", f"/curriculum-library-versions/{first['library_version_id']}/decision",
              json={"decision": "Approved"}), 200)

    other, _ = draft(client, login, people["ac"], code="NIT-CRS-047", label="CV 7.0", topics=())
    inserted = data(call(client, login, people["ac"], "post", f"/curriculum-versions/{other}/library-modules",
                         json={"library_version_id": first["library_version_id"]}), 201)
    assert inserted["library_version_id"] == first["library_version_id"] and [t["title"] for t in inserted["topics"]] == ["Syntax"]

    call(client, login, people["ac"], "post", f"/curriculum-modules/{module_id}/topics", json={"title": "Loops"})
    second = data(call(client, login, people["ac"], "post", f"/curriculum-library/{library['library_module_id']}/versions",
                       json={"module_id": module_id, "change_note": "Adds loops"}), 201)
    assert second["version_no"] == 2 and second["status"] == "Pending"
    data(call(client, login, people["ac2"], "post", f"/curriculum-library-versions/{second['library_version_id']}/decision",
              json={"decision": "Approved"}), 200)
    unchanged = data(call(client, login, people["ac"], "get", f"/curriculum-versions/{other}"), 200)["modules"][0]
    assert unchanged["library_version_id"] == first["library_version_id"] and len(unchanged["topics"]) == 1
