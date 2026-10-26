"""Utilitaires partages : lecture du .env et connexions MariaDB."""
import os
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parent.parent


def load_env(path=None):
    """Charge .env s'il existe. .env.example n'est jamais lu."""
    path = Path(path) if path else ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def _cfg(prefix):
    return dict(
        host=os.environ.get(f"{prefix}_DB_HOST", "127.0.0.1"),
        port=int(os.environ.get(f"{prefix}_DB_PORT", "3306")),
        user=os.environ.get(f"{prefix}_DB_USER", "root"),
        password=os.environ.get(f"{prefix}_DB_PASSWORD", ""),
        charset="utf8mb4",
    )


def connect_source():
    """Base Dialette, en lecture seule (transaction READ ONLY)."""
    load_env()
    cfg = _cfg("SOURCE")
    conn = pymysql.connect(database=os.environ.get("SOURCE_DB_NAME", "dialette"), **cfg)
    with conn.cursor() as cur:
        cur.execute("SET SESSION TRANSACTION READ ONLY")
    return conn


def lab_db_name():
    load_env()
    name = os.environ.get("LAB_DB_NAME", "dialette_lab")
    if not name.endswith("_lab"):
        raise SystemExit(f"Refus : LAB_DB_NAME={name!r} ne se termine pas par _lab.")
    return name


def connect_lab(with_database=True):
    load_env()
    cfg = _cfg("LAB")
    if with_database:
        cfg["database"] = lab_db_name()
    return pymysql.connect(**cfg)
