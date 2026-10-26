"""Generateur reproductible de donnees synthetiques pour dialette_lab.

Usage : python scripts/generate_data.py --volume 10000 [--seed 42]

N (--volume) est le nombre de conversations. Messages et vues de widget en derivent via
config/distributions.json. Un seul generateur pseudo-aleatoire (random.Random(seed)) est
utilise : meme graine, meme volume et meme fichier de distributions donnent des donnees
identiques. Le chargement se fait par lots. Les types polymorphes sont ecrits en alias
(convention actuelle du morph map de Dialette).
"""
import argparse
import bisect
import collections
import datetime as dt
import json
import math
import random
import sys
import time

from common import ROOT, connect_lab, lab_db_name

# Vocabulaire neutre ecrit pour le generateur : aucun mot ne vient des donnees de Dialette.
WORDS = ("projet site page client offre devis delai budget equipe outil service contact "
         "message reponse besoin objectif etape suivi rendez-vous appel lancement version "
         "contenu design reseau marque produit demande question idee plan retour merci "
         "bonjour salut disponible rapidement propose ensemble conseil mission atelier "
         "formation cadre notes mise test base module compte ligne nouveau simple clair").split()
DIGITS = "0123456789"
REF_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


class Gen:
    def __init__(self, dist, seed):
        self.d = dist
        self.rng = random.Random(seed)

    # --- primitives
    def pick(self, weights):
        return self.rng.choices(list(weights), weights=list(weights.values()))[0]

    def quantile(self, points, pcts):
        """Echantillonne par interpolation lineaire de la fonction quantile."""
        u = self.rng.random() * 100
        i = min(bisect.bisect_right(pcts, u) - 1, len(pcts) - 2)
        span = pcts[i + 1] - pcts[i]
        frac = (u - pcts[i]) / span if span else 0
        return points[i] + (points[i + 1] - points[i]) * frac

    def text(self, length):
        length = int(round(length))
        if length <= 0:
            return ""
        out = []
        size = 0
        while size < length:
            w = self.rng.choice(WORDS)
            out.append(w)
            size += len(w) + 1
        s = " ".join(out)[:length]
        return s[:-1] + "a" if s.endswith(" ") else s

    def phone(self):
        return "+" + "".join(self.rng.choice(DIGITS) for _ in range(11))

    def hex(self, n=64):
        return "%0*x" % (n, self.rng.getrandbits(n * 4))


