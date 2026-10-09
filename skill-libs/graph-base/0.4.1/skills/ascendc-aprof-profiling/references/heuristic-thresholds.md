# Local symptom thresholds

`compress_msprof.py` owns the executable defaults; command-line overrides are recorded in the draft. These are expert screening heuristics, not calibrated architecture probabilities or performance gates.

| Screening variable | Default |
| --- | --- |
| Scalar active ratio | 0.30 |
| MTE2 active ratio | 0.50 |
| Maximum bandwidth usage for setup-bound hypothesis | 0.60 |
| Minimum useful bytes per MTE instruction | 16384 |
| UB conflict ratio | 0.05 |
| Per-core imbalance | 0.10 |
| Observed/theoretical traffic amplification | 1.20 |
| Minimum full-profile repeats / maximum CV | 5 / 0.05 |

A setup-bound hypothesis needs all three MTE/bandwidth/granularity inputs. Missing data remains unknown. High scalar share, imbalance or conflict can indicate multiple mechanisms, and tiny workloads refute naive saturation expectations. All architecture denominators come from the actual platform profile. Profile repeats are separate from at least thirty paired timing samples used by the runtime gain gate. These local thresholds preserve the former collector's screening intent without loading an external knowledge file.
