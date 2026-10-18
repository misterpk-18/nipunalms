"""R6: the course outline. Modules and topics live on the course; everyone who can see the course reads it, Super Admin and Founder edit
it (an edit applies at once, tells the Branch Managers of branches with open batches of the course, and is audited), and the CRM-owned
fields stay read-only."""
from sqlalchemy import select, text

from config.database import db
from models import AuditLog, CourseModule, Notification
from tests.helpers import course_id as java_course_id
from tests.test_delivery import call, data, future, iso, world as delivery_world  # noqa: F401
import pytest


@pytest.fixture
def world(delivery_world):
    """The delivery world, with the outlines it pre-writes removed: these tests start from empty courses."""
    db.session.execute(text("DELETE FROM course_modules"))
    db.session.commit()
    return delivery_world

PROFILE = {"attendance_minimum_pct": 75, "pass_mark_pct": 50, "recovery_rule": "Approved recovery before the end date",
           "reassessment_rule": "One reassessment"}


def _outline(client, login, who, course_id):
    return call(client, login, who, "get", f"/courses/{course_id}/outline")


def _module(client, login, who, course_id, title="Core Java", **extra):
    return data(call(client, login, who, "post", f"/courses/{course_id}/modules", json={"title": title, **extra}), 201)


def _topic(client, login, who, module_id, title, **extra):
    return data(call(client, login, who, "post", f"/course-modules/{module_id}/topics", json={"title": title, **extra}), 201)


# ---------------------------------------------------------------- the migration's result on a fresh database

def test_there_are_no_curriculum_versions_left_in_the_schema(app):
    gone = db.session.execute(text("""
        SELECT to_regclass('curriculum_versions') IS NULL AND to_regclass('curriculum_events') IS NULL
           AND to_regclass('equivalence_rules') IS NULL AND to_regclass('academic_mappings') IS NULL
           AND to_regclass('curriculum_variations') IS NULL AND to_regclass('curriculum_version_components') IS NULL
           AND to_regclass('learning_credits') IS NULL AND to_regtype('curriculum_status') IS NULL""")).scalar()
    assert gone is True
    columns = {(t, c) for t, c in db.session.execute(text(
        "SELECT table_name, column_name FROM information_schema.columns WHERE column_name = 'curriculum_version_id'"))}
    assert columns == set()
    keeps = db.session.execute(text("""
        SELECT (SELECT is_nullable FROM information_schema.columns WHERE table_name = 'course_modules' AND column_name = 'course_id'),
               (SELECT count(*) FROM information_schema.columns WHERE table_name = 'courses' AND column_name IN
                  ('hours_verified_by', 'hours_verified_at', 'completion_profile')),
               to_regclass('course_assessment_requirements') IS NOT NULL, to_regclass('library_modules') IS NOT NULL""")).one()
    assert tuple(keeps) == ("NO", 3, True, True)


def test_a_student_follows_the_course_outline_without_a_curriculum_version(world, client, login, run_sql):
    people, _, student = world
    cid = java_course_id()
    module = _module(client, login, people["admin"], cid)
    topic = _topic(client, login, people["admin"], module["module_id"], "Streams")
    rows = run_sql("SELECT count(*) FROM enrolment_required_topics WHERE topic_id = :t", t=topic["topic_id"]).scalar()
    assert rows >= 1
    cards = data(call(client, login, student.student_code, "get", "/me/enrolments"), 200)
    assert "curriculum_version" not in cards[0]
    detail = data(call(client, login, student.student_code, "get", f"/me/enrolments/{cards[0]['enrolment_id']}"), 200)
    assert [m["title"] for m in detail["modules"]] == ["Core Java"] and detail["topics"]["total"] == 1
    page = data(call(client, login, student.student_code, "get", f"/modules/{module['module_id']}"), 200)
    assert page["course_id"] == cid and "curriculum_version" not in page
    assert data(call(client, login, student.student_code, "get", f"/topics/{topic['topic_id']}"), 200)["module"]["course_id"] == cid


# ---------------------------------------------------------------- reading

