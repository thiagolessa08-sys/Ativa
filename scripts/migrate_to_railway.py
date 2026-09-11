"""Copia as tabelas do SSW para um PostgreSQL de destino e cria índices.

Uso:
    $env:RAILWAY_DATABASE_URL="postgresql://..."
    python scripts/migrate_to_railway.py

O processo transmite os dados diretamente entre os dois bancos, sem gravar
arquivos intermediários e sem alterar o banco SSW.
"""
from __future__ import annotations

import argparse
import os
import threading
import time
from contextlib import closing
from pathlib import Path

import psycopg2
from dotenv import dotenv_values
from psycopg2 import sql


ROOT = Path(__file__).resolve().parents[1]
TABLES = ("ocorrencia", "manifesto", "ctrc", "ctrc_unid_passagem")

INDEXES = (
    "create unique index if not exists ux_ocorrencia_codigo on ocorrencia (codigo)",
    "create unique index if not exists ux_manifesto_seq on manifesto (seq_manifesto)",
    "create index if not exists ix_manifesto_periodo on manifesto (data_inclusao)",
    "create index if not exists ix_manifesto_periodo_destino on manifesto (data_inclusao, sigla_fil_dest)",
    "create index if not exists ix_manifesto_placa on manifesto (placa_cavalo)",
    "create index if not exists ix_ctrc_seq on ctrc (seq_ctrc)",
    "create index if not exists ix_ctrc_periodo on ctrc (data_ref)",
    "create index if not exists ix_ctrc_periodo_filial on ctrc (data_ref, sigla_fil_emit)",
    "create index if not exists ix_ctrc_periodo_destino on ctrc (data_ref, uf_dest)",
    "create index if not exists ix_ctrc_periodo_segmento on ctrc (data_ref, segmento_pag)",
    "create index if not exists ix_ctrc_periodo_cliente on ctrc (data_ref, nome_cli_pag)",
    "create index if not exists ix_ctrc_filial_destino on ctrc (sigla_fil_emit, sigla_fil_dest, data_ref)",
    "create index if not exists ix_ctrc_ocorrencia on ctrc (ult_ocor)",
    "create index if not exists ix_ctrc_manifesto on ctrc (seq_manifesto) where seq_manifesto is not null",
    "create index if not exists ix_ctrc_pendencias on ctrc (data_prev_ent, sigla_fil_atual) where data_entrega is null",
    "create unique index if not exists ux_ctrc_passagem on ctrc_unid_passagem (seq_ctrc, cod_fil_ent)",
    "create index if not exists ix_ctrc_passagem_seq on ctrc_unid_passagem (seq_ctrc)",
    "create index if not exists ix_ctrc_passagem_filial on ctrc_unid_passagem (cod_fil_ent, data_armazem)",
)


def source_connection():
    env = dotenv_values(ROOT / ".env")
    conn = psycopg2.connect(
        host=env["BI_HOST"],
        port=int(env.get("BI_PORT") or 5432),
        dbname=env["BI_DATABASE"],
        user=env["BI_USER"],
        password=env["BI_PASSWORD"],
        connect_timeout=15,
        application_name="ativa_railway_migration_source",
    )
    conn.set_client_encoding("LATIN1")
    return conn


def target_connection(url: str):
    conn = psycopg2.connect(url, connect_timeout=20, application_name="ativa_railway_migration_target")
    conn.set_client_encoding("LATIN1")
    return conn


def table_definition(source, table: str) -> tuple[list[str], str]:
    with source.cursor() as cur:
        cur.execute(
            """
            select a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod), a.attnotnull
            from pg_catalog.pg_attribute a
            join pg_catalog.pg_class c on c.oid=a.attrelid
            join pg_catalog.pg_namespace n on n.oid=c.relnamespace
            where n.nspname='public' and c.relname=%s and a.attnum>0 and not a.attisdropped
            order by a.attnum
            """,
            (table,),
        )
        fields = cur.fetchall()
    columns = [name for name, _, _ in fields]
    declarations = [
        sql.SQL("{} {}{}").format(
            sql.Identifier(name),
            sql.SQL(data_type),
            sql.SQL(" not null" if not_null else ""),
        )
        for name, data_type, not_null in fields
    ]
    ddl = sql.SQL("create table if not exists {} ({})").format(
        sql.Identifier(table), sql.SQL(", ").join(declarations)
    ).as_string(source)
    return columns, ddl


def stream_table(source, target, table: str, columns: list[str]) -> None:
    quoted = sql.SQL(",").join(map(sql.Identifier, columns)).as_string(source)
    copy_out = f"copy {table} ({quoted}) to stdout with (format csv, delimiter E'\\t', null '\\N', quote E'\\b')"
    copy_in = f"copy {table} ({quoted}) from stdin with (format csv, delimiter E'\\t', null '\\N', quote E'\\b')"
    read_fd, write_fd = os.pipe()
    error: list[BaseException] = []

    def produce() -> None:
        try:
            with os.fdopen(write_fd, "wb", buffering=0) as writer, source.cursor() as cur:
                cur.copy_expert(copy_out, writer, size=1024 * 1024)
        except BaseException as exc:
            error.append(exc)
            try:
                os.close(write_fd)
            except OSError:
                pass

    producer = threading.Thread(target=produce, name=f"copy-{table}", daemon=True)
    producer.start()
    try:
        with os.fdopen(read_fd, "rb", buffering=0) as reader, target.cursor() as cur:
            cur.copy_expert(copy_in, reader, size=1024 * 1024)
    finally:
        producer.join()
    if error:
        raise error[0]


def count(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(sql.SQL("select count(*) from {}").format(sql.Identifier(table)))
        return cur.fetchone()[0]


def migrate(target_url: str, replace: bool = False) -> None:
    started = time.monotonic()
    with closing(source_connection()) as source, closing(target_connection(target_url)) as target:
        target.autocommit = False
        with target.cursor() as cur:
            cur.execute("set statement_timeout=0")
            cur.execute("set lock_timeout='30s'")

        for table in TABLES:
            columns, ddl = table_definition(source, table)
            with target.cursor() as cur:
                cur.execute(ddl)
                cur.execute(sql.SQL("select count(*) from {}").format(sql.Identifier(table)))
                existing = cur.fetchone()[0]
                if existing and not replace:
                    raise RuntimeError(f"A tabela {table} já contém {existing} registros. Use --replace para recarregar.")
                if existing:
                    cur.execute(sql.SQL("truncate table {}").format(sql.Identifier(table)))
            target.commit()

            source_rows = count(source, table)
            print(f"{table}: copiando {source_rows:,} registros...", flush=True)
            table_started = time.monotonic()
            stream_table(source, target, table, columns)
            target.commit()
            target_rows = count(target, table)
            if target_rows != source_rows:
                raise RuntimeError(f"Contagem divergente em {table}: origem={source_rows}, destino={target_rows}")
            print(f"{table}: OK em {(time.monotonic()-table_started)/60:.1f} min", flush=True)

        print("Criando índices para o dashboard...", flush=True)
        for statement in INDEXES:
            with target.cursor() as cur:
                cur.execute(statement)
            target.commit()
        with target.cursor() as cur:
            for table in TABLES:
                cur.execute(sql.SQL("analyze {}").format(sql.Identifier(table)))
        target.commit()
        print(f"Migração concluída em {(time.monotonic()-started)/60:.1f} min.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-url", default=os.getenv("RAILWAY_DATABASE_URL"))
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if not args.target_url:
        parser.error("Informe --target-url ou RAILWAY_DATABASE_URL")
    migrate(args.target_url, args.replace)
