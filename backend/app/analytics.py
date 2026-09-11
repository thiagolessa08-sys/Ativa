from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from functools import wraps
from threading import Lock
from time import monotonic
from typing import Any, Callable

from psycopg2.extras import RealDictCursor

from .db import connection, json_value, query, query_one, rows


_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = Lock()


def cached(ttl: int = 90):
    def decorator(fn: Callable[..., Any]):
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            key = f"{fn.__name__}:{args!r}:{sorted(kwargs.items())!r}"
            now = monotonic()
            with _cache_lock:
                item = _cache.get(key)
                if item and now - item[0] < ttl:
                    return item[1]
            value = fn(*args, **kwargs)
            with _cache_lock:
                _cache[key] = (now, value)
            return value
        return wrapper
    return decorator


@dataclass(frozen=True)
class Filters:
    start: date
    end: date
    branch: str | None = None
    uf: str | None = None
    segment: str | None = None

    @property
    def days(self) -> int:
        return max((self.end - self.start).days + 1, 1)

    @property
    def previous(self) -> tuple[date, date]:
        previous_end = self.start - timedelta(days=1)
        return previous_end - timedelta(days=self.days - 1), previous_end


def _where(f: Filters, alias: str = "c", date_column: str = "data_ref") -> tuple[str, dict[str, Any]]:
    clauses = [f"{alias}.{date_column} between %(start)s and %(end)s"]
    params: dict[str, Any] = {"start": f.start, "end": f.end}
    if f.branch:
        clauses.append(f"trim({alias}.sigla_fil_emit) = %(branch)s")
        params["branch"] = f.branch
    if f.uf:
        clauses.append(f"trim({alias}.uf_dest) = %(uf)s")
        params["uf"] = f.uf
    if f.segment:
        clauses.append(f"trim({alias}.segmento_pag) = %(segment)s")
        params["segment"] = f.segment
    return " and ".join(clauses), params


def _pct_change(current: float | int | None, previous: float | int | None) -> float | None:
    current = float(current or 0)
    previous = float(previous or 0)
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


@cached(300)
def filter_options() -> dict[str, Any]:
    meta = query_one("select min(data_ref) min_date, max(data_ref) max_date from ctrc")
    max_date = date.fromisoformat(meta["max_date"])
    return {
        **meta,
        "default_start": (max_date - timedelta(days=29)).isoformat(),
        "branches": [r["option_value"] for r in query("select distinct trim(sigla_fil_emit) as option_value from ctrc where sigla_fil_emit is not null order by 1")],
        "states": [r["option_value"] for r in query("select distinct trim(uf_dest) as option_value from ctrc where uf_dest is not null order by 1")],
        "segments": [r["option_value"] for r in query("select distinct trim(segmento_pag) as option_value from ctrc where segmento_pag is not null order by 1")],
    }


def _aggregate(cur: Any, f: Filters, start: date, end: date) -> dict[str, Any]:
    local = Filters(start, end, f.branch, f.uf, f.segment)
    where, params = _where(local)
    cur.execute(f"""
        select
            count(*) shipments,
            count(*) filter (where c.data_entrega is not null) delivered,
            count(*) filter (where c.data_entrega is not null and c.data_prev_ent is not null and c.data_entrega <= c.data_prev_ent) on_time,
            count(*) filter (where c.data_entrega is null and c.data_prev_ent < %(end)s) delayed,
            coalesce(sum(c.vlr_frete),0) revenue,
            coalesce(sum(c.qtde_vol),0) volumes,
            coalesce(sum(c.peso_calculo),0) weight,
            coalesce(avg(c.vlr_frete),0) avg_ticket,
            coalesce(avg(c.data_entrega-c.data_ref) filter (where c.data_entrega is not null),0) avg_transit
        from ctrc c where {where}
    """, params)
    raw = dict(cur.fetchone())
    data = {k: json_value(v) for k, v in raw.items()}
    data["sla"] = round((data["on_time"] / data["delivered"] * 100), 1) if data["delivered"] else 0
    return data


