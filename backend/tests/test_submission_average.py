import pytest

from app import models
from app.db import SessionLocal
from app.services.questions import load_questions
from tests.conftest import login
from tests.test_diagnostic_submissions import make_complete_payload


def test_submission_saves_full_precision_average_and_replaces_it_after_deletion(client, monkeypatch):
    monkeypatch.setattr("app.routes.diagnostic.score_open_answer",
                        lambda *args: {"score": 4.123456, "reason": "Test score", "flags": []})
    headers, _ = login(client, "sara@northwind.test", "Northwind Logistics")
    _, answers = make_complete_payload(client, headers)
    bank = {question["id"]: question for question in load_questions()}
    scores = [
        4.123456 if bank[a["question_id"]]["type"] == "open" else next(
            option["points"] for option in bank[a["question_id"]]["options"] if option["text"] == a["answer"]
        ) for a in answers
    ]
    expected = sum(scores) / len(scores)
    assert client.post("/diagnostic/submit", headers=headers, json={"answers": answers}).status_code == 200
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email="sara@northwind.test").one()
        membership = db.query(models.Membership).filter_by(user_id=user.id).one()
        submission = db.query(models.DiagnosticSubmission).filter_by(membership_id=membership.id).one()
        assert submission.average_score == pytest.approx(expected)
        assert submission.average_score != round(expected, 2)
        membership_id = membership.id
    assert client.get("/reports/me", headers=headers).json()["average_score"] == round(expected, 2)

    assert client.delete("/diagnostic/me", headers=headers).status_code == 200
    with SessionLocal() as db:
        assert db.query(models.DiagnosticSubmission).filter_by(membership_id=membership_id).first() is None
    monkeypatch.setattr("app.routes.diagnostic.score_open_answer",
                        lambda *args: {"score": 1, "reason": "New score", "flags": []})
    assert client.post("/diagnostic/submit", headers=headers, json={"answers": answers}).status_code == 200
    assert client.get("/reports/me", headers=headers).json()["average_score"] != round(expected, 2)


def test_report_and_dashboard_read_saved_average_instead_of_recalculating(client, add_completed_respondents):
    add_completed_respondents("Engineering", 5, score=4)
    with SessionLocal() as db:
        department = db.query(models.Department).filter_by(name="Engineering").one()
        memberships = db.query(models.Membership).filter_by(department_id=department.id).all()
        completed = db.query(models.DiagnosticSubmission).filter(
            models.DiagnosticSubmission.membership_id.in_([m.id for m in memberships])
        ).all()
        employee = db.get(models.Membership, completed[0].membership_id).user.email
        # Deliberately alter underlying rows to detect unwanted read-time recalculation.
        db.query(models.Response).filter(
            models.Response.submission_id.in_([s.id for s in completed])
        ).update({"score": 1}, synchronize_session=False)
        db.commit()

    headers, _ = login(client, employee, "Northwind Logistics")
    assert client.get("/reports/me", headers=headers).json()["average_score"] == 4
    headers, session = login(client, "asha@northwind.test", "Northwind Logistics")
    org_id = session["organizations"][0]["org_id"]
    data = client.get(f"/dashboard?org_id={org_id}", headers=headers).json()
    engineering = next(d for d in data["departments"] if d["department"] == "Engineering")
    assert engineering["average_score"] == 4
    assert engineering["level"] == "Leader"
