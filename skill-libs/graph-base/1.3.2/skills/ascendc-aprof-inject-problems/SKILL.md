---
name: ascendc-aprof-inject-problems
description: 生成算法选择诊断用的 Ascend C 对照 kernel，包含完整排序代替 TopK 和两遍统计 Softmax，并保存正确性约束和 CPU oracle。
---

# 算法选择注入

从完整包根运行下列命令。每次使用新的输出目录，生成 baseline 和 injected kernel、清单及算法工作量说明。

```bash
python3 skills/ascendc-aprof-inject-problems/tools/inject_case.py --recipe full_sort_for_topk --size 128 --k 4 --output /dev/shm/aprof-topk
python3 skills/ascendc-aprof-inject-problems/tools/inject_case.py --recipe two_pass_softmax --size 128 --output /dev/shm/aprof-softmax
```

在 asc-tools 仓库根运行时，在上述脚本路径前添加 `skills/tool-ops-optimize/`。

内容与输入边界见[算法 recipe](references/algorithm-recipes.md)。工具返回失败时检查参数或已有输出目录，保留原有产物。硬件执行由[直调技能](../ascendc-kernel-direct-invoke/SKILL.md)接入工程，构建命令按[编译说明](../ascendc-kernel-direct-invoke/references/build-kernel.md)选择。

注入器注册为辅助评测能力，由 coordinator/diagnosis 在明确评测任务中调用。生成的 Ascend C kernel、CPU oracle、构建结果与设备验证分别记录。旧六篇 tiling 注入文档的能力范围已移出本版，现行入口只登记本页列出的两个算法 recipe。