@cached(90)
def overview(f: Filters) -> dict[str, Any]:
    where, params = _where(f)
    prev_start, prev_end = f.previous
    with connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            current = _aggregate(cur, f, f.start, f.end)
            previous = _aggregate(cur, f, prev_start, prev_end)
            cur.execute(f"""
                select c.data_ref date, count(*) shipments,
                    count(*) filter(where c.data_entrega is not null) delivered,
                    count(*) filter(where c.data_entrega is not null and c.data_prev_ent is not null and c.data_entrega <= c.data_prev_ent) on_time,
                    count(*) filter(where c.data_entrega is null and c.data_prev_ent < %(end)s) delayed,
                    coalesce(sum(c.vlr_frete),0) revenue,
                    coalesce(sum(c.qtde_vol),0) volumes,
                    coalesce(sum(c.peso_calculo),0) weight,
                    coalesce(avg(c.vlr_frete),0) avg_ticket,
                    coalesce(avg(c.data_entrega-c.data_ref) filter(where c.data_entrega is not null),0) avg_transit
                from ctrc c where {where}
                group by 1 order by 1
            """, params)
            trend = rows(cur)
            cur.execute(f"""
                select trim(c.sigla_fil_emit) branch, count(*) shipments,
                    coalesce(sum(c.vlr_frete),0) revenue,
                    count(*) filter(where c.data_entrega is null and c.data_prev_ent < %(end)s) delayed,
                    round(100.0 * count(*) filter(where c.data_entrega is not null and c.data_entrega <= c.data_prev_ent)
                      / nullif(count(*) filter(where c.data_entrega is not null),0),1) sla
                from ctrc c where {where}
                group by 1 order by shipments desc limit 8
            """, params)
            branches = rows(cur)
            cur.execute(f"""
                select trim(c.uf_dest) uf, count(*) shipments,
                    coalesce(sum(c.vlr_frete),0) revenue
                from ctrc c where {where}
                group by 1 order by shipments desc limit 10
            """, params)
            states = rows(cur)
            cur.execute(f"""
                select coalesce(o.descricao, trim(c.sigla_ult_ocor), 'Sem ocorrencia') as occurrence_label,
                    count(*) as occurrence_count
                from ctrc c left join ocorrencia o on o.codigo=c.ult_ocor
                where {where} and c.data_entrega is null
                group by 1 order by 2 desc limit 7
            """, params)
            occurrences = rows(cur)
    comparisons = {key: _pct_change(current.get(key), previous.get(key)) for key in ("shipments", "delivered", "revenue", "volumes")}
    comparisons["sla"] = round(current["sla"] - previous["sla"], 1)
    return {"kpis": current, "previous": previous, "comparisons": comparisons, "trend": trend, "branches": branches, "states": states, "occurrences": occurrences}


@cached(90)
def operations(f: Filters) -> dict[str, Any]:
    where, params = _where(f)
    branch_filter = ""
    if f.branch:
        branch_filter = " and trim(m.sigla_fil_dest)=%(branch)s"
    return {
        "branches": query(f"""
            select trim(c.sigla_fil_emit) branch, count(*) shipments,
                coalesce(sum(c.qtde_vol),0) volumes, round(coalesce(sum(c.peso_calculo),0)/1000,1) tons,
                coalesce(sum(c.vlr_frete),0) revenue,
                count(*) filter(where c.data_entrega is null and c.data_prev_ent < %(end)s) delayed,
                round(100.0*count(*) filter(where c.data_entrega is not null and c.data_entrega<=c.data_prev_ent)/nullif(count(*) filter(where c.data_entrega is not null),0),1) sla
            from ctrc c where {where} group by 1 order by shipments desc
        """, params),
        "routes": query(f"""
            select trim(c.sigla_fil_emit)||' - '||trim(c.sigla_fil_dest) as route,
                count(*) shipments, round(coalesce(sum(c.peso_calculo),0)/1000,1) tons,
                coalesce(sum(c.vlr_frete),0) revenue,
                round(avg(c.data_entrega-c.data_ref) filter(where c.data_entrega is not null),1) transit_days
            from ctrc c where {where} group by 1 order by shipments desc limit 15
        """, params),
        "hourly": query(f"""
            select extract(hour from c.hora_ref)::int as hour_of_day, count(*) shipments
            from ctrc c where {where} group by 1 order by 1
        """, params),
        "manifest_flow": query(f"""
            select trim(m.sigla_fil_dest) destination, count(*) manifests,
                count(*) filter(where m.data_chegada is not null) arrived,
                count(*) filter(where m.data_chegada is null and m.data_prev_chegada < %(end)s) delayed
            from manifesto m
            where m.data_inclusao between %(start)s and %(end)s{branch_filter}
            group by 1 order by manifests desc limit 12
        """, params),
    }


