# CANNBench AProf split v0001

This split freezes operator-level membership before AProf performance traces
are collected. Canonical operator projects remain under `operators/<name>`;
the split directories contain manifests and newline-delimited task lists rather
than copies or symlinks.

## Inventory boundary

- The upstream catalog contains 53 tasks with 20 cases each.
- The filesystem currently contains 49 runnable projects with 20/20
  correctness results.
- `benchmark_results.json` still lists 46 projects. The three additional
  correctness-complete projects are `grouped_matmul_swiglu_quant`, `gru`, and
  `mha`.
- `lstm`, `mla`, `mla_prolog`, and `sparse_flash_attention` are not yet
  materialized. They are reserved as pending development-train tasks and no
  empty operator project is fabricated for them.

The active split is therefore:

```text
development train: 29 ready + 4 pending Level 4 -> target 33
validation:         5 ready
sealed test:       15 ready
```

Once the four pending tasks exist, the complete design is a 38-task learning
pool (33 development train + 5 validation) and a 15-task sealed test.

## Trace rules

1. Use only `train/operators.txt` to produce traces that update SkillGraph or
   policy state.
2. Use `validation/operators.txt` for checkpoint selection, budget tuning, and
   stopping decisions. Validation episodes must not enter the policy-training
   input of the run they evaluate.
3. Do not inspect optimization outcomes from `test/operators.txt` during trace
   exploration. Test episodes must not update skills, graph weights, prompts,
   budgets, or checkpoint selection before the paper result is frozen.
4. A task is the split unit. All 20 cases stay with the task.
5. Candidate search may use a fixed sentinel subset, but acceptance requires
   correctness on all 20 cases. Final baseline and candidate performance use
   all 20 cases with the same timing protocol.

The sealed test primarily measures transfer to new operators whose broad
mechanism families may have appeared in the learning pool. It is not currently
claimed as a strict family-OOD benchmark.

## Validate

From the repository root:

```bash
python3 benchmarks/cannbench/validate_splits.py
```

The validator checks disjointness, exact coverage, task readiness, 20/20
correctness, pending Level 4 status, text-list parity, and the frozen membership
digest.

## Iterate over training projects

```bash
while IFS= read -r operator; do
  op_dir="benchmarks/cannbench/operators/$operator"
  echo "$op_dir"
done < benchmarks/cannbench/train/operators.txt
```

Runtime traces should stay inside each project's `.aprof/` directory or in a
separate run directory keyed by split version, operator, and run ID. Do not
write learned state into `test/`.
