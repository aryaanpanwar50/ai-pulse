import hashlib

import pytest

from app.auth import hash_password, verify_password
from app import models
from app.db import SessionLocal


def test_password_hashes_use_random_salts_and_detect_tampering():
    first = hash_password("same-password")
    second = hash_password("same-password")
    assert first != second
    assert first.startswith("sha256$")
    assert len(first) <= 200  # Fits the existing password_hash column.
    assert verify_password("same-password", first)
    assert verify_password("same-password", second)
    assert not verify_password("wrong-password", first)
    algorithm, salt, digest = first.split("$")
    changed_salt = ("0" if salt[0] != "0" else "1") + salt[1:]
    assert not verify_password("same-password", f"{algorithm}${changed_salt}${digest}")


def test_salted_hash_preserves_unicode_and_password_whitespace():
    password = "  caf\u00e9-\u5b89\u5168  "
    hashed = hash_password(password)
    assert verify_password(password, hashed)
    assert not verify_password(password.strip(), hashed)


@pytest.mark.parametrize("hashed", ["", "sha256$invalid$salt", "sha256$" + "0" * 32 + "$broken", "unsupported$abc$def"])
def test_malformed_password_hashes_are_rejected(hashed):
    assert verify_password("pulse123", hashed) is False


def test_legacy_login_upgrades_only_after_success_and_keeps_salted_hash_stable(client):
    legacy = hashlib.sha256(b"pulse123").hexdigest()
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email="priya@northwind.test").one()
        user.password_hash = legacy
        user_id = user.id
        db.commit()

    assert client.post("/auth/login", json={"email": "priya@northwind.test", "password": "wrong"}).status_code == 401
    with SessionLocal() as db:
        assert db.get(models.User, user_id).password_hash == legacy

    assert client.post("/auth/login", json={"email": "priya@northwind.test", "password": "pulse123"}).status_code == 200
    with SessionLocal() as db:
        salted = db.get(models.User, user_id).password_hash
        assert salted.startswith("sha256$")
        assert verify_password("pulse123", salted)
        assert db.query(models.Membership).filter_by(user_id=user_id).count() == 1

    assert client.post("/auth/login", json={"email": "priya@northwind.test", "password": "pulse123"}).status_code == 200
    with SessionLocal() as db:
        assert db.get(models.User, user_id).password_hash == salted
