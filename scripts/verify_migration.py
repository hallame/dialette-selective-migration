"""Verifie la migration MariaDB vers MongoDB (configuration B).

Usage : python scripts/verify_migration.py [--out docs/migration_verification_10000.md]

Controles : comptes par table, messages par conversation, hash du contenu des messages
(et de la ligne complete), egalite du JSON de meta avec le document migre, orphelins cote
MongoDB, index attendus. Code de sortie 1 si un controle echoue.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import sys

import pymysql.cursors

from common import ROOT, connect_lab, connect_mongo, lab_db_name, mongo_db_name
from migrate_selective import INDEXES

MSG_COLS = ["id", "conversation_id", "sender_type", "sender_id", "sender_role", "content",
            "read_at", "created_at", "updated_at", "deleted_at"]
RESULTS = []  # (section, controle, attendu, obtenu, ok)


def check(section, name, expected, got, ok=None):
    ok = (expected == got) if ok is None else ok
    RESULTS.append((section, name, expected, got, ok))
    return ok


def canon(v):
    return v.isoformat(sep=" ") if isinstance(v, dt.datetime) else v


def digest_rows(rows):
    """SHA-256 d'un flux de tuples, serialises en JSON compact."""
    h = hashlib.sha256()
    for r in rows:
        h.update(json.dumps([canon(x) for x in r], ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    src = connect_lab()
    src.cursor().execute("SET time_zone = '+00:00'")
    client, db = connect_mongo()
    cur = src.cursor()

    def one(sql):
        cur.execute(sql)
        return cur.fetchone()[0]

    n_conv = one("SELECT COUNT(*) FROM conversations")

    # 1. comptes
    for sec_name, sql, coll in [
        ("messages", "SELECT COUNT(*) FROM messages", "messages"),
        ("widget_views", "SELECT COUNT(*) FROM widget_views", "widget_views"),
        ("conversations.meta non NULL / conversation_answers",
         "SELECT COUNT(*) FROM conversations WHERE meta IS NOT NULL", "conversation_answers"),
    ]:
        check("Comptes", sec_name, one(sql), db[coll].count_documents({}))

    # 2. messages par conversation
    cur.execute("SELECT conversation_id, COUNT(*) FROM messages GROUP BY conversation_id")
    sql_counts = dict(cur.fetchall())
    mongo_counts = {d["_id"]: d["n"] for d in db.messages.aggregate(
        [{"$group": {"_id": "$conversation_id", "n": {"$sum": 1}}}], allowDiskUse=True)}
    diff = sum(1 for k in set(sql_counts) | set(mongo_counts) if sql_counts.get(k) != mongo_counts.get(k))
    check("Messages par conversation", "conversations avec message (MariaDB / MongoDB)", len(sql_counts), len(mongo_counts))
    check("Messages par conversation", "conversations dont le nombre de messages differe (attendu 0)", 0, diff)
    check("Messages par conversation", "total des messages", sum(sql_counts.values()), sum(mongo_counts.values()))

    # 3. hash du contenu des messages
    ss = src.cursor(pymysql.cursors.SSCursor)
    ss.execute(f"SELECT {','.join(MSG_COLS)} FROM messages ORDER BY id")
    mongo_cur = db.messages.find({}, {c if c != "id" else "_id": 1 for c in MSG_COLS}).sort("_id", 1).batch_size(5000)

    def mongo_rows():
        for d in mongo_cur:
            yield tuple(d["_id"] if c == "id" else d.get(c) for c in MSG_COLS)

    h_full_s, h_full_m = hashlib.sha256(), hashlib.sha256()
    h_cont_s, h_cont_m = hashlib.sha256(), hashlib.sha256()
    row_diff = content_diff = n = 0
    ci = MSG_COLS.index("content")
    sentinel = object()
    it_m = mongo_rows()
    for rs in ss:
        rm = next(it_m, sentinel)
        n += 1
        for r, hf, hc in ((rs, h_full_s, h_cont_s), (rm, h_full_m, h_cont_m)):
            if r is sentinel:
                continue
            hf.update((json.dumps([canon(x) for x in r], ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
            hc.update(((r[ci] or "") + "\x00").encode("utf-8"))
        if rm is sentinel or rs != rm:
            row_diff += 1
        if rm is sentinel or rs[ci] != rm[ci]:
            content_diff += 1
    extra = sum(1 for _ in it_m)
    check("Messages (hash)", "messages compares", n, n + extra)
    check("Messages (hash)", "lignes dont un champ differe (attendu 0)", 0, row_diff)
    check("Messages (hash)", "messages dont le contenu differe (attendu 0)", 0, content_diff)
    check("Messages (hash)", "SHA-256 du contenu, ordre par id", h_cont_s.hexdigest(), h_cont_m.hexdigest())
    check("Messages (hash)", "SHA-256 des lignes completes, ordre par id", h_full_s.hexdigest(), h_full_m.hexdigest())

    # widget_views : meme principe
    ss = src.cursor(pymysql.cursors.SSCursor)
    ss.execute("SELECT id, widget_id, created_at FROM widget_views ORDER BY id")
    mv = db.widget_views.find({}).sort("_id", 1).batch_size(10000)
    hv_s = digest_rows(ss)
    hv_m = digest_rows((d["_id"], d["widget_id"], d["created_at"]) for d in mv)
    check("Widget views (hash)", "SHA-256 des lignes (id, widget_id, created_at), ordre par id", hv_s, hv_m)

    # 4. meta
    ss = src.cursor(pymysql.cursors.SSCursor)
    ss.execute("SELECT id, meta FROM conversations WHERE meta IS NOT NULL ORDER BY id")
    ans = db.conversation_answers.find({}).sort("_id", 1).batch_size(5000)
    eq_val = eq_order = missing = total = 0
    it_a = iter(ans)
    bad_types = 0
    for cid, meta in ss:
        total += 1
        doc = next(it_a, None)
        if doc is None or doc["_id"] != cid:
            missing += 1
            continue
        original = json.loads(meta)
        if original == doc["answers"]:
            eq_val += 1
        if list(original) == list(doc["answers"]):
            eq_order += 1
        for k, v in original.items():
            if type(v) is not type(doc["answers"].get(k)):
                bad_types += 1
    check("Meta (JSON)", "meta absents ou mal apparies cote MongoDB (attendu 0)", 0, missing)
    check("Meta (JSON)", "JSON egal au document migre (valeurs)", total, eq_val)
    check("Meta (JSON)", "meme ordre des cles", total, eq_order)
    check("Meta (JSON)", "valeurs dont le type JSON differe (attendu 0)", 0, bad_types)
    n_null = one("SELECT COUNT(*) FROM conversations WHERE meta IS NULL")
    check("Meta (JSON)", "conversations a meta NULL sans document (attendu : toutes)", n_null,
          n_conv - db.conversation_answers.count_documents({}))

    # 5. orphelins cote MongoDB (cascade, voir docs/methodo.md)
    conv_ids = {r[0] for r in _all(src, "SELECT id FROM conversations")}
    widget_ids = {r[0] for r in _all(src, "SELECT id FROM widgets")}
    check("Orphelins MongoDB", "messages sans conversation dans MariaDB (attendu 0)", 0,
          sum(1 for c in db.messages.distinct("conversation_id") if c not in conv_ids))
    check("Orphelins MongoDB", "widget_views sans widget dans MariaDB (attendu 0)", 0,
          sum(1 for w in db.widget_views.distinct("widget_id") if w not in widget_ids))
    check("Orphelins MongoDB", "conversation_answers sans conversation dans MariaDB (attendu 0)", 0,
          sum(1 for d in db.conversation_answers.find({}, {"_id": 1}) if d["_id"] not in conv_ids))

    # 6. index
    for coll, expected in INDEXES.items():
        have = {i["name"]: list(i["key"].items()) for i in db[coll].list_indexes() if i["name"] != "_id_"}
        want = {name: keys for keys, name in expected}
        check("Index MongoDB", f"{coll} : index hors _id", sorted(want), sorted(have))
    check("Index MongoDB", "widget_views : index sur created_at (attendu aucun)", False,
          any("created_at" in i["key"] for i in db.widget_views.list_indexes()))

    ok_all = all(r[4] for r in RESULTS)
    lines = [f"# Verification de la migration, N = {n_conv}", "",
             f"Source : MariaDB `{lab_db_name()}`. Cible : MongoDB `{mongo_db_name()}` (serveur {client.server_info()['version']}).", "",
             f"Resultat global : **{'TOUS LES CONTROLES REUSSIS' if ok_all else 'ECHEC'}** "
             f"({sum(1 for r in RESULTS if r[4])} sur {len(RESULTS)}).", ""]
    cur_sec = None
    for sec, name, exp, got, ok in RESULTS:
        if sec != cur_sec:
            cur_sec = sec
            lines += ["", f"## {sec}", "", "| Controle | Attendu (MariaDB) | Obtenu (MongoDB) | Resultat |", "|---|---|---|---|"]
        f = lambda v: f"`{v[:16]}...`" if isinstance(v, str) and len(v) == 64 else str(v)
        lines.append(f"| {name} | {f(exp)} | {f(got)} | {'OK' if ok else 'ECHEC'} |")
    text = "\n".join(lines) + "\n"
    print(text)
    if a.out:
        (ROOT / a.out).write_text(text, encoding="utf-8")
    return 0 if ok_all else 1


def _all(conn, sql):
    c = conn.cursor()
    c.execute(sql)
    return c.fetchall()


if __name__ == "__main__":
    sys.exit(main())
