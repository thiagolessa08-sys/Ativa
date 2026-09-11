from __future__ import annotations

import hashlib
import hmac
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .analytics import Filters, deliveries, filter_options, finance, fleet, operations, overview
from .chat_service import ask
from .config import settings
from .db import query_one
from .sftp_service import latest_transfer_costs, source_status


app = FastAPI(title="Ativa Command Center API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

SESSION_COOKIE = "ativa_session"
PUBLIC_API_PATHS = {"/api/health", "/api/auth/login", "/api/auth/logout", "/api/auth/me"}


def _session_token(username: str, expires_at: int) -> str:
    payload = f"{username}|{expires_at}"
    secret = settings.dashboard_auth_secret or settings.dashboard_password
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{signature}"


def _session_user(token: str | None) -> str | None:
    if not token or not settings.dashboard_password:
        return None
    try:
        username, expires_raw, signature = token.rsplit("|", 2)
        expires_at = int(expires_raw)
    except (ValueError, TypeError):
        return None
    if expires_at < int(time.time()):
        return None
    expected = _session_token(username, expires_at).rsplit("|", 1)[1]
    if not hmac.compare_digest(signature, expected):
        return None
    return username if hmac.compare_digest(username, settings.dashboard_user) else None


@app.middleware("http")
async def protect_api(request: Request, call_next: Any) -> Response:
    if request.url.path.startswith("/api/") and request.url.path not in PUBLIC_API_PATHS:
        if not _session_user(request.cookies.get(SESSION_COOKIE)):
            return JSONResponse({"detail": "Sessão não autenticada."}, status_code=401)
    return await call_next(request)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


@app.post("/api/auth/login")
def login(payload: LoginRequest, response: Response) -> dict[str, Any]:
    if not settings.dashboard_password:
        raise HTTPException(503, "O acesso ao dashboard ainda não foi configurado.")
    valid_user = hmac.compare_digest(payload.username, settings.dashboard_user)
    valid_password = hmac.compare_digest(payload.password, settings.dashboard_password)
    if not (valid_user and valid_password):
        raise HTTPException(401, "Usuário ou senha inválidos.")
    max_age = max(settings.dashboard_session_hours, 1) * 3600
    expires_at = int(time.time()) + max_age
    response.set_cookie(
        SESSION_COOKIE,
        _session_token(settings.dashboard_user, expires_at),
        max_age=max_age,
        httponly=True,
        secure=settings.dashboard_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"authenticated": True, "username": settings.dashboard_user}


@app.post("/api/auth/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"authenticated": False}


@app.get("/api/auth/me")
def auth_me(request: Request, response: Response) -> dict[str, Any]:
    username = _session_user(request.cookies.get(SESSION_COOKIE))
    response.headers["Cache-Control"] = "no-store"
    return {"authenticated": bool(username), "username": username}


def make_filters(
    start: date | None,
    end: date | None,
    branch: str | None,
    uf: str | None,
    segment: str | None,
) -> Filters:
    options = filter_options()
    resolved_end = end or date.fromisoformat(options["max_date"])
    resolved_start = start or resolved_end - timedelta(days=29)
    if resolved_start > resolved_end:
        raise HTTPException(422, "A data inicial deve ser anterior à data final.")
    return Filters(resolved_start, resolved_end, branch or None, uf or None, segment or None)


def common_params(
    start: date | None = Query(None),
    end: date | None = Query(None),
    branch: str | None = Query(None),
    uf: str | None = Query(None),
    segment: str | None = Query(None),
) -> Filters:
    return make_filters(start, end, branch, uf, segment)


@app.get("/api/health")
def health() -> dict[str, Any]:
    try:
        db = query_one("select current_database() as database, (select max(data_ref) from ctrc) as last_data")
        return {"ok": True, "database": db}
    except Exception as exc:
        raise HTTPException(503, f"Banco indisponível: {type(exc).__name__}") from exc


@app.get("/api/filters")
def filters_endpoint() -> dict[str, Any]:
    return filter_options()


@app.get("/api/overview")
def overview_endpoint(start: date | None = None, end: date | None = None, branch: str | None = None, uf: str | None = None, segment: str | None = None) -> dict[str, Any]:
    return overview(make_filters(start, end, branch, uf, segment))


@app.get("/api/operations")
def operations_endpoint(start: date | None = None, end: date | None = None, branch: str | None = None, uf: str | None = None, segment: str | None = None) -> dict[str, Any]:
    return operations(make_filters(start, end, branch, uf, segment))


@app.get("/api/deliveries")
def deliveries_endpoint(start: date | None = None, end: date | None = None, branch: str | None = None, uf: str | None = None, segment: str | None = None) -> dict[str, Any]:
    return deliveries(make_filters(start, end, branch, uf, segment))


@app.get("/api/finance")
def finance_endpoint(start: date | None = None, end: date | None = None, branch: str | None = None, uf: str | None = None, segment: str | None = None) -> dict[str, Any]:
    return finance(make_filters(start, end, branch, uf, segment))


@app.get("/api/fleet")
def fleet_endpoint(start: date | None = None, end: date | None = None, branch: str | None = None, uf: str | None = None, segment: str | None = None) -> dict[str, Any]:
    result = fleet(make_filters(start, end, branch, uf, segment))
    try:
        result["transfer_costs"] = latest_transfer_costs()
    except Exception as exc:
        result["transfer_costs"] = {"error": type(exc).__name__, "routes": [], "summary": {}}
    return result


@app.get("/api/sources")
def sources_endpoint() -> dict[str, Any]:
    db = query_one("select count(*) as row_count, min(data_ref) as min_date, max(data_ref) as max_date from ctrc")
    try:
        transfer = source_status()
    except Exception as exc:
        transfer = {"ok": False, "error": type(exc).__name__, "folders": []}
    return {"database": {"ok": True, "rows": db["row_count"], "min_date": db["min_date"], "max_date": db["max_date"]}, "transfer": transfer}


class ChatRequest(BaseModel):
    message: str = Field(min_length=3, max_length=1000)
    filters: dict[str, Any] | None = None


@app.post("/api/chat")
def chat_endpoint(payload: ChatRequest) -> dict[str, Any]:
    try:
        return ask(payload.message, payload.filters)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Não foi possível responder: {type(exc).__name__}") from exc


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
