# 原始算子 case-06—10：两轮独立静态分析

范围为五个原算子、每项全部原 20 case，共 100 case。原输入和技能包未修改；只执行文件读取、CPU 源码/公式分析、检索展开、路由及契约校验。没有运行原输入生成器或 oracle，没有构建、native、profiling、外网或训练。源码成本是源程序工作量预测，不等同于实际访存流量或耗时。

目标 910C/A3 依据包内 `skills/npu-arch/references/platform-evidence.md` 映射为 `dav-2201`，作为 task-declared 文档适用域。未探测当前设备，实际核数、UB、CANN/编译器和 API 能力仍分别登记为具体缺项。

| 原任务 | R1 选择和具体结构 | R2 更新 | 实际知识如何影响判断 |
|---|---|---|---|
| 06 Gather | `hoist_invariant_control`：owner 起点解码一次，mixed-radix 坐标递推更新非 gather 轴源偏移，rank-1 直接索引；保留原始位宽和非法索引语义。 | 15,250 个边界地址断言覆盖全部 20 case；case 20 证明不能把输出下标直接当输入线性前缀。补记原分段未对齐的物理写所有权缺口。 | `control_metadata_overhead` 和 `hot-loop-address` 将范围限定为地址控制；`gather_output_owned` 要求输出唯一 owner；不因随机 x 访问就强行加载整个源窗口。 |
| 07 StridedSlice | `reorder_contiguous_access`：规范化 shape/step/base，合并连续尾维；连续组 11 case 用同宽 UB 批量搬运，9 case 保留 fallback。T 域 256/1024/4096。 | 81 个边界断言复核负 stride、size-1、新轴及 run 边界；case 20 的 run 为 127，不扩大成整输出。 | `noncontiguous_access`、通用 layout 模板、`coalesce` 和 `valid-length` 确认按真实连续片段分割；没有执行转置，也不读取切片间空洞或尾部越界。 |
| 08 GridSampler3D | `hoist_invariant_control`：同一空间点在 channel 组间共享坐标几何，H 域 4/8/16，T 域 64/128/256/512；保留独立轴权重和原乘加顺序。 | **削弱 R1 预测**：奇数空间尺寸的物理写边界不由逻辑分组保证。R2 保留原对齐线性 owner，仅复用 owner 内完整 channel 平面，头尾片段 fallback；实际收益覆盖必须按真实 owner 重算。 | `control_metadata_overhead`、`hot-loop-address` 支持 channel 不变量外提；`gather_output_owned` 只采用所有权原则；`numeric` 阻止预乘权重或重排浮点累计。 |
| 09 GELU | `dispatch_by_workload`：按 approximate mode 分支分配 UB；tanh 9 case 去除未使用的 5 个 FP32 erf scratch 和 mask，T 域 1024/2048/4096；其余 11 case 保留完整 none 路径。 | T=1024 时显式少分配 20,736 B，属容量公式而非加速结果；确认 none scratch 别名仍有读取，不误删；量化/尾部修正不变。 | `dynamic_shape_mismatch`、连续 elementwise 模板和 `dispatch` 支持 mode 域；`buffer reuse` 仅作生命周期佐证；`numeric` 确认保留原 FP32→int32→FP32 量化。 |
| 10 Sigmoid | `software_pipeline_stages`：2 个物理输入/输出槽、队列深度 1；先当前 DeQue 再预取下一块，prolog/steady/drain，单块 fallback；T 域 2048/4096/8192。 | 核对 1/2/3 tile 调度与全部 20 case 的容量公式；T=4096 的显式缓冲 65,536 B，另加真实 API scratch/reserve；没有证明真实重叠。 | `pipeline_serialization`、连续 elementwise 模板和 `pipeline` 约束槽数、事件与最后读者；`numeric` 确认低精度边界 Cast 不可作为冗余删除。 |

各项均从完整 Problem 目录检索，再选择正文展开，保留检索回执、展开回放、实际正文行号和判断变化记录。全树咨询、所选 Action 的 P 绑定候选、条件采用和正式 C2/C3 选择由 `knowledge-selection-R1.json` / `knowledge-selection-R2.json` 明确区分。P 使用当前选定实例真实调用 `route_parallel`；O 保留真实 Action 绑定内部咨询，没有 confirmed_plan，未伪称正式 C3 路由或已实施结果。

每项入口：`case-XX/结果.md`、`source-analysis-R1.md`、`review-R2.md`、`decision-R1.json`、`decision-R2.json`。源文件及 hash 位于 `source-index.json`；完整矩阵成本位于 `matrix-costs-R1.json`；第二轮新静态证据位于 `static-evidence-R2.json`。最终 API 和 CLI 校验回执分别为 `validation-API-Rn.json`、`validation-CLI-Rn.json`，全体状态以根目录 `validation-summary.json` 为准。

这里构造了 C1 schema、reasoning、decision 的真实验证记录；没有声称 C1–C2 全链已完成。每项 `C2-gap.json` 列出无法构造完整真实 architecture、parallel/dispatch 及实现入口绑定的精确缺项。性能相关条件仍未知：需要真实合法实现、全部原 20 case 正确性验证、目标环境容量/API 回执及可比测量，才能决定保留、回退或调整参数。没有加速比，没有 implemented C3。
