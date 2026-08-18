# moe_finalize_routing direct invoke

Correctness-first Ascend C implementation of all 20 original level-3 MoeFinalizeRouting cases.
The executable launches a custom device kernel directly through ACL; it does not call ACLNN.

Run on the assigned physical device with:

```bash
ASCEND_RT_VISIBLE_DEVICES=1 ./run.sh --all --device 0
```