def test_everyone_who_can_see_the_course_reads_the_outline(world, client, login, make_student):
    people, _, student = world
    cid = java_course_id()
    module = _module(client, login, people["admin"], cid)
    _topic(client, login, people["admin"], module["module_id"], "Streams")

    for who in ("admin", "founder", "ac", "ac_vij", "g1", student.student_code):
        body = data(_outline(client, login, people[who] if who in people else who, cid), 200)
        assert [m["title"] for m in body["modules"]] == ["Core Java"] and body["course"]["course_code"] == "NIT-CRS-047"
        assert body["counts"] == {"modules": 1, "topics": 1, "required_topics": 1}
    assert data(_outline(client, login, people["admin"], cid), 200)["can_edit"] is True
    assert data(_outline(client, login, people["ac"], cid), 200)["can_edit"] is False
    # staff get the hours, completion rules, required assessments and usage; a trainer and a student do not
    assert {"totals", "completion_profile", "assessment_requirements", "usage"} <= set(data(_outline(client, login, people["ac"], cid), 200))
    for who in (people["g1"], student.student_code):
        assert not {"totals", "completion_profile", "assessment_requirements", "usage"} & set(data(_outline(client, login, who, cid), 200))
    # a trainer without a batch of the course, and a student without an enrolment in it, do not see it
    assert _outline(client, login, people["v1"], cid).status_code == 404
    other = make_student(course="NIT-CRS-052", admission_id="A-OTHER", person_id="P-OTHER", email="other@example.test")
    assert _outline(client, login, other.student_code, cid).status_code == 404
    assert _outline(client, login, people["admin"], 999999).status_code == 404


def test_the_course_list_is_for_branch_managers_super_admin_and_founder(world, client, login):
    people, batch, student = world
    for who in ("admin", "founder", "ac"):
        rows = data(call(client, login, people[who], "get", "/courses"), 200)
        java = next(r for r in rows if r["course_code"] == "NIT-CRS-047")
        assert java["usage"]["running_batches"] == 1 and java["counts"]["modules"] == 0 and "components" in java
    company = data(call(client, login, people["admin"], "get", "/courses"), 200)
    assert next(r for r in company if r["course_code"] == "NIT-CRS-047")["usage"]["by_branch"][0]["branch"]["branch_id"] == 1
    # a Branch Manager of another branch counts only their own branch
    vij = next(r for r in data(call(client, login, people["ac_vij"], "get", "/courses"), 200) if r["course_code"] == "NIT-CRS-047")
    assert vij["usage"]["running_batches"] == 0 and vij["usage"]["by_branch"] == []
    for who in (people["g1"], student.student_code):
        assert call(client, login, who, "get", "/courses").status_code == 403


# ---------------------------------------------------------------- editing

def test_only_super_admin_and_founder_edit_the_outline(world, client, login):
    people, _, student = world
    cid = java_course_id()
    module = _module(client, login, people["admin"], cid, "Basics")
    topic = _topic(client, login, people["founder"], module["module_id"], "Syntax")
    for who in (people["ac"], people["g1"], student.student_code):
        assert call(client, login, who, "post", f"/courses/{cid}/modules", json={"title": "x"}).status_code == 403
        assert call(client, login, who, "patch", f"/course-modules/{module['module_id']}", json={"title": "x"}).status_code == 403
        assert call(client, login, who, "delete", f"/course-modules/{module['module_id']}").status_code == 403
        assert call(client, login, who, "post", f"/course-modules/{module['module_id']}/topics", json={"title": "x"}).status_code == 403
        assert call(client, login, who, "patch", f"/course-topics/{topic['topic_id']}", json={"title": "x"}).status_code == 403
        assert call(client, login, who, "delete", f"/course-topics/{topic['topic_id']}").status_code == 403
        assert call(client, login, who, "post", f"/courses/{cid}/hours-verification").status_code == 403
        assert call(client, login, who, "put", f"/courses/{cid}/completion-profile", json=PROFILE).status_code == 403
        assert call(client, login, who, "post", f"/courses/{cid}/assessment-requirements", json={}).status_code == 403
        assert call(client, login, who, "put", f"/courses/{cid}/track-pins", json={"component_id": 1}).status_code == 403
    assert call(client, login, people["ac"], "get", f"/course-library").status_code == 200
    assert call(client, login, people["g1"], "get", f"/course-library").status_code == 403


def test_add_rename_reorder_and_remove_modules_and_topics(world, client, login):
    people, _, _ = world
    cid, admin = java_course_id(), people["admin"]
    first, second = _module(client, login, admin, cid, "One"), _module(client, login, admin, cid, "Two")
    t1, t2 = (_topic(client, login, admin, second["module_id"], "Loops", is_required=False),
              _topic(client, login, admin, second["module_id"], "Syntax"))
    assert t1["sort_order"] == 1 and t2["sort_order"] == 2 and t1["is_required"] is False
    data(call(client, login, admin, "patch", f"/course-modules/{second['module_id']}", json={"title": "Second", "position": 1}), 200)
    data(call(client, login, admin, "patch", f"/course-topics/{t2['topic_id']}", json={"position": 1, "title": "Syntax basics"}), 200)
    body = data(_outline(client, login, admin, cid), 200)
    assert [m["title"] for m in body["modules"]] == ["Second", "One"]
    assert [t["title"] for t in body["modules"][0]["topics"]] == ["Syntax basics", "Loops"]
    assert call(client, login, admin, "delete", f"/course-topics/{t1['topic_id']}").status_code == 204
    assert call(client, login, admin, "delete", f"/course-modules/{first['module_id']}").status_code == 204
    body = data(_outline(client, login, admin, cid), 200)
    assert [(m["title"], m["sort_order"]) for m in body["modules"]] == [("Second", 1)]
    assert [t["title"] for t in body["modules"][0]["topics"]] == ["Syntax basics"]


