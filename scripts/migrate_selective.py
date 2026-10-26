"""Migration selective MariaDB (dialette_lab) vers MongoDB (dialette_lab) : configuration B.

Tables migrees : messages, widget_views, et conversations.meta (collection conversation_answers).
Le noyau transactionnel reste dans MariaDB et n'est jamais modifie par ce script.

Proprietes :
- par lots (--batch), pagination par cle (id > dernier id), donc cout constant par lot ;
- idempotent : _id MongoDB = id d'origine et ecriture par ReplaceOne(upsert=True) ;
- reprise : un point de reprise (dernier id ecrit) est enregistre dans la collection
  _migration_state apres chaque lot ecrit. Une interruption ne perd au pire qu'un lot, rejoue
  sans effet grace a l'idempotence. --restart ignore le point de reprise ;
- --dry-run : lit, convertit et compte (dont ce qui serait insere ou remplace), n'ecrit rien,
  ne cree ni index ni collection ;
- journal : une ligne par lot et un resume par table (duree, debit) dans output/migration_<volume>.jsonl.

Limite connue : la reprise ne detecte pas les lignes modifiees ou supprimees dans la source
en dessous du point de reprise. Pour resynchroniser, utiliser --restart.
"""
import argparse
import datetime as dt
import json
import sys
import time

import pymongo
from pymongo import ReplaceOne

from common import ROOT, connect_lab, connect_mongo, lab_db_name, mongo_db_name

STATE = "_migration_state"

# Pour chaque table : collection cible, requete source paginee par id, conversion ligne -> document.
TABLES = {
    "messages": {
        "collection": "messages",
        "sql": "SELECT id, conversation_id, sender_type, sender_id, sender_role, content, read_at, "
               "created_at, updated_at, deleted_at FROM messages WHERE id > %s ORDER BY id LIMIT %s",
        "convert": lambda r: {"_id": r[0], "conversation_id": r[1], "sender_type": r[2], "sender_id": r[3],
                              "sender_role": r[4], "content": r[5], "read_at": r[6], "created_at": r[7],
                              "updated_at": r[8], "deleted_at": r[9]},
    },
    "widget_views": {
        "collection": "widget_views",
        "sql": "SELECT id, widget_id, created_at FROM widget_views WHERE id > %s ORDER BY id LIMIT %s",
        "convert": lambda r: {"_id": r[0], "widget_id": r[1], "created_at": r[2]},
    },
    "conversation_answers": {
        "collection": "conversation_answers",
        "sql": "SELECT id, meta FROM conversations WHERE meta IS NOT NULL AND id > %s ORDER BY id LIMIT %s",
        "convert": lambda r: {"_id": r[0], "answers": json.loads(r[1])},
    },
}

# Index equivalents a ceux de MariaDB (voir docs/methodo.md). Aucun index sur widget_views.created_at.
INDEXES = {
    "messages": [
        ([("conversation_id", 1), ("created_at", 1)], "messages_conversation_id_created_at_index"),
        ([("sender_type", 1), ("sender_id", 1)], "messages_sender_type_sender_id_index"),
    ],
    "widget_views": [([("widget_id", 1)], "widget_views_widget_id_foreign")],
    "conversation_answers": [],
}


def log(fh, **event):
    event["ts"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    line = json.dumps(event, ensure_ascii=False)
    fh.write(line + "\n")
    fh.flush()
    print(line)


def migrate_table(name, spec, src, db, args, fh):
    state = db[STATE]
    coll = db[spec["collection"]]
    saved = state.find_one({"_id": name})
    last_id = 0 if args.restart or not saved else saved["last_id"]
    rows_done = 0 if args.restart or not saved else saved["rows_done"]
    resumed_from = last_id
    t0 = time.perf_counter()
    read = inserted = replaced = unchanged = would_insert = would_replace = batches = 0
    log(fh, event="table_start", table=name, dry_run=args.dry_run, resumed_from=resumed_from, batch=args.batch)

    cur = src.cursor()
    while True:
        cur.execute(spec["sql"], (last_id, args.batch))
        rows = cur.fetchall()
        if not rows:
            break
        docs = [spec["convert"](r) for r in rows]
        t_b = time.perf_counter()
        if args.dry_run:
            ids = [d["_id"] for d in docs]
            existing = coll.count_documents({"_id": {"$in": ids}}) if ids else 0
            would_replace += existing
            would_insert += len(ids) - existing
        else:
            res = coll.bulk_write([ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in docs], ordered=False)
            inserted += res.upserted_count
            replaced += res.modified_count
            unchanged += res.matched_count - res.modified_count
        last_id = rows[-1][0]
        read += len(rows)
        rows_done += len(rows)
        batches += 1
        if not args.dry_run:
            state.replace_one({"_id": name}, {"_id": name, "last_id": last_id, "rows_done": rows_done,
                                              "updated_at": dt.datetime.now(dt.timezone.utc)}, upsert=True)
        log(fh, event="batch", table=name, batch_no=batches, rows=len(rows), last_id=last_id,
            write_seconds=round(time.perf_counter() - t_b, 4))
        if args.stop_after_batches and batches >= args.stop_after_batches:
            log(fh, event="interrupted", table=name, reason="--stop-after-batches (test de reprise)")
            return False
    secs = time.perf_counter() - t0
    log(fh, event="table_done", table=name, dry_run=args.dry_run, rows_read=read, batches=batches,
        inserted=inserted, replaced=replaced, unchanged=unchanged, would_insert=would_insert,
        would_replace=would_replace, seconds=round(secs, 3), rows_per_second=round(read / secs, 1) if secs else None,
        resumed_from=resumed_from, last_id=last_id)
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch", type=int, default=5000, help="lignes par lot")
    ap.add_argument("--tables", nargs="+", choices=list(TABLES), default=list(TABLES))
    ap.add_argument("--dry-run", action="store_true", help="n'ecrit rien dans MongoDB")
    ap.add_argument("--restart", action="store_true", help="ignore le point de reprise et rejoue toute la table")
    ap.add_argument("--stop-after-batches", type=int, default=0,
                    help="s'arrete apres K lots par table (simule une interruption, pour tester la reprise)")
    ap.add_argument("--log", default=None, help="fichier de journal (defaut : output/migration_<N>.jsonl)")
    args = ap.parse_args()

    src = connect_lab()
    src.cursor().execute("SET time_zone = '+00:00'")
    client, db = connect_mongo()
    cur = src.cursor()
    cur.execute("SELECT COUNT(*) FROM conversations")
    n_conv = cur.fetchone()[0]
    out = ROOT / "output"
    out.mkdir(exist_ok=True)
    path = args.log or str(out / f"migration_{n_conv}.jsonl")

    with open(path, "a", encoding="utf-8") as fh:
        log(fh, event="run_start", source=f"mariadb:{lab_db_name()}", target=f"mongodb:{mongo_db_name()}",
            volume_conversations=n_conv, dry_run=args.dry_run, restart=args.restart, tables=args.tables)
        if not args.dry_run:
            for t in args.tables:
                for keys, idx_name in INDEXES[t]:
                    db[TABLES[t]["collection"]].create_index(keys, name=idx_name)
            log(fh, event="indexes_ready")
        complete = True
        for t in args.tables:
            if not migrate_table(t, TABLES[t], src, db, args, fh):
                complete = False
                break
        log(fh, event="run_end", complete=complete)
    client.close()
    src.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
