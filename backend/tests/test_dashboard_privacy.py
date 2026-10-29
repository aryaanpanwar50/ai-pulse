import pytest

from tests.conftest import login


def dashboard(client):
    headers, session = login(client, "asha@northwind.test", "Northwind Logistics")
    org_id = session["organizations"][0]["org_id"]
    response = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize("completed", [0, 1, 4])
def test_small_departments_withhold_scores_levels_and_risks(client, add_completed_respondents, completed):
    add_completed_respondents("Engineering", completed, score=4, flags=["confidential_data_shared"])
    data = dashboard(client)
    department = next(d for d in data["departments"] if d["department"] == "Engineering")
    assert department["responded"] == completed
    assert department["suppressed"] is True
    assert department["average_score"] is None
    assert department["level"] is None
    assert data["top_risks"] == []
    assert data["risk_summary_available"] is False
    assert data["minimum_respondents"] == 5


def test_five_distinct_completions_release_results_without_small_team_risks(client, add_completed_respondents):
    add_completed_respondents("Engineering", 5, score=4, flags=["unreviewed_output"])
    data = dashboard(client)
    engineering = next(d for d in data["departments"] if d["department"] == "Engineering")
    assert engineering["responded"] == 5  # Many answer rows still represent only five people.
    assert engineering["suppressed"] is False
    assert engineering["average_score"] == 4
    assert engineering["level"] == "Leader"
    assert dict(data["top_risks"]) == {"unreviewed_output": 5}
    assert data["risk_summary_available"] is True
    assert data["risk_summary_scope"] == "departments_meeting_minimum_responses"

    # Priya's suppressed Support data remains available in her own report.
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    report = client.get("/reports/me", headers=headers)
    assert report.status_code == 200
    assert report.json()["average_score"] is not None
    assert "customer_data_shared" in report.json()["risks"]
    assert "customer_data_shared" not in dict(data["top_risks"])


def test_deleting_fifth_response_suppresses_department_and_removes_its_risks(client, add_completed_respondents):
    add_completed_respondents("Support", 4, flags=["unreviewed_output"])
    before = dashboard(client)
    assert dict(before["top_risks"]) == {"customer_data_shared": 1, "unreviewed_output": 4}
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    assert client.delete("/diagnostic/me", headers=headers).status_code == 200
    after = dashboard(client)
    support = next(d for d in after["departments"] if d["department"] == "Support")
    assert support["responded"] == 4
    assert support["suppressed"] is True
    assert support["average_score"] is None
    assert support["level"] is None
    assert after["top_risks"] == []
    assert after["risk_summary_available"] is False


def test_eligible_department_without_risks_is_distinct_from_suppressed_summary(client, add_completed_respondents):
    add_completed_respondents("Engineering", 5)
    data = dashboard(client)
    assert data["risk_summary_available"] is True
    assert data["top_risks"] == []


def test_other_organization_cannot_make_department_eligible(client, add_completed_respondents):
    add_completed_respondents("Stores", 5, flags=["confidential_data_shared"], org_name="Bluepeak Retail")
    data = dashboard(client)
    assert all(d["suppressed"] for d in data["departments"])
    assert data["top_risks"] == []
