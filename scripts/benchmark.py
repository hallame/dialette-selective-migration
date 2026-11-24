
r"""Comparative benchmark between Configuration A (MariaDB) and Configuration B (Hybrid MariaDB + MongoDB).

Measures 6 representative Dialette workloads (R1, R2, W1, W2, A1, A2) across both architectures,
including the indexed variant (+i) on widget_views(widget_id, created_at).
Automatically cleans up synthetic rows inserted during write benchmarks.

Usage:
    venv\Scripts\python.exe scripts\benchmark.py --out docs\benchmark_10000.md
"""
import argparse
import datetime as dt
import json
import random
import statistics
import time

from common import ROOT, connect_lab, connect_mongo, lab_db_name, mongo_db_name


def compute_stats_ms(samples_sec):
    ms = sorted(s * 1000.0 for s in samples_sec)
    p95_idx = min(len(ms) - 1, int(0.95 * len(ms)))
    return {
        "n": len(ms),
        "mean_ms": round(statistics.mean(ms), 3),
        "median_ms": round(statistics.median(ms), 3),
        "p95_ms": round(ms[p95_idx], 3),
        "min_ms": round(ms[0], 3),
        "max_ms": round(ms[-1], 3),
    }


def measure(fn, warmup, repeats):
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return compute_stats_ms(samples)


