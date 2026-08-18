# depthwise_conv_2d direct invoke

Correctness-first Ascend C direct-invoke implementation for the 20 original
`third_party/cann-bench/tasks/level3/depthwise_conv_2d` cases.

```bash
ASCEND_RT_VISIBLE_DEVICES=1 ./run.sh --case 1 --device 0
ASCEND_RT_VISIBLE_DEVICES=1 ./run.sh --all --skip-build --device 0
```
