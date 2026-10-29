import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from . import models
from .config import SECRET_KEY, TOKEN_HOURS
from .db import get_db


def hash_password(password: str) -> str:
    """Store the scheme, a random 16-byte salt, and the salted SHA-256 digest."""
    salt = secrets.token_bytes(16)
    digest = hashlib.sha256(salt + password.encode("utf-8")).hexdigest()
    return f"sha256${salt.hex()}${digest}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        # Older accounts have only a digest, without a salt or separator.
        if "$" not in hashed:
            digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
            return hmac.compare_digest(digest, hashed)

        algorithm, salt_hex, stored_digest = hashed.split("$")
        salt = bytes.fromhex(salt_hex)
        if algorithm != "sha256" or len(salt) != 16:
            return False
        digest = hashlib.sha256(salt + password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(digest, stored_digest)
    except (ValueError, TypeError, AttributeError):
        # Malformed stored values should fail login rather than crash it.
        return False


def make_token(user_id: int, org_id: int | None = None) -> str:
    payload = {
        "sub": str(user_id),
        "org": org_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def _decode(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        return jwt.decode(authorization[7:], SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")


def current_user(
    authorization: str | None = Header(None), db: Session = Depends(get_db)
) -> models.User:
    data = _decode(authorization)
    user = db.get(models.User, int(data["sub"]))
    if not user:
        raise HTTPException(401, "Unknown user")
    return user


def current_membership(
    authorization: str | None = Header(None), db: Session = Depends(get_db)
) -> models.Membership:
    """The membership for the organization selected after login."""
    data = _decode(authorization)
    if not data.get("org"):
        raise HTTPException(400, "Select an organization first")
    m = (
        db.query(models.Membership)
        .filter_by(user_id=int(data["sub"]), org_id=data["org"])
        .first()
    )
    if not m:
        raise HTTPException(403, "Not a member of this organization")
    return m
