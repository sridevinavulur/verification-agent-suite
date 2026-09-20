# Bandit feature-group ablation (TEST split)

Each row removes one feature group from the LinUCB context. A drop vs `full` indicates the group carries signal.

| Variant | Solved % | Mean reward | Design var |
| --- | ---: | ---: | ---: |
| full | 76.5 | 0.468 | 0.5279 |
| -size | 76.5 | 0.468 (+0.000) | 0.5279 |
| -depth | 76.5 | 0.468 (+0.000) | 0.5279 |
| -difficulty | 76.5 | 0.468 (+0.000) | 0.5279 |
| -property_type | 76.5 | 0.468 (+0.000) | 0.5279 |

> On a small toy suite the trained bandit may converge to the same arm regardless of which feature group is masked, giving near-zero deltas. That is expected here and is itself a threat-to-validity signal (sample too small to attribute importance); see THREAT_MODEL.md.
