import json
from pathlib import Path

from tests.conftest import login
from app.services.llm import _mock
from app.utils import ALLOWED_FLAGS


def make_complete_payload(client, headers):
    questions = client.get("/diagnostic/questions", headers=headers).json()
    answers = []
    for question in questions:
        answer = question["options"][0] if question["type"] == "mcq" else "I use AI for routine work and review the result."
        answers.append({"question_id": question["id"], "answer": answer})
    return questions, answers


def test_mock_scoring_responses_follow_the_scoring_contract():
    path = Path(__file__).parents[1] / "data" / "mock_ai_responses.json"
    canned = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(canned, list)
    assert canned

    for raw in canned:
        result = json.loads(raw)
        assert isinstance(result["score"], (int, float))
        assert not isinstance(result["score"], bool)
        assert 1 <= result["score"] <= 5
        assert isinstance(result["reason"], str)
        assert isinstance(result["flags"], list)
        assert set(result["flags"]) <= ALLOWED_FLAGS

    assert any(json.loads(raw)["flags"] == [] for raw in canned)


def test_mock_runtime_never_selects_invalid_examples():
    for answer in ["ssss", "daily", "customer data", "another answer"]:
        result = json.loads(_mock(answer))
        assert 1 <= result["score"] <= 5
        assert isinstance(result["reason"], str)


def test_open_answer_with_mock_mode_can_be_submitted(client):
    headers, _ = login(client, "sara@northwind.test", "Northwind Logistics")
    _, answers = make_complete_payload(client, headers)
    for answer in answers:
        if answer["question_id"] == "common-open":
            answer["answer"] = "ssss"

    response = client.post(
        "/diagnostic/submit",
        headers=headers,
        json={"answers": answers},
    )
    assert response.status_code == 200
    assert response.json()["submitted"] is True


def test_submission_requires_all_questions_and_only_allows_one(client, monkeypatch):
    monkeypatch.setattr(
        "app.routes.diagnostic.score_open_answer",
        lambda *_: {"score": 3, "reason": "Reviewed use.", "flags": []},
    )
    headers, _ = login(client, "sara@northwind.test", "Northwind Logistics")
    questions, answers = make_complete_payload(client, headers)

    initial = client.get("/diagnostic/me", headers=headers)
    assert initial.status_code == 200
    assert initial.json() == {"submitted": False, "submitted_at": None}

    incomplete = client.post(
        "/diagnostic/submit",
        headers=headers,
        json={"answers": answers[:-1]},
    )
    assert incomplete.status_code == 400
    assert client.get("/diagnostic/me", headers=headers).json()["submitted"] is False

    submitted = client.post(
        "/diagnostic/submit",
        headers=headers,
        json={"answers": answers},
    )
    assert submitted.status_code == 200
    assert submitted.json()["submitted"] is True

    view = client.get("/diagnostic/me", headers=headers)
    assert view.status_code == 200
    assert view.json()["submitted"] is True
    report = client.get("/reports/me", headers=headers)
    assert report.status_code == 200
    assert report.json()["answered"] == len(questions)

    repeated = client.post(
        "/diagnostic/submit",
        headers=headers,
        json={"answers": answers},
    )
    assert repeated.status_code == 409


def test_employee_can_delete_selected_org_response_only(client, monkeypatch):
    monkeypatch.setattr(
        "app.routes.diagnostic.score_open_answer",
        lambda *_: {"score": 3, "reason": "Reviewed use.", "flags": []},
    )
    _, session = login(client, "ravi@consult.test")
    orgs = {org["org_name"]: org["org_id"] for org in session["organizations"]}

    scoped_headers = {}
    for org_name, org_id in orgs.items():
        selected = client.post(
            "/auth/select-org",
            json={"org_id": org_id},
            headers={"Authorization": f"Bearer {session['token']}"},
        )
        assert selected.status_code == 200
        headers = {"Authorization": f"Bearer {selected.json()['token']}"}
        scoped_headers[org_name] = headers
        _, answers = make_complete_payload(client, headers)
        submitted = client.post(
            "/diagnostic/submit",
            headers=headers,
            json={"answers": answers},
        )
        assert submitted.status_code == 200

    deleted = client.delete(
        "/diagnostic/me",
        headers=scoped_headers["Northwind Logistics"],
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted_submissions"] == 1
    assert deleted.json()["deleted_answers"] > 0

    northwind = client.get("/diagnostic/me", headers=scoped_headers["Northwind Logistics"])
    bluepeak = client.get("/diagnostic/me", headers=scoped_headers["Bluepeak Retail"])
    assert northwind.json()["submitted"] is False
    assert bluepeak.json()["submitted"] is True

    priya_headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    assert client.get("/diagnostic/me", headers=priya_headers).json()["submitted"] is True


def test_report_is_separate_and_available_for_submitted_response(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")

    status = client.get("/diagnostic/me", headers=headers)
    assert status.status_code == 200
    assert set(status.json()) == {"submitted", "submitted_at"}
    assert status.json()["submitted"] is True

    report = client.get("/reports/me", headers=headers)
    assert report.status_code == 200
    assert report.json()["name"] == "Priya Nair"
    assert report.json()["answered"] > 0


def test_invalid_ai_score_leaves_no_partial_submission(client, monkeypatch):
    monkeypatch.setattr(
        "app.routes.diagnostic.score_open_answer",
        lambda *_: {"score": 7, "reason": "Invalid scale.", "flags": []},
    )
    headers, _ = login(client, "sara@northwind.test", "Northwind Logistics")
    _, answers = make_complete_payload(client, headers)

    response = client.post(
        "/diagnostic/submit",
        headers=headers,
        json={"answers": answers},
    )
    assert response.status_code == 502
    assert client.get("/diagnostic/me", headers=headers).json()["submitted"] is False