def run_suite(cur, conn, mdb, conv_ids, widget_ids, warmup, repeats, agg_repeats):
    results = {}
    n_c = len(conv_ids)
    n_w = len(widget_ids)
    c_iter = iter(range(10_000_000))

    # R1: Full conversation thread load (consultant inbox / client thread view)
    def r1_sql():
        cid = conv_ids[next(c_iter) % n_c]
        cur.execute("SELECT id, reference, status, meta, last_message_at FROM conversations WHERE id = %s", (cid,))
        cur.fetchone()
        cur.execute(
            "SELECT id, sender_type, sender_role, content, read_at, created_at "
            "FROM messages WHERE conversation_id = %s ORDER BY created_at ASC",
            (cid,),
        )
        cur.fetchall()

    def r1_hybrid():
        cid = conv_ids[next(c_iter) % n_c]
        cur.execute("SELECT id, reference, status, last_message_at FROM conversations WHERE id = %s", (cid,))
        cur.fetchone()
        mdb["conversation_answers"].find_one({"_id": cid})
        list(mdb["messages"].find({"conversation_id": cid}).sort("created_at", 1))

    results["R1_read_thread"] = {
        "A_mariadb": measure(r1_sql, warmup, repeats),
        "B_hybrid": measure(r1_hybrid, warmup, repeats),
    }

    # R2: Real-time HTTP polling for new messages (id > last_id)
    poll_targets = []
    for cid in conv_ids[: min(200, n_c)]:
        cur.execute("SELECT id FROM messages WHERE conversation_id = %s ORDER BY id ASC", (cid,))
        mids = [r[0] for r in cur.fetchall()]
        last_id = mids[-2] if len(mids) >= 2 else 0
        poll_targets.append((cid, last_id))
    n_p = len(poll_targets)

    def r2_sql():
        cid, last_id = poll_targets[next(c_iter) % n_p]
        cur.execute(
            "SELECT id, sender_role, content, created_at FROM messages "
            "WHERE conversation_id = %s AND id > %s ORDER BY id ASC",
            (cid, last_id),
        )
        cur.fetchall()

    def r2_hybrid():
        cid, last_id = poll_targets[next(c_iter) % n_p]
        list(mdb["messages"].find({"conversation_id": cid, "_id": {"$gt": last_id}}).sort("_id", 1))

    results["R2_polling_new_msgs"] = {
        "A_mariadb": measure(r2_sql, warmup, repeats),
        "B_hybrid": measure(r2_hybrid, warmup, repeats),
    }

    # W1: Incoming message insert + conversation timestamp update
    cur.execute("SELECT COALESCE(MAX(id), 0) FROM messages")
    max_msg_id = int(cur.fetchone()[0])
    m_id_gen = iter(range(max_msg_id + 1, max_msg_id + 10_000_000))
    now_utc = dt.datetime(2026, 9, 10, 12, 0, 0)

    def w1_sql():
        cid = conv_ids[next(c_iter) % n_c]
        cur.execute(
            "INSERT INTO messages (conversation_id, sender_type, sender_id, sender_role, content, created_at, updated_at) "
            "VALUES (%s, 'contact', 1, 'client', 'benchmark payload', %s, %s)",
            (cid, now_utc, now_utc),
        )
        cur.execute("UPDATE conversations SET last_message_at = %s WHERE id = %s", (now_utc, cid))
        conn.commit()

    def w1_hybrid():
        cid = conv_ids[next(c_iter) % n_c]
        mdb["messages"].insert_one({
            "_id": next(m_id_gen),
            "conversation_id": cid,
            "sender_type": "contact",
            "sender_id": 1,
            "sender_role": "client",
            "content": "benchmark payload",
            "read_at": None,
            "created_at": now_utc,
            "updated_at": now_utc,
            "deleted_at": None,
        })
        cur.execute("UPDATE conversations SET last_message_at = %s WHERE id = %s", (now_utc, cid))
        conn.commit()

    results["W1_write_message"] = {
        "A_mariadb": measure(w1_sql, warmup, repeats),
        "B_hybrid": measure(w1_hybrid, warmup, repeats),
    }
    cur.execute("DELETE FROM messages WHERE id > %s", (max_msg_id,))
    conn.commit()
    mdb["messages"].delete_many({"_id": {"$gt": max_msg_id}})

    # W2: High-frequency widget view event insert (without created_at index)
    cur.execute("SELECT COALESCE(MAX(id), 0) FROM widget_views")
    max_wv_id = int(cur.fetchone()[0])
    v_id_gen = iter(range(max_wv_id + 1, max_wv_id + 10_000_000))

    def w2_sql():
        wid = widget_ids[next(c_iter) % n_w]
        cur.execute("INSERT INTO widget_views (widget_id, created_at) VALUES (%s, %s)", (wid, now_utc))
        conn.commit()

    def w2_mongo():
        wid = widget_ids[next(c_iter) % n_w]
        mdb["widget_views"].insert_one({"_id": next(v_id_gen), "widget_id": wid, "created_at": now_utc})

    results["W2_write_widget_view_no_idx"] = {
        "A_mariadb": measure(w2_sql, warmup, repeats),
        "B_hybrid": measure(w2_mongo, warmup, repeats),
    }
    cur.execute("DELETE FROM widget_views WHERE id > %s", (max_wv_id,))
    conn.commit()
    mdb["widget_views"].delete_many({"_id": {"$gt": max_wv_id}})

    # A1: Daily widget views aggregation over last 30 days (without composite index)
    since_dt = dt.datetime(2026, 8, 11, 0, 0, 0)
    target_wid = widget_ids[0]

    def a1_sql():
        cur.execute(
            "SELECT DATE(created_at) AS d, COUNT(*) FROM widget_views "
            "WHERE widget_id = %s AND created_at >= %s GROUP BY d ORDER BY d ASC",
            (target_wid, since_dt),
        )
        cur.fetchall()

    def a1_mongo():
        pipeline = [
            {"$match": {"widget_id": target_wid, "created_at": {"$gte": since_dt}}},
            {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}, "c": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]
        list(mdb["widget_views"].aggregate(pipeline))

    results["A1_agg_views_30d_no_idx"] = {
        "A_mariadb": measure(a1_sql, 1, agg_repeats),
        "B_hybrid": measure(a1_mongo, 1, agg_repeats),
    }

    # Indexed variant (+i): add composite index (widget_id, created_at)
    print("Creating composite index (widget_id, created_at) for +i variant...")
    cur.execute("CREATE INDEX widget_views_widget_id_created_at_index ON widget_views (widget_id, created_at)")
    conn.commit()
    mdb["widget_views"].create_index([("widget_id", 1), ("created_at", 1)], name="widget_views_widget_id_created_at_index")

    results["W2_write_widget_view_with_idx"] = {
        "A_plus_i_mariadb": measure(w2_sql, warmup, repeats),
        "B_plus_i_hybrid": measure(w2_mongo, warmup, repeats),
    }
    cur.execute("DELETE FROM widget_views WHERE id > %s", (max_wv_id,))
    conn.commit()
    mdb["widget_views"].delete_many({"_id": {"$gt": max_wv_id}})

    results["A1_agg_views_30d_with_idx"] = {
        "A_plus_i_mariadb": measure(a1_sql, 1, agg_repeats),
        "B_plus_i_hybrid": measure(a1_mongo, 1, agg_repeats),
    }

    # Drop temporary index to restore baseline Dialette DDL
    cur.execute("DROP INDEX widget_views_widget_id_created_at_index ON widget_views")
    conn.commit()
    mdb["widget_views"].drop_index("widget_views_widget_id_created_at_index")

    # A2: Analytical aggregation on dynamic qualification schema (meta / answers)
    def a2_sql():
        cur.execute(
            "SELECT JSON_UNQUOTE(JSON_EXTRACT(meta, '$.project_type')) AS pt, COUNT(*) "
            "FROM conversations WHERE meta IS NOT NULL GROUP BY pt"
        )
        cur.fetchall()

    def a2_mongo():
        list(mdb["conversation_answers"].aggregate([{"$group": {"_id": "$answers.project_type", "c": {"$sum": 1}}}]))

    results["A2_agg_qualification_schema"] = {
        "A_mariadb": measure(a2_sql, 1, agg_repeats),
        "B_hybrid": measure(a2_mongo, 1, agg_repeats),
    }

    return results


