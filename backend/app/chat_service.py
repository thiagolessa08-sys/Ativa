from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, timedelta
from typing import Any

import sqlglot
from sqlglot import exp

from .config import settings
from .db import query


ALLOWED_TABLES = {"ctrc", "ctrc_unid_passagem", "manifesto", "ocorrencia"}
BLOCKED_FUNCTIONS = {"pg_sleep", "dblink", "lo_import", "lo_export", "pg_read_file", "pg_ls_dir"}
BLOCKED_COLUMNS = {"cgc_pag", "cgc_emit", "cgc_dest", "c_chave_fis", "endereco_volume", "instrucao_entrega"}

SCHEMA = """
PostgreSQL 9.6, tabelas somente leitura:
- ctrc: cada linha é um conhecimento/CT-e. Datas: data_ref, data_prev_ent, data_entrega. Valores: vlr_frete, vlr_merc, qtde_vol, peso_calculo. Origem/destino: sigla_fil_emit, sigla_fil_atual, sigla_fil_dest, uf_origem, uf_dest, cidade_origem, cidade_dest. Clientes: nome_cli_pag, nome_cli_emit, nome_cli_dest. Segmento: segmento_pag. Última ocorrência: ult_ocor, data_ult_ocor.
- ocorrencia: codigo, descricao, tp_entrega. Relacione ocorrencia.codigo = ctrc.ult_ocor.
- manifesto: viagens de transferência; data_inclusao, data_prev_chegada, data_chegada, placa_cavalo, marca, modelo, nome_motorista, cidade_origem, cidade_dest, uf_dest, sigla_fil_dest.
- ctrc_unid_passagem: passagens do conhecimento por filial; seq_ctrc, sigla_fil_ent, data_armazem, data_saida, situacao.
Regras: entregue quando data_entrega IS NOT NULL; no prazo quando data_entrega <= data_prev_ent; atrasado em aberto quando data_entrega IS NULL e data_prev_ent < CURRENT_DATE. Receita = SUM(vlr_frete).
"""


