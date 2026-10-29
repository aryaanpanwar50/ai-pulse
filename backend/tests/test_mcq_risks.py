import pytest

from app import models
from app.db import SessionLocal
from app.services.questions import load_questions
from app.utils import ALLOWED_FLAGS
from tests.conftest import login
from tests.test_diagnostic_submissions import make_complete_payload


def test_mcq_flag_rules_are_valid_and_private(client):
    questions = {q["id"]: q for q in load_questions()}
    assert questions["common-policy"]["options"][0]["flags"] == ["policy_unaware"]
    assert questions["common-review"]["options"][0]["flags"] == ["unreviewed_output"]
    for question in questions.values():
        for option in question.get("options", []):
            assert set(option.get("flags", [])) <= ALLOWED_FLAGS

    headers, _ = login(client, "kavitha@northwind.test", "Northwind Logistics")
    for question in client.get("/diagnostic/questions", headers=headers).json():
        assert "flags" not in question
        assert "points" not in question
        assert all(isinstance(option, str) for option in question.get("options", []))


@pytest.mark.parametrize("flagged", [True, False])
def test_mcq_flags_are_saved_and_combined_with_written_flags(
    client, monkeypatch, add_completed_respondents, flagged
):
    monkeypatch.setattr(
        "app.routes.diagnostic.score_open_answer",
        lambda *_: {"score": 3, "reason": "Reviewed use.", "flags": ["unreviewed_output"]},
    )
    headers, _ = login(client, "kavitha@northwind.test", "Northwind Logistics")
    _, answers = make_complete_payload(client, headers)
    if not flagged:
        choices = {
            "common-policy": "Yes, I've read it",
            "common-review": "Check facts and edit it",
        }
        for answer in answers:
            answer["answer"] = choices.get(answer["question_id"], answer["answer"])

    assert client.post("/diagnostic/submit", headers=headers, json={"answers": answers}).status_code == 200
    expected = ["policy_unaware", "unreviewed_output"] if flagged else ["unreviewed_output"]
    assert client.get("/reports/me", headers=headers).json()["risks"] == expected
    with SessionLocal() as db:
        member = db.query(models.Membership).join(models.User).filter(models.User.email == "kavitha@northwind.test").one()
        rows = {row.question_id: row for row in db.query(models.Response).filter_by(membership_id=member.id)}
        assert rows["common-review"].flags == (["unreviewed_output"] if flagged else [])
        assert rows["common-review"].score == (1 if flagged else 4)
        assert rows["common-policy"].flags == (["policy_unaware"] if flagged else [])
        assert rows["common-data"].flags == []
        assert rows["common-freq"].flags == []
        assert rows["sup-drafts"].flags == []
        department_name = member.department.name

    add_completed_respondents(department_name, 3)
    admin_headers, session = login(client, "asha@northwind.test", "Northwind Logistics")
    org_id = session["organizations"][0]["org_id"]
    risks = dict(client.get(f"/dashboard?org_id={org_id}", headers=admin_headers).json()["top_risks"])
    assert risks["unreviewed_output"] == 1
    assert risks.get("policy_unaware", 0) == (1 if flagged else 0)


def test_invalid_mcq_flag_cannot_be_saved(client, monkeypatch):
    from app.services.questions import questions_for

    headers, _ = login(client, "kavitha@northwind.test", "Northwind Logistics")
    _, answers = make_complete_payload(client, headers)
    questions = questions_for("support", "mid")
    questions[0]["options"][0]["flags"] = ["unknown_risk"]
    monkeypatch.setattr("app.routes.diagnostic.questions_for", lambda *_: questions)

    response = client.post("/diagnostic/submit", headers=headers, json={"answers": answers})
    assert response.status_code == 500
    assert client.get("/diagnostic/me", headers=headers).json()["submitted"] is False
