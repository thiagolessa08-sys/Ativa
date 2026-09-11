from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .analytics import Filters, deliveries, filter_options, finance, fleet, operations, overview
from .chat_service import ask
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
