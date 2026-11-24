# Benchmark Results, N = 1000000

- MariaDB database: `dialette_lab` | MongoDB database: `dialette_lab`
- Counts: 1000000 conversations, 4025372 messages, 11400000 widget_views, 750363 conversation_answers
- Total runtime: 818.9 s

| Workload | Config A (MariaDB) med / p95 (ms) | Config B (Hybrid) med / p95 (ms) | Speedup (A / B) |
|---|---|---|---|
| R1: Read full thread + qualification | 2.012 / 2.797 | 2.591 / 3.114 | x0.78 |
| R2: HTTP polling new messages | 2.91 / 4.019 | 1.393 / 1.644 | x2.09 |
| W1: Write message + UPDATE conversation | 2.865 / 3.856 | 2.6 / 2.963 | x1.1 |
| W2: Write widget_view (no date index) | 1.589 / 2.857 | 0.749 / 0.876 | x2.12 |
| W2+i: Write widget_view (with date index) | 1.65 / 1.992 | 0.792 / 1.001 | x2.08 |
| A1: Aggregate daily views 30d (no index) | 98509.024 / 107312.995 | 9624.985 / 10146.529 | x10.23 |
| A1+i: Aggregate daily views 30d (with index) | 351.05 / 390.99 | 692.676 / 923.045 | x0.51 |
| A2: Aggregate project_type on JSON/answers | 8946.019 / 9005.016 | 1291.841 / 1330.89 | x6.93 |