@cached(90)
def deliveries(f: Filters) -> dict[str, Any]:
    where, params = _where(f)
    return {
        "sla_trend": query(f"""
            select c.data_ref date,
                round(100.0*count(*) filter(where c.data_entrega is not null and c.data_entrega<=c.data_prev_ent)/nullif(count(*) filter(where c.data_entrega is not null),0),1) sla,
                count(*) filter(where c.data_entrega is null and c.data_prev_ent < %(end)s) delayed
            from ctrc c where {where} group by 1 order by 1
        """, params),
        "lateness": query(f"""
            select bucket, count(*) as bucket_count from (
                select case
                    when c.data_entrega is null and %(end)s-c.data_prev_ent > 7 then 'Mais de 7 dias'
                    when c.data_entrega is null and %(end)s-c.data_prev_ent between 4 and 7 then '4 a 7 dias'
                    when c.data_entrega is null and %(end)s-c.data_prev_ent between 2 and 3 then '2 a 3 dias'
                    when c.data_entrega is null and %(end)s-c.data_prev_ent = 1 then '1 dia'
                    else 'No prazo' end bucket
                from ctrc c where {where}
            ) x group by 1 order by case bucket when 'Mais de 7 dias' then 1 when '4 a 7 dias' then 2 when '2 a 3 dias' then 3 when '1 dia' then 4 else 5 end
        """, params),
        "occurrences": query(f"""
            select coalesce(o.descricao,trim(c.sigla_ult_ocor),'Sem ocorrência') occurrence,
                count(*) shipments, min(c.data_prev_ent) oldest_due,
                count(distinct trim(c.sigla_fil_atual)) branches
            from ctrc c left join ocorrencia o on o.codigo=c.ult_ocor
            where {where} and c.data_entrega is null
            group by 1 order by shipments desc limit 15
        """, params),
        "destination_cities": query(f"""
            select trim(c.cidade_dest)||' / '||trim(c.uf_dest) city, count(*) shipments,
                count(*) filter(where c.data_entrega is null and c.data_prev_ent < %(end)s) delayed,
                round(100.0*count(*) filter(where c.data_entrega is not null and c.data_entrega<=c.data_prev_ent)/nullif(count(*) filter(where c.data_entrega is not null),0),1) sla
            from ctrc c where {where} group by 1 order by shipments desc limit 15
        """, params),
        "destination_states": query(f"""
            select trim(c.uf_dest) uf, count(*) shipments,
                count(*) filter(where c.data_entrega is null and c.data_prev_ent < %(end)s) delayed,
                round(100.0*count(*) filter(where c.data_entrega is not null and c.data_entrega<=c.data_prev_ent)/nullif(count(*) filter(where c.data_entrega is not null),0),1) sla,
                coalesce(sum(c.vlr_frete),0) revenue
            from ctrc c where {where} and c.uf_dest is not null
            group by 1 order by shipments desc
        """, params),
    }


