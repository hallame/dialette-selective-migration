"""Verifie le contenu de dialette_lab contre config/distributions.json.

Usage : python scripts/verify_lab.py [--out docs/verification_10000.md]
Ecrit un rapport Markdown (agregats uniquement) et affiche les anomalies d'integrite.
"""
import argparse
import collections
import json
import math
import statistics
import sys

from common import ROOT, connect_lab, lab_db_name

ROWS = []  # (section, indicateur, cible, obtenu, ecart_relatif)


def rel(target, got):
    if target in (None, 0) or got is None:
        return None
    return (got - target) / target * 100


def add(section, name, target, got):
    ROWS.append((section, name, target, got, rel(target, got) if isinstance(target, (int, float)) else None))


def fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--distributions", default=str(ROOT / "config" / "distributions.json"))
    a = ap.parse_args()
    d = json.load(open(a.distributions, encoding="utf-8"))
    run = None
    conn = connect_lab()
    cur = conn.cursor()
    cur.execute("SET time_zone = '+00:00'")

    def one(sql):
        cur.execute(sql)
        return cur.fetchone()[0]

    def rows(sql):
        cur.execute(sql)
        return cur.fetchall()

    counts = {t: one(f"SELECT COUNT(*) FROM {t}") for t in
              ("users", "widgets", "contacts", "conversations", "messages", "widget_views")}
    N = counts["conversations"]
    try:
        run = json.load(open(ROOT / "output" / f"run_{N}.json", encoding="utf-8"))
    except OSError:
        pass
    window = run["window_days"] if run else 365

    # --- comptes
    r = d["ratios"]
    add("Comptes", "contacts (N x ratio)", round(r["contacts_per_conversation"] * N), counts["contacts"])
    add("Comptes", "widget_views (N x ratio)", round(r["views_per_conversation"] * N), counts["widget_views"])
    add("Comptes", "messages (N x moyenne)", round(r["messages_per_conversation_mean"] * N), counts["messages"])
    add("Comptes", "users", d["dimensions"]["n_users"], counts["users"])
    add("Comptes", "widgets", d["dimensions"]["n_widgets"], counts["widgets"])

    # --- messages par conversation
    per = rows("SELECT n, COUNT(*) FROM (SELECT COUNT(*) n FROM messages GROUP BY conversation_id) x GROUP BY n")
    hist = {str(k): v for k, v in per}
    n_with = sum(hist.values())
    add("Messages", "messages par conversation (moyenne)", r["messages_per_conversation_mean"], counts["messages"] / n_with)
    add("Messages", "conversations sans message", 0, N - n_with)
    th = d["messages"]["per_conversation_histogram"]
    tot_th = sum(th.values())
    for k in sorted(set(th) | set(hist), key=int):
        add("Messages", f"part des conversations a {k} message(s)", th.get(k, 0) / tot_th, hist.get(k, 0) / n_with)

    # --- longueur
    add("Messages", "longueur moyenne, tous roles", d["messages"]["length_mean_all"],
        float(one("SELECT AVG(CHAR_LENGTH(content)) FROM messages")))
    by_role = rows("SELECT CONCAT(sender_type,':',sender_role), COUNT(*), AVG(CHAR_LENGTH(content)), "
                   "AVG(read_at IS NOT NULL) FROM messages GROUP BY 1")
    got_len = {k: float(m) for k, _, m, _ in by_role}
    got_read = {k: float(rd) for k, _, _, rd in by_role}
    for k, tgt in d["messages"]["length_mean_by_role"].items():
        add("Messages", f"longueur moyenne, role {k}", tgt, got_len.get(k))
    for k, tgt in d["messages"]["share_read_by_role"].items():
        add("Messages", f"part lue, role {k}", tgt, got_read.get(k))
    first = rows("SELECT CONCAT(sender_type,':',sender_role), COUNT(*) FROM messages m JOIN "
                 "(SELECT conversation_id, MIN(id) mid FROM messages GROUP BY conversation_id) f ON f.mid = m.id GROUP BY 1")
    ft = sum(c for _, c in first)
    gf = {k: c / ft for k, c in first}
    for k, tgt in d["messages"]["first_role"].items():
        add("Messages", f"part des conversations commencant par {k}", tgt, gf.get(k, 0))
    legacy = one("SELECT COUNT(*) FROM messages WHERE sender_type LIKE '%\\\\%'")
    add("Messages", "sender_type en nom de classe (convention ancienne, attendu 0)", 0, legacy)

    # --- vues
    add("Vues", "vues par conversation", r["views_per_conversation"], counts["widget_views"] / N)
    daily = {str(k): c for k, c in rows("SELECT DATE(created_at), COUNT(*) FROM widget_views GROUP BY 1")}
    days = [daily.get(k, 0) for k in sorted(daily)]
    first_day = rows("SELECT MIN(DATE(created_at)) FROM widget_views")[0][0]
    import datetime as dt
    series = []
    for i in range(window):
        series.append(daily.get(str(first_day + dt.timedelta(days=i)), 0))
    mean_d = statistics.mean(series)
    cv_got = statistics.pstdev(series) / mean_d
    target_mean = r["views_per_conversation"] * N / window
    add("Vues", f"vues par jour (moyenne sur {window} j)", target_mean, mean_d)
    cv_target = math.sqrt(1 / mean_d + d["widget_views"]["daily_overdispersion_cv"] ** 2)
    add("Vues", "coefficient de variation quotidien", cv_target, cv_got)
    add("Vues", "part des jours actifs", None, sum(1 for x in series if x) / window)
    wshare = rows("SELECT widget_id, COUNT(*) FROM widget_views GROUP BY 1 ORDER BY 2 DESC")
    tot = counts["widget_views"]
    for i, (wid, c) in enumerate(wshare):
        tgt = d["dimensions"]["view_share_per_widget"][i] if i < len(d["dimensions"]["view_share_per_widget"]) else 0
        add("Vues", f"part du widget de rang {i + 1}", tgt, c / tot)

    # --- conversations
    cc = d["conversations"]
    ss = {f"{s}|{(src or '')}": c for s, src, c in rows("SELECT status, source, COUNT(*) FROM conversations GROUP BY 1,2")}
    for k, tgt in cc["status_source"].items():
        add("Conversations", f"part status|source = {k}", tgt, ss.get(k, 0) / N)
    tp = {f"{a_}|{b_}": c for a_, b_, c in rows("SELECT interlocutor_type, conversable_type, COUNT(*) FROM conversations GROUP BY 1,2")}
    for k, tgt in cc["type_pairs_interlocutor_conversable"].items():
        add("Conversations", f"part types {k}", tgt, tp.get(k, 0) / N)
    add("Conversations", "types en nom de classe (attendu 0)", 0,
        one("SELECT COUNT(*) FROM conversations WHERE interlocutor_type LIKE '%\\\\%' OR conversable_type LIKE '%\\\\%'"))
    cl = one("SELECT COUNT(*) FROM conversations WHERE status='closed'")
    add("Conversations", "fermees avec closed_at", cc["share_closed_with_closed_at"],
        one("SELECT COUNT(*) FROM conversations WHERE status='closed' AND closed_at IS NOT NULL") / cl)

    # --- meta
    meta_rows = [json.loads(m[0]) for m in rows("SELECT meta FROM conversations WHERE meta IS NOT NULL")]
    add("Meta", "part de meta NULL", cc["share_meta_null"], 1 - len(meta_rows) / N)
    invalid = one("SELECT COUNT(*) FROM conversations WHERE meta IS NOT NULL AND JSON_VALID(meta) = 0")
    add("Meta", "meta non valides en JSON (attendu 0)", 0, invalid)
    pat = collections.Counter(",".join(m.keys()) for m in meta_rows)
    for k, tgt in d["meta"]["key_set_patterns"].items():
        add("Meta", f"part du motif de cles {k}", tgt, pat.get(k, 0) / len(meta_rows))
    add("Meta", "motifs de cles inattendus (attendu 0)", 0, sum(c for k, c in pat.items() if k not in d["meta"]["key_set_patterns"]))
    add("Meta", "done est un booleen true", d["meta"]["share_done_true_among_meta"],
        sum(1 for m in meta_rows if m.get("done") is True) / len(meta_rows))
    non_str = sum(1 for m in meta_rows for k, v in m.items() if k != "done" and not isinstance(v, str))
    add("Meta", "valeurs non chaines hors done (attendu 0)", 0, non_str)
    for key in ("type", "timeline", "budget", "project_type"):
        c = collections.Counter(m[key] for m in meta_rows if key in m)
        tot_c = sum(c.values())
        for val, tgt in d["meta"]["categorical_values"][key].items():
            got = (tot_c - sum(n for v, n in c.items() if v in d["meta"]["categorical_values"][key])) / tot_c if val == "__other__" else c.get(val, 0) / tot_c
            add("Meta", f"{key} = {val if val != '__other__' else 'autre (saisie libre)'}", tgt, got)
    avg_size = float(one("SELECT AVG(LENGTH(meta)) FROM conversations WHERE meta IS NOT NULL"))
    add("Meta", "taille moyenne de meta en octets (reference Dialette 113,8)", 113.8, avg_size)

    # --- integrite (les FK sont aussi imposees par InnoDB ; on verifie quand meme)
    integ = [
        ("messages sans conversation", "SELECT COUNT(*) FROM messages m LEFT JOIN conversations c ON c.id=m.conversation_id WHERE c.id IS NULL"),
        ("widget_views sans widget", "SELECT COUNT(*) FROM widget_views v LEFT JOIN widgets w ON w.id=v.widget_id WHERE w.id IS NULL"),
        ("widgets sans user", "SELECT COUNT(*) FROM widgets w LEFT JOIN users u ON u.id=w.user_id WHERE u.id IS NULL"),
        ("conversations avec user_id inexistant", "SELECT COUNT(*) FROM conversations c LEFT JOIN users u ON u.id=c.user_id WHERE c.user_id IS NOT NULL AND u.id IS NULL"),
        ("contacts avec user_id inexistant", "SELECT COUNT(*) FROM contacts c LEFT JOIN users u ON u.id=c.user_id WHERE c.user_id IS NOT NULL AND u.id IS NULL"),
        ("interlocutor_id sans contact", "SELECT COUNT(*) FROM conversations c LEFT JOIN contacts k ON k.id=c.interlocutor_id WHERE k.id IS NULL"),
        ("conversable contact sans contact", "SELECT COUNT(*) FROM conversations c LEFT JOIN contacts k ON k.id=c.conversable_id WHERE c.conversable_type='contact' AND k.id IS NULL"),
        ("expediteur contact sans contact", "SELECT COUNT(*) FROM messages m LEFT JOIN contacts k ON k.id=m.sender_id WHERE m.sender_type='contact' AND k.id IS NULL"),
        ("expediteur user sans user", "SELECT COUNT(*) FROM messages m LEFT JOIN users u ON u.id=m.sender_id WHERE m.sender_type='user' AND u.id IS NULL"),
        ("last_message_at different du dernier message", "SELECT COUNT(*) FROM conversations c JOIN (SELECT conversation_id, MAX(created_at) mx FROM messages GROUP BY 1) x ON x.conversation_id=c.id WHERE c.last_message_at <> x.mx"),
        ("lignes polymorphes de type inconnu", "SELECT COUNT(*) FROM conversations WHERE interlocutor_type NOT IN ('contact','user') OR conversable_type NOT IN ('contact','lead','project')"),
        ("references ou jetons dupliques", "SELECT (SELECT COUNT(*)-COUNT(DISTINCT reference) FROM conversations) + (SELECT COUNT(*)-COUNT(DISTINCT token) FROM conversations)"),
    ]
    integrity = []
    for name, sql in integ:
        v = int(one(sql))
        integrity.append((name, v))
        add("Integrite", name + " (attendu 0)", 0, v)
    idx = rows("SHOW INDEX FROM widget_views")
    has_created_idx = any(i[4] == "created_at" for i in idx)
    add("Integrite", "index sur widget_views.created_at (attendu 0, comme Dialette)", 0, 1 if has_created_idx else 0)
    bad = sum(1 for n, v in integrity if v)
    conn.close()

    # --- rapport
    lines = [f"# Verification de {lab_db_name()}, N = {N}", "",
             f"Distributions : `config/distributions.json` (extraites le {d['source']['extracted_on']}, "
             f"echantillon : {d['sample_sizes']['conversations']} conversations, {d['sample_sizes']['messages']} messages, "
             f"{d['sample_sizes']['widget_views']} vues ; base de test, pas de production).", ""]
    if run:
        lines += [f"Generation : graine {run['seed']}, fenetre {run['window_days']} jours jusqu'au {run['end_date']}, "
                  f"duree {run['seconds']} s.", ""]
    lines += [f"Anomalies d'integrite : **{bad}**.", ""]
    current = None
    for sec, name, tgt, got, e in ROWS:
        if sec != current:
            current = sec
            lines += ["", f"## {sec}", "", "| Indicateur | Cible | Obtenu | Ecart relatif |", "|---|---|---|---|"]
        lines.append(f"| {name} | {fmt(tgt)} | {fmt(got)} | {'' if e is None else f'{e:+.1f} %'} |")
    text = "\n".join(lines) + "\n"
    print(text)
    if a.out:
        (ROOT / a.out).write_text(text, encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
