"""Cree (ou recree) la base dialette_lab a partir de sql/lab_schema.sql.

Detruit le contenu de dialette_lab si elle existe deja. Refuse tout nom de base qui ne se
termine pas par _lab, donc ne peut jamais toucher la base de l'application.
"""
import sys

from common import ROOT, connect_lab, lab_db_name


def main():
    name = lab_db_name()
    ddl = (ROOT / "sql" / "lab_schema.sql").read_text(encoding="utf-8")
    # Commentaires retires avant le decoupage : un bloc peut commencer par un commentaire.
    ddl = "\n".join(ln for ln in ddl.splitlines() if not ln.strip().startswith("--"))
    cleaned = [s.strip() for s in ddl.split(";") if s.strip()]

    conn = connect_lab(with_database=False)
    with conn.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS `{name}`")
        cur.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cur.execute(f"USE `{name}`")
        for stmt in cleaned:
            cur.execute(stmt)
        cur.execute("SHOW TABLES")
        print(f"base {name} creee, tables :", ", ".join(r[0] for r in cur.fetchall()))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
