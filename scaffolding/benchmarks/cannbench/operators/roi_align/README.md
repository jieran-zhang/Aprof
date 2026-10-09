# ROIAlign Ascend C direct-invoke benchmark

Correctness-first implementation of the 20 cases under
`third_party/cann-bench/tasks/level3/roi_align`.

```bash
./run.sh --case 1 --device 0
./run.sh --all --device 0
```

The Flash pass intentionally omits profiling and performance optimization.
