# GRU direct Ascend C benchmark

Correctness-first direct invocation implementation for the authoritative
`third_party/cann-bench/tasks/level4/gru` task. The executable launches only
self-compiled Ascend C kernels: Cube Matmul kernels compute both gate matrix
products and an AIV kernel performs sigmoid/tanh and recurrent hidden updates.

```bash
ASCEND_RT_VISIBLE_DEVICES=1 ./run.sh --all --device 0
```

`results.json` records the 20 original cases validated on Ascend910_9362
(`dav-2201`). Profiling was intentionally not collected.