def render_markdown(volume, counts, results, elapsed_sec):
    lines = [
        f"# Benchmark Results, N = {volume}",
        "",
        f"- MariaDB database: `{lab_db_name()}` | MongoDB database: `{mongo_db_name()}`",
        f"- Counts: {counts['conversations']} conversations, {counts['messages']} messages, "
        f"{counts['widget_views']} widget_views, {counts['answers']} conversation_answers",
        f"- Total runtime: {elapsed_sec:.1f} s",
        "",
        "| Workload | Config A (MariaDB) med / p95 (ms) | Config B (Hybrid) med / p95 (ms) | Speedup (A / B) |",
        "|---|---|---|---|",
    ]
    labels = {
        "R1_read_thread": "R1: Read full thread + qualification",
        "R2_polling_new_msgs": "R2: HTTP polling new messages",
        "W1_write_message": "W1: Write message + UPDATE conversation",
        "W2_write_widget_view_no_idx": "W2: Write widget_view (no date index)",
        "W2_write_widget_view_with_idx": "W2+i: Write widget_view (with date index)",
        "A1_agg_views_30d_no_idx": "A1: Aggregate daily views 30d (no index)",
        "A1_agg_views_30d_with_idx": "A1+i: Aggregate daily views 30d (with index)",
        "A2_agg_qualification_schema": "A2: Aggregate project_type on JSON/answers",
    }
    for key, label in labels.items():
        pair = results[key]
        k_a, k_b = list(pair.keys())
        sa, sb = pair[k_a], pair[k_b]
        ratio = round(sa["median_ms"] / sb["median_ms"], 2) if sb["median_ms"] > 0 else 0
        lines.append(
            f"| {label} | {sa['median_ms']} / {sa['p95_ms']} | {sb['median_ms']} / {sb['p95_ms']} | x{ratio} |"
        )
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repeats", type=int, default=200, help="iterations for R1, R2, W1, W2")
    ap.add_argument("--agg-repeats", type=int, default=15, help="iterations for A1, A2")
    ap.add_argument("--warmup", type=int, default=10, help="warmup iterations")
    ap.add_argument("--out", default=None, help="output Markdown report path")
    args = ap.parse_args()

    t0 = time.perf_counter()
    conn = connect_lab()
    cur = conn.cursor()
    cur.execute("SET time_zone = '+00:00'")
    client, mdb = connect_mongo()

    cur.execute("SELECT COUNT(*) FROM conversations")
    n_conv = int(cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM messages")
    n_msg = int(cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM widget_views")
    n_wv = int(cur.fetchone()[0])
    n_ans = mdb["conversation_answers"].count_documents({})
    counts = {"conversations": n_conv, "messages": n_msg, "widget_views": n_wv, "answers": n_ans}

    cur.execute("SELECT id FROM conversations ORDER BY id ASC")
    all_cids = [r[0] for r in cur.fetchall()]
    sample_cids = random.Random(42).sample(all_cids, min(500, len(all_cids)))
    cur.execute("SELECT id FROM widgets ORDER BY id ASC")
    widget_ids = [r[0] for r in cur.fetchall()]

    print(f"Running benchmark N={n_conv} (messages={n_msg}, views={n_wv}, answers={n_ans})...")
    results = run_suite(cur, conn, mdb, sample_cids, widget_ids, args.warmup, args.repeats, args.agg_repeats)
    elapsed = time.perf_counter() - t0

    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    payload = {"volume": n_conv, "counts": counts, "elapsed_seconds": round(elapsed, 2), "results": results}
    (out_dir / f"benchmark_{n_conv}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    md = render_markdown(n_conv, counts, results, elapsed)
    print("\n" + md)
    if args.out:
        out_path = ROOT / args.out
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
        print(f"Report written to {out_path}")

    client.close()
    conn.close()


if __name__ == "__main__":
    main()
