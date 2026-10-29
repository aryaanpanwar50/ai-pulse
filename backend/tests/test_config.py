import pytest

from app.config import (
    _required_setting,
    _validate_frontend_url,
    _validate_secret,
)


def test_required_setting_does_not_use_a_default(monkeypatch):
    for name in (
        "SECRET_KEY",
        "DATABASE_URL",
        "AI_MODE",
        "LLM_API_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
        "TOKEN_HOURS",
        "FRONTEND_URL",
    ):
        monkeypatch.delenv(name, raising=False)
        with pytest.raises(RuntimeError, match=name):
            _required_setting(name, allow_empty=name.startswith("LLM_"))


def test_jwt_secret_must_be_at_least_32_bytes():
    with pytest.raises(RuntimeError, match="32 bytes"):
        _validate_secret("short")
    assert _validate_secret("x" * 32) == "x" * 32


def test_frontend_url_must_be_one_explicit_origin():
    assert _validate_frontend_url(" https://pulse.example.com/ ") == "https://pulse.example.com"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "*",
        "ftp://pulse.example.com",
        "https://pulse.example.com/dashboard",
        "https://user@pulse.example.com",
        "https://pulse.example.com:bad",
        "https://pulse .example.com",
    ],
)
def test_frontend_url_rejects_invalid_origins(value):
    with pytest.raises(RuntimeError, match="FRONTEND_URL"):
        _validate_frontend_url(value)
