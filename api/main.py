import logging
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from api.auth import require_api_key
from api.routes.leads import router
from api.routes.scrapers import router as scrapers_router
from core.config import get_settings
from core.db import get_session_factory
from core.logging import configure_logging, request_id_context


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(get_settings().log_level)
    yield


app = FastAPI(title="Frame Katha Studio Automation", version="0.1.0", lifespan=lifespan)
app.include_router(router)
app.include_router(scrapers_router)
logger = logging.getLogger(__name__)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = str(uuid4())
    token = request_id_context.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "http_request_completed",
            extra={
                "method": request.method,
                "status_code": response.status_code,
            },
        )
        return response
    finally:
        request_id_context.reset(token)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Pydantic's default errors may echo submitted contacts or credentials.
    details = [
        {"loc": error["loc"], "type": error["type"], "msg": "Invalid value"}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": details})


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    logger.error("database_unavailable")
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"], dependencies=[Depends(require_api_key)])
def ready(factory: Annotated[sessionmaker, Depends(get_session_factory)]):
    with factory() as session:
        session.execute(text("SELECT 1"))
    return {"status": "ready"}