def insert(cur, table, cols, rows):
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join(['%s'] * len(cols))})"
    cur.executemany(sql, rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--volume", type=int, required=True, help="N = nombre de conversations")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--window-days", type=int, default=365, help="fenetre temporelle des donnees")
    ap.add_argument("--end-date", default="2026-09-10", help="dernier jour de la fenetre (AAAA-MM-JJ)")
    ap.add_argument("--batch", type=int, default=5000)
    ap.add_argument("--distributions", default=str(ROOT / "config" / "distributions.json"))
    a = ap.parse_args()

    dist = json.load(open(a.distributions, encoding="utf-8"))
    g = Gen(dist, a.seed)
    rng = g.rng
    N = a.volume
    end_day = dt.datetime.fromisoformat(a.end_date)
    start_day = end_day - dt.timedelta(days=a.window_days - 1)
    t0 = time.time()

    conn = connect_lab()
    cur = conn.cursor()
    cur.execute("SET time_zone = '+00:00'")
    print(f"base cible : {lab_db_name()}  N={N}  seed={a.seed}  fenetre={a.window_days} j")

    # --- remise a zero (jamais la base de l'application : lab_db_name() l'interdit)
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for t in ("widget_views", "messages", "conversations", "contacts", "widgets", "users"):
        cur.execute(f"TRUNCATE TABLE {t}")
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")

    # --- dimensions : users, widgets
    dim = dist["dimensions"]
    conv_shares = dim["conversation_share_per_active_user"]
    n_active = len(conv_shares)
    created0 = start_day
    insert(cur, "users", ["id", "email", "created_at"],
           [(i, f"user{i}@lab.invalid", created0) for i in range(1, dim["n_users"] + 1)])
    # Les widgets sont repartis en tourniquet entre les utilisateurs actifs.
    insert(cur, "widgets", ["id", "user_id", "slug", "created_at"],
           [(i, ((i - 1) % n_active) + 1, f"widget-{i}", created0) for i in range(1, dim["n_widgets"] + 1)])
    conn.commit()

    # --- contacts
    n_contacts = round(dist["ratios"]["contacts_per_conversation"] * N)
    active_users = list(range(1, n_active + 1))
    seen_users = [rng.choices(active_users, weights=conv_shares)[0] for _ in range(n_contacts)]
    rows = []
    for i in range(1, n_contacts + 1):
        rows.append((i, f"CON-{i:08d}", f"c{i}@lab.invalid", seen_users[i - 1], start_day, None))
        if len(rows) >= a.batch:
            insert(cur, "contacts", ["id", "reference", "email", "user_id", "created_at", "deleted_at"], rows)
            rows = []
    if rows:
        insert(cur, "contacts", ["id", "reference", "email", "user_id", "created_at", "deleted_at"], rows)
    conn.commit()
    print(f"contacts : {n_contacts}  ({time.time() - t0:.1f}s)")

    # --- conversations et messages, par lots, dans l'ordre chronologique des conversations
    conv_hours = dist["conversation_hour_of_day_share"]
    hour_w = [conv_hours[str(h)] for h in range(24)]
    ts = []
    for _ in range(N):
        day = rng.randrange(a.window_days)
        hour = rng.choices(range(24), weights=hour_w)[0]
        ts.append(start_day + dt.timedelta(days=day, hours=hour, minutes=rng.randrange(60), seconds=rng.randrange(60)))
    ts.sort()

    M = dist["messages"]
    pcts = M["quantile_points_percent"]
    hist = M["per_conversation_histogram"]
    hist_keys, hist_w = [int(k) for k in hist], list(hist.values())
    meta_cfg = dist["meta"]
    conv_cfg = dist["conversations"]
    cat = meta_cfg["categorical_values"]
    free_q = meta_cfg["free_text_length_quantiles"]
    refs, tokens = set(), set()

    conv_cols = ["id", "reference", "interlocutor_type", "interlocutor_id", "subject", "conversable_type",
                 "conversable_id", "meta", "status", "token", "source", "last_message_at", "closed_at",
                 "user_id", "created_at", "updated_at", "deleted_at"]
    msg_cols = ["conversation_id", "sender_type", "sender_id", "sender_role", "content", "read_at",
                "created_at", "updated_at", "deleted_at"]
    n_msgs = 0
    conv_rows, msg_rows = [], []

    def flush():
        nonlocal conv_rows, msg_rows
        if conv_rows:
            insert(cur, "conversations", conv_cols, conv_rows)
            insert(cur, "messages", msg_cols, msg_rows)
            conn.commit()
        conv_rows, msg_rows = [], []

    for idx in range(N):
        cid = idx + 1
        created = ts[idx]
        owner = rng.choices(active_users, weights=conv_shares)[0]
        contact_id = rng.randrange(1, n_contacts + 1)
        t_inter, t_conv = g.pick(conv_cfg["type_pairs_interlocutor_conversable"]).split("|")
        conv_id_target = contact_id if t_conv == "contact" else rng.randrange(1, N + 1)
        status, source = g.pick(conv_cfg["status_source"]).split("|")

        # messages
        L = rng.choices(hist_keys, weights=hist_w)[0]
        role = g.pick(M["first_role"])
        when = created + dt.timedelta(seconds=g.quantile(M["first_message_offset_seconds_quantiles"], pcts))
        msgs = []
        for j in range(L):
            if j:
                nxt = M["role_transitions"].get(role)
                role = g.pick(nxt) if nxt else g.pick(M["first_role"])
                when = when + dt.timedelta(seconds=round(g.quantile(M["gap_seconds_quantiles"], pcts)))
            stype, srole = role.split(":")
            sender_id = contact_id if stype == "contact" else owner
            content = g.text(g.quantile(M["length_quantiles_by_role"][role], pcts))
            read_at = None
            if rng.random() < M["share_read_by_role"][role]:
                read_at = when + dt.timedelta(seconds=round(g.quantile(M["gap_seconds_quantiles"], pcts)))
            msgs.append((cid, stype, sender_id, srole, content, read_at, when, when, None))
        last_at = msgs[-1][6]
        n_msgs += len(msgs)

        # meta
        meta = None
        if rng.random() >= conv_cfg["share_meta_null"]:
            doc = {}
            for key in g.pick(meta_cfg["key_set_patterns"]).split(","):
                if key == "done":
                    doc[key] = rng.random() < meta_cfg["share_done_true_among_meta"]
                elif key in cat:
                    v = g.pick(cat[key])
                    doc[key] = g.text(rng.randint(6, 20)) if v == "__other__" else v
                elif key == "phone":
                    doc[key] = g.phone()
                else:
                    doc[key] = g.text(g.quantile(free_q[key], pcts))
            # separateurs compacts et ASCII echappe, comme json_encode de PHP
            meta = json.dumps(doc, ensure_ascii=True, separators=(",", ":"))

        while True:
            ref = "CONV26-" + "".join(rng.choice(REF_CHARS) for _ in range(6))
            if ref not in refs:
                refs.add(ref)
                break
        token = g.hex()
        subject = g.text(rng.randint(10, 40)) if rng.random() < conv_cfg["share_with_subject"] else None
        closed_at = None
        if status == "closed" and rng.random() < conv_cfg["share_closed_with_closed_at"]:
            closed_at = last_at

        conv_rows.append((cid, ref, t_inter, contact_id, subject, t_conv, conv_id_target, meta, status, token,
                          source or None, last_at, closed_at, owner, created, max(last_at, created), None))
        msg_rows.extend(msgs)
        if len(conv_rows) >= a.batch:
            flush()
    flush()
    print(f"conversations : {N}  messages : {n_msgs}  ({time.time() - t0:.1f}s)")

    # --- widget_views : repartition par jour (surdispersion lognormale), puis par widget et heure
    wv = dist["widget_views"]
    total_views = round(dist["ratios"]["views_per_conversation"] * N)
    cv_w = wv["daily_overdispersion_cv"]
    sigma = math.sqrt(math.log(1 + cv_w ** 2))
    day_w = [rng.lognormvariate(0.0, sigma) for _ in range(a.window_days)]
    per_day = collections.Counter(rng.choices(range(a.window_days), weights=day_w, k=total_views))
    v_hours = [wv["hour_of_day_share"][str(h)] for h in range(24)]
    widget_w = dim["view_share_per_widget"]
    widget_ids = list(range(1, len(widget_w) + 1))
    buf, n_views = [], 0
    for day in range(a.window_days):
        k = per_day.get(day, 0)
        day_rows = []
        for _ in range(k):
            h = rng.choices(range(24), weights=v_hours)[0]
            t = start_day + dt.timedelta(days=day, hours=h, minutes=rng.randrange(60), seconds=rng.randrange(60))
            day_rows.append((rng.choices(widget_ids, weights=widget_w)[0], t))
        day_rows.sort(key=lambda r: r[1])  # ids croissants dans l'ordre chronologique
        buf.extend(day_rows)
        n_views += k
        if len(buf) >= a.batch:
            insert(cur, "widget_views", ["widget_id", "created_at"], buf)
            conn.commit()
            buf = []
    if buf:
        insert(cur, "widget_views", ["widget_id", "created_at"], buf)
        conn.commit()
    print(f"widget_views : {n_views}  ({time.time() - t0:.1f}s)")

    meta_run = {"volume": N, "seed": a.seed, "window_days": a.window_days, "end_date": a.end_date,
                "start_date": start_day.date().isoformat(), "distributions": a.distributions,
                "n_contacts": n_contacts, "n_messages": n_msgs, "n_widget_views": n_views,
                "seconds": round(time.time() - t0, 1)}
    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    (out_dir / f"run_{N}.json").write_text(json.dumps(meta_run, indent=2) + "\n", encoding="utf-8")
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
