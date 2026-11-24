# Benchmark Results, N = 100000

- MariaDB database: `dialette_lab` | MongoDB database: `dialette_lab`
- Counts: 100000 conversations, 402404 messages, 1140000 widget_views, 74975 conversation_answers
- Total runtime: 102.0 s

| Workload | Config A (MariaDB) med / p95 (ms) | Config B (Hybrid) med / p95 (ms) | Speedup (A / B) |
|---|---|---|---|
| R1: Read full thread + qualification | 0.854 / 1.137 | 1.329 / 2.853 | x0.64 |
| R2: HTTP polling new messages | 1.568 / 2.149 | 0.822 / 1.114 | x1.91 |
| W1: Write message + UPDATE conversation | 1.661 / 2.316 | 0.928 / 1.357 | x1.79 |
| W2: Write widget_view (no date index) | 1.058 / 1.525 | 0.408 / 0.492 | x2.59 |
| W2+i: Write widget_view (with date index) | 1.126 / 1.441 | 0.464 / 0.64 | x2.43 |
| A1: Aggregate daily views 30d (no index) | 4736.515 / 5568.81 | 575.897 / 842.479 | x8.22 |
| A1+i: Aggregate daily views 30d (with index) | 20.816 / 25.174 | 44.727 / 60.181 | x0.47 |
| A2: Aggregate project_type on JSON/answers | 526.578 / 747.938 | 69.084 / 83.391 | x7.62 |