@cached(90)
def finance(f: Filters) -> dict[str, Any]:
    where, params = _where(f)
    return {
        "monthly": query(f"""
            select to_char(date_trunc('month',c.data_ref),'YYYY-MM') as period,
                count(*) shipments, coalesce(sum(c.vlr_frete),0) revenue,
                coalesce(sum(c.vlr_merc),0) merchandise,
                round(avg(c.vlr_frete),2) avg_ticket
            from ctrc c where {where} group by 1 order by 1
        """, params),
        "customers": query(f"""
            select trim(c.nome_cli_pag) customer, count(*) shipments,
                coalesce(sum(c.vlr_frete),0) revenue, round(avg(c.vlr_frete),2) avg_ticket,
                coalesce(sum(c.vlr_merc),0) merchandise
            from ctrc c where {where} and c.nome_cli_pag is not null
            group by 1 order by revenue desc limit 20
        """, params),
        "segments": query(f"""
            select coalesce(nullif(trim(c.segmento_pag),''),'Não informado') segment,
                count(*) shipments, coalesce(sum(c.vlr_frete),0) revenue
            from ctrc c where {where} group by 1 order by revenue desc limit 15
        """, params),
        "states": query(f"""
            select trim(c.uf_dest) uf, count(*) shipments, coalesce(sum(c.vlr_frete),0) revenue,
                round(avg(c.vlr_frete),2) avg_ticket
            from ctrc c where {where} group by 1 order by revenue desc
        """, params),
    }


@cached(90)
def fleet(f: Filters) -> dict[str, Any]:
    clauses = ["m.data_inclusao between %(start)s and %(end)s"]
    params: dict[str, Any] = {"start": f.start, "end": f.end}
    if f.branch:
        clauses.append("trim(m.sigla_fil_dest)=%(branch)s")
        params["branch"] = f.branch
    if f.uf:
        clauses.append("trim(m.uf_dest)=%(uf)s")
        params["uf"] = f.uf
    where = " and ".join(clauses)
    kpis = query_one(f"""
        select count(*) manifests, count(distinct trim(m.placa_cavalo)) vehicles,
            count(distinct m.seq_motorista) drivers,
            count(*) filter(where m.data_chegada is not null) arrived,
            count(*) filter(where m.data_chegada is not null and m.data_prev_chegada is not null and m.data_chegada<=m.data_prev_chegada) on_time,
            round(avg(m.data_chegada-m.data_inclusao) filter(where m.data_chegada is not null),1) avg_transit
        from manifesto m where {where}
    """, params)
    arrived = kpis.get("arrived") or 0
    kpis["sla"] = round((kpis.get("on_time") or 0) / arrived * 100, 1) if arrived else 0
    return {
        "kpis": kpis,
        "routes": query(f"""
            select trim(m.cidade_origem)||' - '||trim(m.cidade_dest) as route,
                count(*) manifests, count(distinct trim(m.placa_cavalo)) vehicles,
                round(avg(m.data_chegada-m.data_inclusao) filter(where m.data_chegada is not null),1) avg_transit
            from manifesto m where {where} group by 1 order by manifests desc limit 15
        """, params),
        "vehicles": query(f"""
            select trim(m.placa_cavalo) vehicle, max(trim(m.marca)||' '||trim(m.modelo)) model,
                count(*) trips, count(distinct trim(m.sigla_fil_dest)) destinations,
                round(avg(m.data_chegada-m.data_inclusao) filter(where m.data_chegada is not null),1) avg_transit
            from manifesto m where {where} and m.placa_cavalo is not null
            group by 1 order by trips desc limit 20
        """, params),
        "drivers": query(f"""
            select trim(m.nome_motorista) driver, count(*) trips,
                count(distinct trim(m.placa_cavalo)) vehicles,
                round(100.0*count(*) filter(where m.data_chegada is not null and m.data_chegada<=m.data_prev_chegada)/nullif(count(*) filter(where m.data_chegada is not null),0),1) sla
            from manifesto m where {where} and m.nome_motorista is not null
            group by 1 order by trips desc limit 15
        """, params),
    }
