import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from core.config import Settings, get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_api_key: Annotated[str | None, Security(api_key_header)] = None,
) -> None:
    if x_api_key is None or not secrets.compare_digest(
        x_api_key.encode(), settings.api_key.get_secret_value().encode()
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
