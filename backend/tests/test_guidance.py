import httpx
import json
import pytest

from tests.conftest import login
from tests.test_diagnostic_submissions import make_complete_payload


def test_guidance_is_generated_once_saved_and_deleted_with_submission(client, monkeypatch):
    calls = []

    def generate(role, seniority, answers):
        calls.append((role, seniority, answers))
        return {"feedback": "You can improve how you review AI output.",
                "next_steps": ["Check one AI-generated reply against its source before sending it."]}

    monkeypatch.setattr("app.routes.diagnostic.generate_guidance", generate, raising=False)
    headers, _ = login(client, "sara@northwind.test", "Northwind Logistics")
    questions, answers = make_complete_payload(client, headers)
    assert client.post("/diagnostic/submit", headers=headers, json={"answers": answers}).status_code == 200

    report = client.get("/reports/me", headers=headers).json()
    assert report["feedback"] == "You can improve how you review AI output."
    assert len(report["next_steps"]) == 1
    assert client.get("/reports/me", headers=headers).json() == report
    assert len(calls) == 1
    assert {a["question_id"] for a in calls[0][2]} == {q["id"] for q in questions}
    assert all("question" in a and "score" in a and "flags" in a for a in calls[0][2])

    assert client.post("/diagnostic/submit", headers=headers, json={"answers": answers}).status_code == 409
    assert len(calls) == 1
    assert client.delete("/diagnostic/me", headers=headers).status_code == 200
    assert client.get("/reports/me", headers=headers).status_code == 404
    assert client.post("/diagnostic/submit", headers=headers, json={"answers": answers}).status_code == 200
    assert len(calls) == 2


@pytest.mark.parametrize("error", [ValueError("Invalid guidance"), httpx.ReadTimeout("Timed out")])
def test_guidance_failure_still_saves_diagnostic(client, monkeypatch, error):
    def fail(*args):
        raise error

    monkeypatch.setattr("app.routes.diagnostic.generate_guidance", fail, raising=False)
    headers, _ = login(client, "sara@northwind.test", "Northwind Logistics")
    _, answers = make_complete_payload(client, headers)
    assert client.post("/diagnostic/submit", headers=headers, json={"answers": answers}).status_code == 200
    report = client.get("/reports/me", headers=headers).json()
    assert report["answered"] == len(answers)
    assert report["feedback"] is None
    assert report["next_steps"] == []


@pytest.mark.parametrize("result", [
    {"feedback": "", "next_steps": ["Review your draft."]},
    {"feedback": "x" * 601, "next_steps": ["Review your draft."]},
    {"feedback": "Feedback", "next_steps": []},
    {"feedback": "Feedback", "next_steps": ["Action"] * 4},
    {"feedback": "Feedback", "next_steps": [" "]},
    {"feedback": "Feedback", "next_steps": ["x" * 241]},
    {"feedback": "Feedback", "next_steps": [123]},
    {"feedback": "Feedback", "next_steps": ["Review"], "score": 5},
    ["unexpected response shape"],
])
def test_invalid_provider_guidance_is_rejected(monkeypatch, result):
    from app.services import guidance

    monkeypatch.setattr(guidance, "AI_MODE", "live")
    monkeypatch.setattr(guidance.llm, "chat_completion", lambda *args, **kwargs: json.dumps(result))
    with pytest.raises(ValueError):
        guidance.generate_guidance("support", "junior", [])


def test_guidance_provider_receives_only_selected_diagnostic_context(monkeypatch):
    from app.services import guidance

    captured = []

    def provider(messages, **kwargs):
        captured.extend(messages)
        return json.dumps({"feedback": " You report reviewing drafts. ",
                           "next_steps": [" Check factual claims before sending. "]})

    monkeypatch.setattr(guidance, "AI_MODE", "live")
    monkeypatch.setattr(guidance.llm, "chat_completion", provider)
    answers = [{"question_id": "common-open", "question": "What did you do?",
                "answer": "I checked a draft.", "score": 4, "flags": []}]
    result = guidance.generate_guidance("support", "junior", answers)
    assert result["feedback"] == "You report reviewing drafts."
    assert result["next_steps"] == ["Check factual claims before sending."]
    assert captured[0]["role"] == "system"
    context = json.loads(captured[1]["content"])
    assert context == {"job_role": "support", "seniority": "junior", "answers": answers}


def test_saved_guidance_is_scoped_to_selected_organization(client, monkeypatch):
    calls = []

    def generate(*args):
        calls.append(args)
        return {"feedback": f"Guidance for submission {len(calls)}.", "next_steps": ["Review one draft."]}

    monkeypatch.setattr("app.routes.diagnostic.generate_guidance", generate)
    _, session = login(client, "ravi@consult.test")
    saved = []
    for organization in session["organizations"]:
        selected = client.post("/auth/select-org", json={"org_id": organization["org_id"]},
                               headers={"Authorization": f"Bearer {session['token']}"})
        headers = {"Authorization": f"Bearer {selected.json()['token']}"}
        _, answers = make_complete_payload(client, headers)
        assert client.post("/diagnostic/submit", headers=headers, json={"answers": answers}).status_code == 200
        saved.append((headers, f"Guidance for submission {len(calls)}."))

    for headers, expected in saved:
        assert client.get("/reports/me", headers=headers).json()["feedback"] == expected
    assert client.delete("/diagnostic/me", headers=saved[0][0]).status_code == 200
    assert client.get("/reports/me", headers=saved[0][0]).status_code == 404
    assert client.get("/reports/me", headers=saved[1][0]).json()["feedback"] == saved[1][1]
