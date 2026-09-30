"""Question bank: drafting, key validation per type, approval, versions, and that keys stay with staff."""
import pytest

from services.scoring import score_answer
from decimal import Decimal
from tests.assessment_world import API, make_question, question_body, world  # noqa: F401 (fixtures)


def create(client, world, who="g1", **overrides):
    return client.post(f"{API}/questions", json=question_body(world, **overrides), headers=world.h[who])


def test_trainer_drafts_and_the_coordinator_approves(client, world):
    response = create(client, world)
    assert response.status_code == 201, response.get_json()
    question = response.get_json()["data"]
    assert question["status"] == "Draft" and question["question_code"].startswith("QB-") and question["version"] == 1
    assert question["branch"]["branch_code"] == "NIT-GNT" and question["author"]["full_name"] == "Trainer G1"
    assert question["tags"] == ["metrics"] and question["answer_key"] == {"option": "B"}

    own = client.post(f"{API}/questions/{question['question_id']}/approve", headers=world.h["g1"])
    assert own.status_code == 403  # trainers do not approve
    approved = client.post(f"{API}/questions/{question['question_id']}/approve", headers=world.h["ac"])
    assert approved.status_code == 200 and approved.get_json()["data"]["status"] == "Approved"
    assert client.post(f"{API}/questions/{question['question_id']}/approve", headers=world.h["ac"]).status_code == 422


def test_an_author_cannot_approve_their_own_question(client, world):
    question = create(client, world, who="ac").get_json()["data"]
    own = client.post(f"{API}/questions/{question['question_id']}/approve", headers=world.h["ac"])
    assert own.status_code == 422 and "another reviewer" in own.get_json()["error"]["message"]
    assert client.post(f"{API}/questions/{question['question_id']}/approve", headers=world.h["ac2"]).status_code == 200


@pytest.mark.parametrize("overrides", [
    {"answer_key": {"option": "Z"}},                                            # not an option
    {"answer_key": {}},
    {"options": [{"key": "A", "text": "only one"}], "answer_key": {"option": "A"}},
    {"options": [{"key": "A", "text": "x"}, {"key": "A", "text": "y"}], "answer_key": {"option": "A"}},
    {"question_type": "Multiple choice", "answer_key": {"options": []}},
    {"question_type": "True / False", "options": [], "answer_key": {"value": "yes"}},
    {"question_type": "Numeric", "options": [], "answer_key": {"value": "three"}},
    {"question_type": "Short answer", "options": [], "answer_key": {"variants": []}},
    {"question_type": "Coding", "options": [], "answer_key": {}},
    {"question_type": "Short answer", "answer_key": {"variants": ["x"]}},       # options given for a type without any
    {"stem": ""},
    {"marks": 0},
    {"difficulty": "Impossible"},
])
def test_answer_keys_must_match_the_question_type(client, world, overrides):
    assert create(client, world, **overrides).status_code == 400


def test_every_type_can_be_created_with_its_key_shape(client, world):
    shapes = [
        ("Multiple choice", [{"key": "A", "text": "L1"}, {"key": "B", "text": "L2"}, {"key": "C", "text": "OHE"}], {"options": ["A", "B"]}),
        ("True / False", [], {"value": True}),
        ("Numeric", [], {"value": 3, "tolerance": 0.1}),
        ("Short answer", [], {"variants": ["Random forest", "Gradient boosting"]}),
        ("Descriptive", [], {"rubric": "Mentions bias, variance and the trade-off"}),
        ("Coding", [], {"rubric": "Returns sum(xs) / len(xs)"}),
        ("Output prediction", [], {"variants": ["2"]}),
    ]
    for question_type, options, key in shapes:
        response = create(client, world, question_type=question_type, options=options, answer_key=key)
        assert response.status_code == 201, (question_type, response.get_json())
        assert response.get_json()["data"]["answer_key"] == key


def test_scope_and_permissions(client, world):
    question = create(client, world).get_json()["data"]
    qid = question["question_id"]
    assert client.get(f"{API}/questions/{qid}", headers=world.h["g2"]).status_code == 200  # another Guntur trainer works in the same branch bank
    assert client.get(f"{API}/questions/{qid}", headers=world.h["v1"]).status_code == 404  # another branch
    assert client.get(f"{API}/questions/{qid}", headers=world.h["ac_vij"]).status_code == 404
    assert client.get(f"{API}/questions/{qid}", headers=world.h["admin"]).status_code == 200
    for who in ("s1", "bm"):
        assert client.get(f"{API}/questions", headers=world.h[who]).status_code == 403
        assert create(client, world, who=who).status_code == 403
    assert [q["question_id"] for q in client.get(f"{API}/questions", headers=world.h["v1"]).get_json()["data"]] == []
    vij = create(client, world, who="v1")  # trainer v1 teaches Java at Vijayawada: the question lands in that branch's bank
    assert vij.status_code == 201 and vij.get_json()["data"]["branch"]["branch_code"] == "NIT-VIJ"
    assert client.get(f"{API}/questions/{vij.get_json()['data']['question_id']}", headers=world.h["g1"]).status_code == 404
    assert create(client, world, who="v1", branch_id=1).status_code == 403  # not their branch
    assert client.get(f"{API}/questions").status_code == 401


