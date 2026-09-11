from __future__ import annotations

import csv
import io
from datetime import datetime
from functools import lru_cache
from time import time
from typing import Any

import paramiko

from .config import settings


FOLDERS = ("ctrc", "caixa", "cliente", "caminhao", "tabelas")
_cached_sources: tuple[float, dict[str, Any]] | None = None


def _connect() -> tuple[paramiko.SSHClient, paramiko.SFTPClient]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        settings.bi2_host,
        port=settings.bi2_port,
        username=settings.bi2_user,
        password=settings.bi2_password,
        timeout=12,
        allow_agent=False,
        look_for_keys=False,
    )
    return client, client.open_sftp()


def source_status() -> dict[str, Any]:
    global _cached_sources
    if _cached_sources and time() - _cached_sources[0] < 180:
        return _cached_sources[1]
    client, sftp = _connect()
    try:
        folders = []
        for folder in FOLDERS:
            attrs = [a for a in sftp.listdir_attr(f"/{folder}") if not a.filename.startswith(".")]
            latest = max(attrs, key=lambda a: a.st_mtime) if attrs else None
            folders.append({
                "folder": folder,
                "files": len(attrs),
                "latest_file": latest.filename if latest else None,
                "latest_at": datetime.fromtimestamp(latest.st_mtime).isoformat() if latest else None,
                "latest_size": latest.st_size if latest else 0,
            })
        result = {"ok": True, "host": settings.bi2_host, "protocol": "SFTP", "folders": folders}
    finally:
        sftp.close()
        client.close()
    _cached_sources = (time(), result)
    return result


def latest_transfer_costs() -> dict[str, Any]:
    client, sftp = _connect()
    try:
        attrs = [a for a in sftp.listdir_attr("/caminhao") if a.filename.startswith("0220_D_")]
        if not attrs:
            return {"file": None, "routes": [], "summary": {}}
        latest = max(attrs, key=lambda a: a.st_mtime)
        with sftp.open(f"/caminhao/{latest.filename}", "rb") as remote:
            text = remote.read().decode("latin-1", "replace")
    finally:
        sftp.close()
        client.close()
    records = list(csv.reader(io.StringIO(text), delimiter=";"))
    if len(records) < 3:
        return {"file": latest.filename, "routes": [], "summary": {}}
    header = [h.strip() for h in records[1]]
    parsed: list[dict[str, str]] = []
    for row in records[2:]:
        if not row or not any(cell.strip() for cell in row):
            continue
        parsed.append({header[i]: row[i].strip() if i < len(row) else "" for i in range(len(header))})

    def number(value: str) -> float:
        try:
            return float(value.replace(".", "").replace(",", ".").strip() or 0)
        except ValueError:
            return 0.0

    grouped: dict[str, dict[str, float]] = {}
    for item in parsed:
        route = f"{item.get('UnidEmissao','?')} → {item.get('UnidDestino','?')}"
        row = grouped.setdefault(route, {"trips": 0, "cost": 0, "freight": 0, "tons": 0})
        row["trips"] += 1
        row["cost"] += number(item.get("ValorCTRB/OS", "0"))
        row["freight"] += number(item.get("ValorFreteProp", "0"))
        row["tons"] += number(item.get("tonCALC", "0"))
    routes = [{"route": route, **values} for route, values in grouped.items()]
    routes.sort(key=lambda item: item["cost"], reverse=True)
    return {
        "file": latest.filename,
        "updated_at": datetime.fromtimestamp(latest.st_mtime).isoformat(),
        "summary": {
            "trips": len(parsed),
            "cost": round(sum(r["cost"] for r in routes), 2),
            "freight": round(sum(r["freight"] for r in routes), 2),
            "tons": round(sum(r["tons"] for r in routes), 2),
        },
        "routes": routes[:15],
    }
