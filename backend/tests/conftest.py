import os
import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["AI_MODE"] = "mock"
os.environ["SECRET_KEY"] = "test-only-secret-key-with-32-bytes-minimum"
os.environ["LLM_API_URL"] = ""
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_MODEL"] = ""
os.environ["TOKEN_HOURS"] = "12"
os.environ["FRONTEND_URL"] = "http://localhost:5173"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app import seed  # noqa: E402


@pytest.fixture()
def client():
    seed.run()
    return TestClient(app)


def login(client, email, org_name=None):
    r = client.post("/auth/login", json={"email": email, "password": "pulse123"})
    data = r.json()
    token = data["token"]
    if org_name:
        org = next(o for o in data["organizations"] if o["org_name"] == org_name)
        token = client.post("/auth/select-org", json={"org_id": org["org_id"]},
                            headers={"Authorization": f"Bearer {token}"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}, data


@pytest.fixture()
def add_completed_respondents(client):
    """Create completed test diagnostics without invoking an AI provider."""
    from uuid import uuid4
    from app import models
    from app.auth import hash_password
    from app.db import SessionLocal
    from app.services.questions import questions_for

    def add(department_name, count, *, score=3.0, flags=(), org_name="Northwind Logistics"):
        with SessionLocal() as db:
            org = db.query(models.Organization).filter_by(name=org_name).one()
            department = db.query(models.Department).filter_by(org_id=org.id, name=department_name).one()
            for _ in range(count):
                user = models.User(email=f"respondent-{uuid4().hex}@example.test", name="Test respondent",
                                   password_hash=hash_password("pulse123"))
                db.add(user)
                db.flush()
                member = models.Membership(user_id=user.id, org_id=org.id, department_id=department.id,
                                           role="employee", job_role="support", seniority="junior")
                db.add(member)
                db.flush()
                submission = models.DiagnosticSubmission(membership_id=member.id, average_score=score)
                db.add(submission)
                db.flush()
                for question in questions_for(member.job_role, member.seniority):
                    db.add(models.Response(
                        membership_id=member.id, submission_id=submission.id,
                        question_id=question["id"], answer="Test answer", score=score,
                        flags=list(flags) if question["type"] == "open" else [],
                    ))
            db.commit()
    return add
