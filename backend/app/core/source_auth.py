"""Notification source authentication via shared secrets (SEC-13).

Sources must present a valid source token. Tokens are configured per source.
No user session is used for source ingress.
"""

from fastapi import Header

from app.core.response import ApiError

# Source name -> shared secret. In production these come from secret manager.
SOURCE_SECRETS = {
    "demo-source": "demo-secret-change-me",
    "email": "email-secret-change-me",
}


def verify_source(source: str = Header(...), x_source_token: str = Header(...)) -> str:
    """Validate notification source credentials. Returns source name."""
    expected = SOURCE_SECRETS.get(source)
    if expected is None or x_source_token != expected:
        raise ApiError(code="AUTH_INVALID", message="invalid source credentials")
    return source