def test_a_trainer_only_drafts_for_courses_they_teach(client, world):
    other_course = world.batches["G1"].course_id + 1  # a course nobody in the fixture teaches
    assert create(client, world, course_id=other_course).status_code in (403, 400)
    assert create(client, world, course_id=999999).status_code == 400


def test_list_filters(client, world):
    make_question(client, world, stem="Approved regression question", tags=["regression"])
    create(client, world, stem="Draft SQL question", difficulty="Hard", tags=["sql"])
    listed = client.get(f"{API}/questions?status=Approved", headers=world.h["g1"]).get_json()
    assert [q["stem"] for q in listed["data"]] == ["Approved regression question"]
    assert listed["meta"]["total"] == 1
    assert len(client.get(f"{API}/questions?difficulty=Hard", headers=world.h["g1"]).get_json()["data"]) == 1
    assert len(client.get(f"{API}/questions?q=regression", headers=world.h["g1"]).get_json()["data"]) == 1
    assert len(client.get(f"{API}/questions?q=SQL", headers=world.h["g1"]).get_json()["data"]) == 1
    assert client.get(f"{API}/questions?status=Bogus", headers=world.h["g1"]).status_code == 400


def test_drafts_edit_freely_but_approved_questions_get_new_versions(client, world):
    draft = create(client, world).get_json()["data"]
    qid = draft["question_id"]
    edited = client.patch(f"{API}/questions/{qid}", json={"stem": "Reworded", "answer_key": {"option": "A"}}, headers=world.h["g1"])
    assert edited.status_code == 200 and edited.get_json()["data"]["stem"] == "Reworded" and edited.get_json()["data"]["answer_key"] == {"option": "A"}
    assert client.patch(f"{API}/questions/{qid}", json={"answer_key": {"option": "Z"}}, headers=world.h["g1"]).status_code == 400
    assert client.patch(f"{API}/questions/{qid}", json={}, headers=world.h["g1"]).status_code == 400
    assert client.patch(f"{API}/questions/{qid}", json={"stem": "x"}, headers=world.h["v1"]).status_code == 404

    client.post(f"{API}/questions/{qid}/approve", headers=world.h["ac"])
    assert client.patch(f"{API}/questions/{qid}", json={"stem": "Changed"}, headers=world.h["g1"]).status_code == 422

    version = client.post(f"{API}/questions/{qid}/new-version", headers=world.h["g1"])
    assert version.status_code == 201
    v2 = version.get_json()["data"]
    assert v2["version"] == 2 and v2["status"] == "Draft" and v2["parent_question_id"] == qid
    client.patch(f"{API}/questions/{v2['question_id']}", json={"stem": "Better wording"}, headers=world.h["g1"])
    client.post(f"{API}/questions/{v2['question_id']}/approve", headers=world.h["ac"])
    assert client.get(f"{API}/questions/{qid}", headers=world.h["g1"]).get_json()["data"]["status"] == "Retired"  # replaced by v2
    assert client.post(f"{API}/questions/{qid}/new-version", headers=world.h["g1"]).status_code == 201  # a retired one can be revived
    assert client.post(f"{API}/questions/{v2['question_id']}/retire", headers=world.h["g1"]).status_code == 403
    assert client.post(f"{API}/questions/{v2['question_id']}/retire", headers=world.h["ac"]).status_code == 200
    assert client.post(f"{API}/questions/{v2['question_id']}/retire", headers=world.h["ac"]).status_code == 422


def test_scoring_rules():
    marks = Decimal("2")
    assert score_answer("Single choice", {"option": "B"}, "B", marks) == 2
    assert score_answer("Single choice", {"option": "B"}, "A", marks) == 0
    assert score_answer("Multiple choice", {"options": ["A", "B"]}, ["B", "A"], marks) == 2  # exact set, any order
    assert score_answer("Multiple choice", {"options": ["A", "B"]}, ["A"], marks) == 0        # no partial credit
    assert score_answer("True / False", {"value": True}, True, marks) == 2
    assert score_answer("True / False", {"value": True}, "true", marks) == 0
    assert score_answer("Numeric", {"value": 3, "tolerance": 0.1}, 3.05, marks) == 2
    assert score_answer("Numeric", {"value": 3, "tolerance": 0.1}, "3.5", marks) == 0
    assert score_answer("Numeric", {"value": 3, "tolerance": 0}, "abc", marks) == 0
    assert score_answer("Short answer", {"variants": ["Random Forest"]}, "  random   forest ", marks) == 2
    assert score_answer("Output prediction", {"variants": ["2"]}, "2", marks) == 2
    assert score_answer("Descriptive", {"rubric": "x"}, "long answer", marks) is None  # needs a trainer
    assert score_answer("Coding", {"rubric": "x"}, "def f(): pass", marks) is None
    assert score_answer("Coding", {"rubric": "x"}, "", marks) == 0                       # blank needs no trainer
    assert score_answer("Single choice", {"option": "B"}, None, marks) == 0
