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


def test_dashboard_and_employee_report_use_the_same_maturity_level(client):
    from app import models
    from app.db import SessionLocal

    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email="vikram@northwind.test").one()
        membership = db.query(models.Membership).filter_by(user_id=user.id).one()
        db.query(models.Response).filter_by(membership_id=membership.id).update(
            {"score": 3.75}, synchronize_session=False
        )
        db.commit()

    employee_headers, _ = login(client, "vikram@northwind.test", "Northwind Logistics")
    report = client.get("/reports/me", headers=employee_headers).json()
    admin_headers, session = login(client, "asha@northwind.test", "Northwind Logistics")
    org_id = session["organizations"][0]["org_id"]
    dashboard = client.get(f"/dashboard?org_id={org_id}", headers=admin_headers).json()
    sales = next(dept for dept in dashboard["departments"] if dept["department"] == "Sales")

    assert report["average_score"] == sales["average_score"] == 3.75
    assert report["level"] == sales["level"] == "Practitioner"


def test_dashboard_counts_each_employee_once_per_risk(client):
    from app import models
    from app.db import SessionLocal

    with SessionLocal() as db:
        for email in ("priya@northwind.test", "vikram@northwind.test"):
            user = db.query(models.User).filter_by(email=email).one()
            membership = db.query(models.Membership).filter_by(user_id=user.id).one()
            rows = db.query(models.Response).filter_by(membership_id=membership.id).all()
            for row in rows:
                row.flags = None
            rows[0].flags = ["customer_data_shared", "customer_data_shared"]
            rows[1].flags = ["customer_data_shared"]
            if email == "priya@northwind.test":
                rows[1].flags = ["customer_data_shared", "unreviewed_output"]
        db.commit()

    headers, session = login(client, "asha@northwind.test", "Northwind Logistics")
    org_id = session["organizations"][0]["org_id"]
    response = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert response.status_code == 200
    assert dict(response.json()["top_risks"]) == {
        "customer_data_shared": 2,
        "unreviewed_output": 1,
    }

    employee_headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    assert client.delete("/diagnostic/me", headers=employee_headers).status_code == 200
    response = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert dict(response.json()["top_risks"]) == {"customer_data_shared": 1}
