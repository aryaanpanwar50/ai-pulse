import os
from urllib.parse import urlsplit

from dotenv import load_dotenv

# Load local settings without replacing values supplied by the process environment.
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(_env_path, override=False)

def _required_setting(name: str, *, allow_empty: bool = False) -> str:
    value = os.getenv(name)
    if value is None or (not allow_empty and not value.strip()):
        raise RuntimeError(f"Required configuration setting {name} is missing")
    return value.strip()


def _validate_secret(secret: str) -> str:
    if len(secret.encode("utf-8")) < 32:
        raise RuntimeError("SECRET_KEY must contain at least 32 bytes")
    return secret


def _validate_frontend_url(raw_origin: str) -> str:
    origin = raw_origin.strip().rstrip("/")
    if not origin or "," in origin or "*" in origin or any(c.isspace() for c in origin):
        raise RuntimeError("FRONTEND_URL must be one explicit web origin")

    parsed = urlsplit(origin)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or "?" in origin
        or "#" in origin
    ):
        raise RuntimeError("FRONTEND_URL must be an HTTP(S) origin without credentials, path, query, or fragment")

    try:
        parsed.port
    except ValueError as exc:
        raise RuntimeError("FRONTEND_URL contains an invalid port") from exc
    return origin


SECRET_KEY = _validate_secret(_required_setting("SECRET_KEY"))
DATABASE_URL = _required_setting("DATABASE_URL")
AI_MODE = _required_setting("AI_MODE").lower()
if AI_MODE not in {"mock", "live"}:
    raise RuntimeError("AI_MODE must be either 'mock' or 'live'")

LLM_API_URL = _required_setting("LLM_API_URL", allow_empty=True)
LLM_API_KEY = _required_setting("LLM_API_KEY", allow_empty=True)
LLM_MODEL = _required_setting("LLM_MODEL", allow_empty=True)
if AI_MODE == "live" and not all((LLM_API_URL, LLM_API_KEY, LLM_MODEL)):
    raise RuntimeError("LLM_API_URL, LLM_API_KEY, and LLM_MODEL are required when AI_MODE=live")

try:
    TOKEN_HOURS = int(_required_setting("TOKEN_HOURS"))
except ValueError as exc:
    raise RuntimeError("TOKEN_HOURS must be a positive integer") from exc
if TOKEN_HOURS <= 0:
    raise RuntimeError("TOKEN_HOURS must be a positive integer")

FRONTEND_URL = _validate_frontend_url(_required_setting("FRONTEND_URL"))