def _plain(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _period(message: str, filters: dict[str, Any] | None) -> tuple[date, date]:
    today = date.today()
    if filters and filters.get("start") and filters.get("end"):
        return date.fromisoformat(filters["start"]), date.fromisoformat(filters["end"])
    text = _plain(message)
    match = re.search(r"ultim[oa]s?\s+(\d{1,3})\s+dias", text)
    if match:
        days = min(int(match.group(1)), 366)
        return today - timedelta(days=days - 1), today
    months = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
    for name, month in months.items():
        if name in text:
            year_match = re.search(r"20\d{2}", text)
            year = int(year_match.group()) if year_match else today.year
            start = date(year, month, 1)
            end = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
            return start, end
    return today - timedelta(days=29), today


def _filter_sql(filters: dict[str, Any] | None, params: dict[str, Any]) -> str:
    clauses = ["c.data_ref between %(start)s and %(end)s"]
    if filters:
        if filters.get("branch"):
            clauses.append("trim(c.sigla_fil_emit)=%(branch)s")
            params["branch"] = filters["branch"]
        if filters.get("uf"):
            clauses.append("trim(c.uf_dest)=%(uf)s")
            params["uf"] = filters["uf"]
        if filters.get("segment"):
            clauses.append("trim(c.segmento_pag)=%(segment)s")
            params["segment"] = filters["segment"]
    return " and ".join(clauses)


def fallback_plan(message: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    text = _plain(message)
    start, end = _period(message, filters)
    params: dict[str, Any] = {"start": start, "end": end}
    where = _filter_sql(filters, params)
    if any(word in text for word in ("cliente", "pagador")) and any(word in text for word in ("top", "maior", "ranking")):
        sql = f"select trim(c.nome_cli_pag) cliente, count(*) conhecimentos, round(sum(c.vlr_frete),2) receita from ctrc c where {where} and c.nome_cli_pag is not null group by 1 order by receita desc limit 15"
        return {"title": "Clientes por receita", "sql": sql, "params": params, "chart_type": "bar"}
    if "rota" in text or ("origem" in text and "destino" in text):
        sql = f"select trim(c.sigla_fil_emit)||' - '||trim(c.sigla_fil_dest) rota, count(*) conhecimentos, round(sum(c.vlr_frete),2) receita from ctrc c where {where} group by 1 order by conhecimentos desc limit 15"
        return {"title": "Rotas com maior movimento", "sql": sql, "params": params, "chart_type": "bar"}
    if "filial" in text or "filiais" in text or "unidade" in text:
        sql = f"select trim(c.sigla_fil_emit) filial, count(*) conhecimentos, round(sum(c.vlr_frete),2) receita, round(100.0*count(*) filter(where c.data_entrega is not null and c.data_entrega<=c.data_prev_ent)/nullif(count(*) filter(where c.data_entrega is not null),0),1) sla from ctrc c where {where} group by 1 order by conhecimentos desc limit 20"
        return {"title": "Desempenho por filial", "sql": sql, "params": params, "chart_type": "bar"}
    if "ocorr" in text or "motivo" in text:
        sql = f"select coalesce(o.descricao,'Sem descrição') ocorrencia, count(*) conhecimentos from ctrc c left join ocorrencia o on o.codigo=c.ult_ocor where {where} group by 1 order by conhecimentos desc limit 15"
        return {"title": "Ocorrências mais frequentes", "sql": sql, "params": params, "chart_type": "bar"}
    if "manifest" in text or "viagem" in text or "motorista" in text or "veiculo" in text or "frota" in text:
        sql = "select count(*) manifestos, count(distinct trim(placa_cavalo)) veiculos, count(distinct seq_motorista) motoristas, round(100.0*count(*) filter(where data_chegada is not null and data_chegada<=data_prev_chegada)/nullif(count(*) filter(where data_chegada is not null),0),1) sla from manifesto where data_inclusao between %(start)s and %(end)s"
        return {"title": "Resumo de transferências", "sql": sql, "params": params, "chart_type": "number"}
    if "atras" in text:
        sql = f"select count(*) entregas_atrasadas, round(sum(c.vlr_frete),2) receita_em_risco from ctrc c where {where} and c.data_entrega is null and c.data_prev_ent < %(end)s"
        return {"title": "Entregas atrasadas", "sql": sql, "params": params, "chart_type": "number"}
    if any(word in text for word in ("receita", "faturamento", "frete", "valor")):
        sql = f"select round(sum(c.vlr_frete),2) receita_frete, count(*) conhecimentos, round(avg(c.vlr_frete),2) ticket_medio from ctrc c where {where}"
        return {"title": "Receita de frete", "sql": sql, "params": params, "chart_type": "number"}
    if "sla" in text or "prazo" in text or "pontual" in text:
        sql = f"select count(*) filter(where c.data_entrega is not null) entregues, count(*) filter(where c.data_entrega<=c.data_prev_ent) no_prazo, round(100.0*count(*) filter(where c.data_entrega<=c.data_prev_ent)/nullif(count(*) filter(where c.data_entrega is not null),0),1) sla from ctrc c where {where}"
        return {"title": "Nível de serviço", "sql": sql, "params": params, "chart_type": "number"}
    sql = f"select count(*) conhecimentos, count(*) filter(where c.data_entrega is not null) entregues, round(sum(c.vlr_frete),2) receita, sum(c.qtde_vol) volumes from ctrc c where {where}"
    return {"title": "Resumo operacional", "sql": sql, "params": params, "chart_type": "number"}


def llm_plan(message: str, filters: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if not settings.openai_api_key:
        return None
    from openai import OpenAI
    kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    client = OpenAI(**kwargs)
    filter_context = json.dumps(filters or {}, ensure_ascii=False)
    response = client.responses.create(
        model=settings.openai_model,
        instructions=(
            "Você é analista de BI da Ativa Logística. Gere uma única consulta PostgreSQL SELECT para responder à pergunta. "
            "Use somente as tabelas e colunas fornecidas, nunca exponha CNPJ, chaves fiscais, endereços ou dados pessoais. "
            "Prefira agregações, aplique LIMIT 200 em resultados detalhados e escreva aliases em português sem espaços. "
            "A data atual é " + date.today().isoformat() + ".\n" + SCHEMA
        ),
        input=f"Filtros ativos: {filter_context}\nPergunta: {message}",
        reasoning={"effort": "low"},
        text={"format": {
            "type": "json_schema",
            "name": "sql_plan",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "sql": {"type": "string"},
                    "chart_type": {"type": "string", "enum": ["number", "bar", "line", "table"]},
                    "explanation": {"type": "string"},
                },
                "required": ["title", "sql", "chart_type", "explanation"],
                "additionalProperties": False,
            },
        }},
        store=False,
    )
    return json.loads(response.output_text)


def validate_sql(sql: str) -> str:
    if not sql or ";" in sql.rstrip().rstrip(";") or "--" in sql or "/*" in sql:
        raise ValueError("A consulta deve conter um único SELECT sem comentários.")
    clean = sql.strip().rstrip(";")
    parseable = re.sub(r"%\([A-Za-z_][A-Za-z0-9_]*\)s", "'2026-01-01'", clean)
    tree = sqlglot.parse_one(parseable, read="postgres")
    if not isinstance(tree, (exp.Select, exp.Union)):
        raise ValueError("Somente consultas SELECT são permitidas.")
    tables = {table.name.lower() for table in tree.find_all(exp.Table)}
    if not tables or not tables.issubset(ALLOWED_TABLES):
        raise ValueError("A consulta usa uma fonte não permitida.")
    functions = {func.sql_name().lower() for func in tree.find_all(exp.Func)}
    if functions & BLOCKED_FUNCTIONS:
        raise ValueError("A consulta usa uma função não permitida.")
    columns = {column.name.lower() for column in tree.find_all(exp.Column)}
    if columns & BLOCKED_COLUMNS:
        raise ValueError("A consulta tentou acessar um campo sensível.")
    for select in tree.find_all(exp.Select):
        if any(isinstance(item, exp.Star) or (isinstance(item, exp.Column) and item.name == "*") for item in select.expressions):
            raise ValueError("Consultas com SELECT * não são permitidas.")
    if not tree.args.get("limit"):
        clean += " LIMIT 200"
    return clean


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if isinstance(value, int):
        return f"{value:,}".replace(",", ".")
    return str(value)


def ask(message: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    provider = "OpenAI" if settings.openai_api_key else "analisador local"
    plan = llm_plan(message, filters) or fallback_plan(message, filters)
    sql = validate_sql(plan["sql"])
    data = query(sql, plan.get("params"))
    if not data:
        answer = "Não encontrei registros para esse recorte."
    elif len(data) == 1:
        parts = [f"{key.replace('_',' ')}: {_format_value(value)}" for key, value in data[0].items()]
        answer = ". ".join(parts) + "."
    else:
        answer = f"Encontrei {len(data)} resultados. A tabela e o gráfico abaixo mostram o ranking solicitado."
    return {
        "title": plan["title"],
        "answer": answer,
        "explanation": plan.get("explanation", "Consulta criada a partir da pergunta e dos filtros ativos."),
        "sql": sql,
        "data": data,
        "chart_type": plan.get("chart_type", "table"),
        "provider": provider,
    }
