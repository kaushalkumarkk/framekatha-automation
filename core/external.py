"""Bounded retries for external providers with redacted failure persistence."""

import logging
import time
from collections.abc import Callable
from typing import TypeVar
from uuid import uuid4

import httpx

from core.db import get_session_factory
from core.logging import request_id_context
from core.models import DeadLetter

T = TypeVar("T")
logger = logging.getLogger(__name__)


class ProviderUnavailable(Exception):
    pass


class ConfigurationRequired(Exception):
    pass


def call_provider(operation: str, call: Callable[[], T], attempts: int = 3) -> T:
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except (httpx.HTTPError, ValueError) as error:
            status = (
                error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
            )
            retryable = status is None or status in {408, 409, 429} or status >= 500
            logger.warning("provider_attempt_failed", extra={"attempt": attempt})
            if retryable and attempt < attempts:
                time.sleep(min(2 ** (attempt - 1), 4))
                continue
            try:
                with get_session_factory().begin() as db:
                    db.add(
                        DeadLetter(
                            job_type=operation,
                            request_id=request_id_context.get() or str(uuid4()),
                            payload={"operation": operation},
                            error_code="provider_failure",
                            error_message="Provider request failed; inspect provider configuration",
                            attempt_count=attempt,
                        )
                    )
            except Exception:
                logger.error("dead_letter_storage_unavailable")
            raise ProviderUnavailable(operation) from None
    raise ProviderUnavailable(operation)
