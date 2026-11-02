"""FastAPI application entry point."""
from __future__ import annotations

import logging
import hmac

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from backend.config import settings
from backend.database import Base, SessionLocal, engine
from backend.ml.predictor import get_predictor
from backend.models.entities import ModelVersion, User
from backend.routes.api import router
from backend.utils.security import hash_password, read_csrf_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("sepsiguard")

app = FastAPI(title=settings.app_name, version="1.0.0", description="Research and decision-support API. Not for diagnosis or treatment decisions.")
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, expose_headers=["Content-Disposition"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "X-CSRF-Token"],
)
app.include_router(router)


@app.middleware("http")
async def csrf_guard(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path != "/api/auth/login":
        token = request.cookies.get(settings.session_cookie)
        if token:
            expected = read_csrf_token(token)
            supplied = request.headers.get("X-CSRF-Token", "")
            if expected and not hmac.compare_digest(expected, supplied):
                return JSONResponse(status_code=403, content={"success": False, "error": {"code": "CSRF_INVALID", "message": "Session request token is missing or invalid."}})
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"success": False, "error": {"code": "INVALID_INPUT", "message": "Request validation failed.", "details": jsonable_encoder(exc.errors())}})


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    message = detail if isinstance(detail, str) else detail.get("message", "The request could not be completed.") if isinstance(detail, dict) else str(detail)
    issues = detail.get("issues", detail.get("errors", [])) if isinstance(detail, dict) else []
    code = "INVALID_INPUT" if exc.status_code == 422 else "REQUEST_ERROR"
    return JSONResponse(status_code=exc.status_code, content={"success": False, "error": {"code": code, "message": message, "details": issues}})


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled API error")
    return JSONResponse(status_code=500, content={"success": False, "error": {"code": "INTERNAL_ERROR", "message": "The request could not be completed."}})


@app.on_event("startup")
def startup():
    if settings.environment == "production" and settings.secret_key == "change-this-local-secret-before-deployment":
        raise RuntimeError("Set SECRET_KEY before starting in production.")
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if settings.bootstrap_admin_email and settings.bootstrap_admin_password:
            if len(settings.bootstrap_admin_password) < 12:
                raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must contain at least 12 characters.")
            if db.scalar(select(User).where(User.email == settings.bootstrap_admin_email)) is None:
                db.add(User(email=settings.bootstrap_admin_email, full_name=settings.bootstrap_admin_name, role="administrator", password_hash=hash_password(settings.bootstrap_admin_password)))
                logger.info("Created initial administrator account from bootstrap environment.")
        predictor = get_predictor()
        model_version = db.scalar(select(ModelVersion).where(ModelVersion.version == predictor.version))
        if model_version is None:
            db.add(ModelVersion(version=predictor.version, status=predictor.status, artifact_path=str(settings.model_path), metadata_json={"clinical_validation": False, "synthetic_data": predictor.synthetic_data}))
        else:
            model_version.status = predictor.status
        db.commit()


@app.get("/api/health")
def health():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"success": True, "status": "ok", "service": "sepsiguard-api"}
