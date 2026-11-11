import hashlib
import hmac
import secrets
import time
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from core.config import Settings, get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def session_token(settings: Settings) -> str:
    body = f"{int(time.time()) + settings.browser_session_hours * 3600}.{secrets.token_hex(16)}"
    signature = hmac.new(
        settings.api_key.get_secret_value().encode(), body.encode(), hashlib.sha256
    ).hexdigest()
    return body + "." + signature


def valid_session(token: str, settings: Settings) -> bool:
    try:
        expires, nonce, signature = token.split(".")
        body = expires + "." + nonce
        expected = hmac.new(
            settings.api_key.get_secret_value().encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        return int(expires) > time.time() and hmac.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


def require_api_key(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    x_api_key: Annotated[str | None, Security(api_key_header)] = None,
) -> None:
    if x_api_key is not None:
        if secrets.compare_digest(x_api_key.encode(), settings.api_key.get_secret_value().encode()):
            return
        raise HTTPException(401, "Invalid API key")
    token = request.cookies.get("fk_session", "")
    if valid_session(token, settings):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if (origin and origin != str(request.base_url).rstrip("/")) or request.headers.get(
                "sec-fetch-site"
            ) == "cross-site":
                raise HTTPException(403, "Cross-origin browser actions are not allowed")
        return
    raise HTTPException(status_code=401, detail="Invalid or missing API key")
