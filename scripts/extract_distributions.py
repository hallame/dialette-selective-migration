"""Extrait des AGREGATS de la base Dialette (lecture seule) vers config/distributions.json.

Aucune valeur de contenu n'est ecrite : seulement des comptes, des longueurs, des
quantiles et des frequences. Les valeurs textuelles ne sont conservees que pour des
cles dont les reponses sont des options predefinies par le widget (liste blanche).
Reutilisable tel quel sur une base de production pour remplacer le fichier.
"""
import collections
import datetime as dt
import json
import math
import statistics
import sys

from common import ROOT, connect_source

# Cles de meta dont les valeurs sont des options predefinies (pas de texte libre).
CATEGORICAL_META_KEYS = ["type", "project_type", "timeline", "budget"]
CATEGORICAL_MIN_COUNT = 2
QUANTILE_POINTS = list(range(0, 101, 5))


def alias(t):
    """Normalise un type polymorphe vers l'alias du morph map (convention actuelle)."""
    return t.rsplit("\\", 1)[-1].lower() if t else t


def quantiles(values):
    s = sorted(values)
    if not s:
        return []
    out = []
    for p in QUANTILE_POINTS:
        pos = (len(s) - 1) * p / 100
        lo, hi = math.floor(pos), math.ceil(pos)
        out.append(round(s[lo] + (s[hi] - s[lo]) * (pos - lo), 2))
    return out


def fold_rare(counter):
    """Les options predefinies peuvent aussi recevoir une saisie libre : toute valeur vue
    moins de CATEGORICAL_MIN_COUNT fois est regroupee sous __other__ (jamais ecrite)."""
    folded = collections.Counter()
    for value, n in counter.items():
        folded[value if n >= CATEGORICAL_MIN_COUNT else "__other__"] += n
    return folded


def normalise(counter):
    total = sum(counter.values())
    return {k: round(v / total, 6) for k, v in sorted(counter.items(), key=lambda kv: -kv[1])}


