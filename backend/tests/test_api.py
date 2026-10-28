from tests.conftest import login


def test_login_lists_organizations(client):
    _, data = login(client, "ravi@consult.test")
    names = {o["org_name"] for o in data["organizations"]}
    assert names == {"Northwind Logistics", "Bluepeak Retail"}


def test_cors_allows_configured_frontend_origin(client):
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_cors_does_not_allow_unconfigured_origin(client):
    response = client.options(
        "/health",
        headers={
            "Origin": "https://unknown.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_does_not_allow_unconfigured_method(client):
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PATCH",
        },
    )
    assert response.status_code == 400


def test_employee_sees_questions(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    r = client.get("/diagnostic/questions", headers=headers)
    assert r.status_code == 200
    assert any(q["id"] == "sup-drafts" for q in r.json())


def test_admin_dashboard(client):
    headers, data = login(client, "asha@northwind.test", "Northwind Logistics")
    org_id = data["organizations"][0]["org_id"]
    r = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["departments"]) == 4


def test_dashboard_uses_completed_people_and_employee_level_averages(client):
    headers, data = login(client, "asha@northwind.test", "Northwind Logistics")
    org_id = data["organizations"][0]["org_id"]
    response = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert response.status_code == 200

    departments = {dept["department"]: dept for dept in response.json()["departments"]}
    assert departments["Sales"]["responded"] == 1
    assert departments["Sales"]["average_score"] == 3.29
    assert departments["Engineering"]["responded"] == 0
    assert departments["Engineering"]["average_score"] is None


def test_admin_cannot_see_other_org(client):
    northwind_headers, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    _, bluepeak = login(client, "meera@bluepeak.test", "Bluepeak Retail")
    bluepeak_id = bluepeak["organizations"][0]["org_id"]
    r = client.get(f"/dashboard?org_id={bluepeak_id}", headers=northwind_headers)
    assert r.status_code == 403