def test_a_module_that_classes_use_is_archived_not_deleted_and_its_topics_stay(world, client, login, make_session):
    people, batch, _ = world
    cid, admin = java_course_id(), people["admin"]
    module = _module(client, login, admin, cid)
    topic = _topic(client, login, admin, module["module_id"], "Streams")
    make_session(batch, people["g1"], future(3), topic_id=topic["topic_id"])
    refused = call(client, login, admin, "delete", f"/course-topics/{topic['topic_id']}")
    assert refused.status_code == 422
    result = call(client, login, admin, "delete", f"/course-modules/{module['module_id']}")
    assert result.status_code == 204
    row = db.session.get(CourseModule, module["module_id"])
    assert row.is_archived is True and row.course_id == cid
    assert data(_outline(client, login, admin, cid), 200)["modules"] == []  # hidden from the outline, nothing lost


def test_hours_completion_rules_required_assessments_and_pins(world, client, login):
    people, _, _ = world
    cid, admin, founder = java_course_id(), people["admin"], people["founder"]
    module = _module(client, login, admin, cid)
    topic = _topic(client, login, admin, module["module_id"], "Streams")
    assert call(client, login, admin, "post", f"/courses/{cid}/hours-verification").status_code == 422  # no estimate yet
    data(call(client, login, admin, "patch", f"/course-topics/{topic['topic_id']}", json={"instructional_minutes": 90, "independent_minutes": 30}), 200)
    body = data(call(client, login, admin, "post", f"/courses/{cid}/hours-verification"), 200)
    assert body["totals"]["hours_verified"] is True and body["totals"]["total_minutes"] == 120
    data(call(client, login, founder, "patch", f"/course-topics/{topic['topic_id']}", json={"instructional_minutes": 60}), 200)
    assert data(_outline(client, login, admin, cid), 200)["totals"]["hours_verified"] is False  # a changed estimate needs a new check
    body = data(call(client, login, founder, "put", f"/courses/{cid}/completion-profile", json=PROFILE), 200)
    assert body["completion_profile"]["pass_mark_pct"] == 50.0
    req = data(call(client, login, admin, "post", f"/courses/{cid}/assessment-requirements", json={
        "kind": "Test", "title": "Final test", "outcome": "Applies streams", "weight": 40, "pass_rule": "50% or more",
        "topic_id": topic["topic_id"]}), 201)
    assert req["course_id"] == cid and [r["title"] for r in data(_outline(client, login, admin, cid), 200)["assessment_requirements"]] == ["Final test"]
    assert call(client, login, admin, "delete", f"/assessment-requirements/{req['requirement_id']}").status_code == 204


def test_a_combo_track_has_its_own_outline_and_can_be_pinned_after_the_review(world, client, login, make_student):
    from repositories import catalog as catalog_repo

    people, _, _ = world
    admin = people["admin"]
    combo = catalog_repo.get_course_by_code("NIT-CRS-018")
    t1 = next(c for c in combo.components if c.track_code == "NIT-CRS-018/T1")
    booster = next(c for c in combo.components if c.track_code == "NIT-CRS-019")
    own = _module(client, login, admin, combo.course_id, "Foundations", component_id=t1.component_id)
    body = data(_outline(client, login, admin, combo.course_id), 200)
    assert body["modules"] == [] and next(t for t in body["tracks"] if t["component"]["track_code"] == "NIT-CRS-018/T1")["modules"][0]["module_id"] == own["module_id"]
    assert call(client, login, admin, "post", f"/courses/{combo.course_id}/modules", json={"title": "x", "component_id": 999999}).status_code == 400
    # the included booster was reviewed (the catalog fixture), so it can follow the Power BI outline; T1 has no standalone course to reuse
    power_bi = java_course_id("NIT-CRS-019")
    _module(client, login, admin, power_bi, "Dashboards")
    assert call(client, login, admin, "put", f"/courses/{combo.course_id}/track-pins", json={"component_id": t1.component_id, "pinned_course_id": power_bi}).status_code == 400
    body = data(call(client, login, admin, "put", f"/courses/{combo.course_id}/track-pins", json={"component_id": booster.component_id, "pinned_course_id": power_bi}), 200)
    pinned = next(t for t in body["tracks"] if t["component"]["track_code"] == "NIT-CRS-019")
    assert pinned["borrowed_from"]["course_id"] == power_bi and [m["title"] for m in pinned["modules"]] == ["Dashboards"]
    data(call(client, login, admin, "put", f"/courses/{combo.course_id}/track-pins", json={"component_id": booster.component_id, "pinned_course_id": None}), 200)


