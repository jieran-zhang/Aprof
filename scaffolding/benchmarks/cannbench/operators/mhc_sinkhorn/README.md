# MhcSinkhorn Ascend C direct-invoke benchmark

Correctness-first device implementation for the 20 level3 cases.

```bash
./run.sh --case 1 --device 0
./run.sh --all --device 0
```

All softmax and Sinkhorn iterations execute inside the Ascend C kernel. The host
only loads input, prepares tiling, launches the kernel, and retrieves output.
