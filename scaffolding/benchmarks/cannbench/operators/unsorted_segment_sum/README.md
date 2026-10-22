# unsorted_segment_sum direct invocation

Standalone Ascend C implementation for the 20 level2 cann-bench cases.

```bash
./run.sh --case 1 --device 2
./run.sh --all --device 2
```

The executable accepts `--shape`, `--dtype`, `--id-dtype`, `--num-segments`,
`--data`, `--ids`, `--output`, and `--device`. Correctness is prioritized over
profiling: accumulation is deterministic on one AICore, with FP32 accumulation
for FP16/BF16 as required by the golden implementation.