def test_the_reusable_module_library_is_used_from_the_course(world, client, login):
    people, _, _ = world
    cid, admin = java_course_id(), people["admin"]
    module = _module(client, login, admin, cid)
    _topic(client, login, admin, module["module_id"], "Streams")
    saved = data(call(client, login, admin, "post", f"/course-modules/{module['module_id']}/library"), 201)
    version = saved["current_version"]
    assert version["status"] == "Approved" and version["content"]["topics"][0]["title"] == "Streams"  # no approval step
    other = java_course_id("NIT-CRS-052")
    copied = data(call(client, login, people["founder"], "post", f"/courses/{other}/library-modules", json={"library_version_id": version["library_version_id"]}), 201)
    assert copied["library_version_id"] == version["library_version_id"] and [t["title"] for t in copied["topics"]] == ["Streams"]
    again = data(call(client, login, admin, "post", f"/course-library/{saved['library_module_id']}/versions",
                      json={"module_id": module["module_id"], "change_note": "More topics"}), 201)
    assert again["version_no"] == 2 and again["status"] == "Approved"


# ---------------------------------------------------------------- the CRM owns code, title, category, status and tracks

def test_course_code_title_category_status_and_tracks_are_read_only(world, client, login, crm_event):
    people, _, _ = world
    cid, admin = java_course_id(), people["admin"]
    for method in ("patch", "put", "post", "delete"):
        assert call(client, login, admin, method, f"/courses/{cid}", json={"title": "Hacked"}).status_code in (404, 405)
    assert call(client, login, admin, "patch", f"/course-modules/{_module(client, login, admin, cid)['module_id']}",
                json={"course_id": 1, "title": "Renamed"}).status_code == 200  # unknown fields are not applied
    module = db.session.execute(select(CourseModule).where(CourseModule.title == "Renamed")).scalar_one()
    assert module.course_id == cid
    # the CRM's event updates its own fields and leaves the LMS-owned outline, hours and completion rules alone
    data(call(client, login, admin, "put", f"/courses/{cid}/completion-profile", json=PROFILE), 200)
    response = crm_event("CourseUpserted", {"course_code": "NIT-CRS-047", "title": "Java Full Stack Developer (2027)", "category": "Software"},
                         source_version=2)
    assert response.status_code == 201, response.get_json()
    body = data(_outline(client, login, admin, cid), 200)
    assert body["course"]["title"] == "Java Full Stack Developer (2027)" and body["course"]["category"] == "Software"
    assert [m["title"] for m in body["modules"]] == ["Renamed"] and body["completion_profile"]["pass_mark_pct"] == 50.0


# ---------------------------------------------------------------- notify and audit

def test_an_edit_tells_the_managers_of_branches_with_open_batches_and_is_audited(world, client, login):
    people, batch, _ = world
    cid, admin = java_course_id(), people["admin"]
    module = _module(client, login, admin, cid, "Cloud basics")

    told = db.session.execute(select(Notification).where(Notification.category == "Courses", Notification.recipient_user_id.in_(
        [people["ac"].user_id, people["ac2"].user_id, people["bm"].user_id]))).scalars().all()
    assert len(told) == 3 and all(n.category == "Courses" and n.link == f"/branch/courses/{cid}" for n in told)
    assert "Cloud basics" in told[0].body
    assert db.session.execute(select(Notification).where(Notification.recipient_user_id == people["ac_vij"].user_id)).first() is None  # no batch there
    assert db.session.execute(select(Notification).where(Notification.recipient_user_id == admin.user_id)).first() is None  # the editor knows

    _topic(client, login, people["founder"], module["module_id"], "Deploying")
    assert db.session.execute(select(Notification).where(Notification.category == "Courses", Notification.recipient_user_id == people["ac"].user_id)).scalars().all().__len__() == 2

    entries = db.session.execute(select(AuditLog).where(AuditLog.action == "COURSE_OUTLINE_CHANGED").order_by(AuditLog.audit_id)).scalars().all()
    assert [e.entity_type for e in entries] == ["course", "course"] and {e.entity_id for e in entries} == {str(cid)}
    assert entries[0].actor_user_id == admin.user_id and entries[1].actor_user_id == people["founder"].user_id
    assert "Cloud basics" in entries[0].new_values["change"]


def test_a_course_with_no_open_batch_tells_nobody(world, client, login):
    people, _, _ = world
    _module(client, login, people["admin"], java_course_id("NIT-CRS-052"), "Python")
    assert db.session.execute(select(Notification).where(Notification.category == "Courses")).first() is None
    assert db.session.execute(select(AuditLog).where(AuditLog.action == "COURSE_OUTLINE_CHANGED")).scalar_one()
