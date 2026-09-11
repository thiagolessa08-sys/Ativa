"""Valida as duas fontes de dados sem alterar ou transferir arquivos."""
import os
import sys

import paramiko
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def testar_bi() -> bool:
    print("\nServidor BI · PostgreSQL")
    try:
        conn = psycopg2.connect(
            host=os.getenv("BI_HOST"),
            port=int(os.getenv("BI_PORT", "5432")),
            dbname=os.getenv("BI_DATABASE"),
            user=os.getenv("BI_USER"),
            password=os.getenv("BI_PASSWORD"),
            connect_timeout=10,
        )
        with conn.cursor() as cur:
            cur.execute("select count(*), min(data_ref), max(data_ref) from ctrc")
            count, first, last = cur.fetchone()
        conn.close()
        print(f"[ OK ] {count:,} conhecimentos · {first} a {last}")
        return True
    except Exception as exc:
        print(f"[FALHA] {type(exc).__name__}: {exc}")
        return False


def testar_bi2() -> bool:
    print("\nServidor BI2 · SFTP")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            os.getenv("BI2_HOST"),
            port=int(os.getenv("BI2_PORT") or "22"),
            username=os.getenv("BI2_USER"),
            password=os.getenv("BI2_PASSWORD"),
            timeout=10,
            allow_agent=False,
            look_for_keys=False,
        )
        sftp = client.open_sftp()
        folders = sftp.listdir("/")
        sftp.close()
        print(f"[ OK ] {len(folders)} pastas: {', '.join(sorted(folders))}")
        return True
    except Exception as exc:
        print(f"[FALHA] {type(exc).__name__}: {exc}")
        return False
    finally:
        client.close()


if __name__ == "__main__":
    target = sys.argv[1].lower() if len(sys.argv) > 1 else "todos"
    results = []
    if target in ("todos", "bi"):
        results.append(testar_bi())
    if target in ("todos", "bi2"):
        results.append(testar_bi2())
    raise SystemExit(0 if all(results) else 1)
