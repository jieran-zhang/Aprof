# moe_re_routing direct invoke

Correctness-first Ascend C direct implementation of all 20 authoritative level-3
MoeReRouting cases. Both routing-index/count construction and token/scale gather
run in custom device kernels; the host only performs ACL allocation, copies and launches.

```bash
ASCEND_RT_VISIBLE_DEVICES=1 ./run.sh --all --device 0
```
