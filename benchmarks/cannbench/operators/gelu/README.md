# gelu AscendC direct invocation

Standalone AscendC direct-invocation implementation for the 20 official
`third_party/cann-bench/tasks/level1/gelu` cases.

```bash
./run.sh --case 1 --device 2
./run.sh --all --device 2
```

The executable accepts raw tensor files and launches `gelu_kernel` directly on
Ascend 910 (`dav-2201`). `approximate=none` uses the erf definition and
`approximate=tanh` uses the cubic tanh definition. Computation is performed in
FP32 and converted back to the input dtype.
