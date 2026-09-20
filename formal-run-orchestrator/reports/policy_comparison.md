# Policy comparison (split: test)

| Policy | Solved % | PASS | FAIL | TIMEOUT | ERROR | INCONC | CPU s | Wall s | PeakMem MB | Mean reward | Reward 95% CI | Design var |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bandit_linucb | 76.5 | 8 | 5 | 4 | 0 | 0 | 1455.2 | 1216.3 | 524 | 0.468 | [0.123, 0.814] | 0.5279 |
| fixed | 76.5 | 8 | 5 | 4 | 0 | 0 | 1455.2 | 1216.3 | 524 | 0.468 | [0.123, 0.814] | 0.5279 |
| rule_based | 58.8 | 8 | 2 | 6 | 1 | 0 | 847.5 | 714.1 | 15690 | 0.177 | [-0.230, 0.585] | 0.7344 |
| random | 47.1 | 6 | 2 | 2 | 7 | 0 | 758.3 | 642.9 | 15690 | -0.043 | [-0.477, 0.391] | 0.8347 |

> Metrics computed on the held-out split via the deterministic MOCK executor. See THREAT_MODEL.md for threats to validity (leakage, correlated designs, non-determinism, tool-version drift, selective reporting).