def main():
    conn = connect_source()
    cur = conn.cursor()

    def one(sql):
        cur.execute(sql)
        return cur.fetchone()[0]

    def rows(sql):
        cur.execute(sql)
        return cur.fetchall()

    n_conv = one("SELECT COUNT(*) FROM conversations")
    n_msg = one("SELECT COUNT(*) FROM messages")
    n_views = one("SELECT COUNT(*) FROM widget_views")
    n_contacts = one("SELECT COUNT(*) FROM contacts")
    n_users = one("SELECT COUNT(*) FROM users")
    n_widgets = one("SELECT COUNT(*) FROM widgets")

    # --- conversations
    conv = rows("SELECT id, interlocutor_type, conversable_type, status, source, meta, created_at, "
                "closed_at, last_message_at, user_id, subject IS NOT NULL FROM conversations")
    user_counts = collections.Counter(r[9] for r in conv)
    status_source = collections.Counter(f"{r[3]}|{r[4] or ''}" for r in conv)
    type_pairs = collections.Counter(f"{alias(r[1])}|{alias(r[2])}" for r in conv)
    fqcn_rows = sum(1 for r in conv if "\\" in (r[1] or "") or "\\" in (r[2] or ""))
    closed = [r for r in conv if r[3] == "closed"]
    conv_by_id = {r[0]: r for r in conv}

    # --- messages
    msgs = rows("SELECT conversation_id, sender_type, sender_role, CHAR_LENGTH(content), "
                "created_at, read_at IS NOT NULL FROM messages ORDER BY conversation_id, created_at, id")
    per_conv = collections.defaultdict(list)
    for m in msgs:
        per_conv[m[0]].append(m)
    count_hist = collections.Counter(len(v) for v in per_conv.values())

    def role_key(m):
        return f"{alias(m[1])}:{m[2]}"

    start, trans = collections.Counter(), collections.defaultdict(collections.Counter)
    gaps, first_offsets = [], []
    lengths, read = collections.defaultdict(list), collections.defaultdict(list)
    for cid, ms in per_conv.items():
        start[role_key(ms[0])] += 1
        first_offsets.append((ms[0][4] - conv_by_id[cid][6]).total_seconds())
        for a, b in zip(ms, ms[1:]):
            trans[role_key(a)][role_key(b)] += 1
            gaps.append((b[4] - a[4]).total_seconds())
        for m in ms:
            lengths[role_key(m)].append(m[3])
            read[role_key(m)].append(1 if m[5] else 0)

    # --- meta
    patterns = collections.Counter()
    cat_values = {k: collections.Counter() for k in CATEGORICAL_META_KEYS}
    text_lengths = collections.defaultdict(list)
    meta_docs = 0
    done_true = 0
    for r in conv:
        if r[5] is None:
            continue
        doc = json.loads(r[5])
        meta_docs += 1
        done_true += 1 if doc.get("done") is True else 0
        patterns[",".join(doc.keys())] += 1
        for k, v in doc.items():
            if k == "done":
                continue
            if k in CATEGORICAL_META_KEYS:
                cat_values[k][str(v)] += 1
            else:
                text_lengths[k].append(len(str(v)))

    # --- widget_views
    views = rows("SELECT widget_id, created_at FROM widget_views")
    per_widget = collections.Counter(v[0] for v in views)
    per_day = collections.Counter(v[1].date() for v in views)
    d0, d1 = min(per_day), max(per_day)
    span = (d1 - d0).days + 1
    daily = [per_day.get(d0 + dt.timedelta(days=i), 0) for i in range(span)]
    mean_d, std_d = statistics.mean(daily), statistics.pstdev(daily)
    cv = std_d / mean_d
    # CV attendu si seul le bruit de Poisson jouait : 1/racine(moyenne). On retire cette part.
    overdisp = math.sqrt(max(cv ** 2 - 1 / mean_d, 0.0))
    hours_v = collections.Counter(v[1].hour for v in views)
    hours_c = collections.Counter(r[6].hour for r in conv)
    conv_days = (max(r[6] for r in conv) - min(r[6] for r in conv)).days + 1

    out = {
        "source": {
            "description": "Base locale Dialette (XAMPP), donnees de developpement et de test, pas de production",
            "database": "dialette",
            "extracted_on": dt.date.today().isoformat(),
            "extraction_script": "scripts/extract_distributions.py",
            "is_production": False,
            "note": "A remplacer par des agregats de production en relancant le script sur la source voulue",
        },
        "sample_sizes": {"conversations": n_conv, "messages": n_msg, "widget_views": n_views,
                         "contacts": n_contacts, "users": n_users, "widgets": n_widgets,
                         "conversations_with_meta": meta_docs},
        "ratios": {
            "contacts_per_conversation": round(n_contacts / n_conv, 6),
            "views_per_conversation": round(n_views / n_conv, 6),
            "messages_per_conversation_mean": round(n_msg / len(per_conv), 6),
        },
        "dimensions": {
            "n_users": n_users, "n_widgets": n_widgets,
            "conversation_share_per_active_user": [round(v / n_conv, 6) for v in sorted(user_counts.values(), reverse=True)],
            "view_share_per_widget": [round(v / n_views, 6) for v in sorted(per_widget.values(), reverse=True)],
        },
        "conversations": {
            "status_source": normalise(status_source),
            "type_pairs_interlocutor_conversable": normalise(type_pairs),
            "share_legacy_class_name_rows": round(fqcn_rows / n_conv, 6),
            "share_with_subject": round(sum(1 for r in conv if r[10]) / n_conv, 6),
            "share_meta_null": round(1 - meta_docs / n_conv, 6),
            "share_closed_with_closed_at": round(sum(1 for r in closed if r[7]) / len(closed), 6) if closed else None,
            "observed_span_days": conv_days,
        },
        "messages": {
            "per_conversation_histogram": {str(k): v for k, v in sorted(count_hist.items())},
            "first_role": normalise(start),
            "role_transitions": {a: normalise(c) for a, c in trans.items()},
            "length_quantiles_by_role": {k: quantiles(v) for k, v in lengths.items()},
            "length_mean_by_role": {k: round(statistics.mean(v), 3) for k, v in lengths.items()},
            "length_mean_all": round(statistics.mean([m[3] for m in msgs]), 3),
            "share_read_by_role": {k: round(statistics.mean(v), 6) for k, v in read.items()},
            "gap_seconds_quantiles": quantiles(gaps),
            "first_message_offset_seconds_quantiles": quantiles(first_offsets),
            "quantile_points_percent": QUANTILE_POINTS,
        },
        "meta": {
            "key_set_patterns": normalise(patterns),
            "share_done_true_among_meta": round(done_true / meta_docs, 6),
            "categorical_values": {k: normalise(fold_rare(c)) for k, c in cat_values.items()},
            "categorical_min_count": CATEGORICAL_MIN_COUNT,
            "free_text_length_quantiles": {k: quantiles(v) for k, v in text_lengths.items()},
            "free_text_n": {k: len(v) for k, v in text_lengths.items()},
        },
        "widget_views": {
            "observed_span_days": span,
            "active_days": sum(1 for x in daily if x),
            "daily_mean": round(mean_d, 4),
            "daily_std": round(std_d, 4),
            "daily_cv": round(cv, 4),
            "daily_overdispersion_cv": round(overdisp, 4),
            "hour_of_day_share": {str(h): round(hours_v.get(h, 0) / n_views, 6) for h in range(24)},
        },
        "conversation_hour_of_day_share": {str(h): round(hours_c.get(h, 0) / n_conv, 6) for h in range(24)},
    }
    target = ROOT / "config" / "distributions.json"
    target.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"ecrit : {target}")
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
