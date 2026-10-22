# unique direct invoke

Correctness-first Ascend C direct-invoke framework for the original 20 level3
Unique cases. Order-preserving key encoding, radix sorting, unique compaction,
dynamic count generation, and inverse construction all execute on the NPU.

```bash
./run.sh --case 1 --device 0
./run.sh --all --skip-build --device 0
```
