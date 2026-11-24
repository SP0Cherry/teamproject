"""Symmetric encryption for stored third-party MCP server tokens (SEC-07/08).

The user-provided server token is encrypted at rest with Fernet (AES-128-CBC +
HMAC). The key is derived from ``MCP_SERVER_TOKEN_ENCRYPT_KEY`` via SHA-256 so
any non-empty secret works. Plaintext tokens never appear in responses or logs.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet_key() -> bytes:
    digest = hashlib.sha256(settings.mcp_server_token_encrypt_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(plain: str) -> str:
    return Fernet(_fernet_key()).encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(cipher: str) -> str | None:
    try:
        return Fernet(_fernet_key()).decrypt(cipher.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None
