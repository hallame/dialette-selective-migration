# Benchmark Results, N = 10000

- MariaDB database: `dialette_lab` | MongoDB database: `dialette_lab`
- Counts: 10000 conversations, 40079 messages, 114000 widget_views, 7591 conversation_answers
- Total runtime: 6.1 s

| Workload | Config A (MariaDB) med / p95 (ms) | Config B (Hybrid) med / p95 (ms) | Speedup (A / B) |
|---|---|---|---|
| R1: Read full thread + qualification | 0.596 / 0.858 | 1.123 / 1.438 | x0.53 |
| R2: HTTP polling new messages | 0.358 / 0.892 | 0.825 / 1.041 | x0.43 |
| W1: Write message + UPDATE conversation | 1.499 / 1.94 | 1.345 / 2.831 | x1.11 |
| W2: Write widget_view (no date index) | 1.024 / 1.194 | 0.419 / 0.494 | x2.44 |
| W2+i: Write widget_view (with date index) | 0.73 / 0.887 | 0.376 / 0.502 | x1.94 |
| A1: Aggregate daily views 30d (no index) | 40.261 / 190.816 | 47.932 / 65.031 | x0.84 |
| A1+i: Aggregate daily views 30d (with index) | 3.05 / 5.235 | 7.331 / 11.024 | x0.42 |
| A2: Aggregate project_type on JSON/answers | 45.452 / 71.591 | 8.797 / 10.441 | x5.17 |
