# 算法 recipe 与诊断对照

两个 recipe 均使用有限 FP32 输入，长度为 1 至 2048，单 block 独占完整输出。TopK 按值降序、同值原索引升序返回值和 int32 索引，要求 `1 <= K <= N`。Softmax 保留稳定最大值平移，完整输出对 oracle 使用任务声明的误差规则。NaN、Inf 和其他 dtype 需先建立专门契约，生成器拒绝超出这里声明的范围。

## full_sort_for_topk

baseline 只执行 K 轮选择，injected 执行 N 轮完整选择排序，再取前 K。两者相同的比较规则保证重复值和负数的顺序一致。源码中比较次数分别为 `K*(2*N-K-1)/2` 和 `N*(N-1)/2`。当 K 接近 N 时算法额外工作很少，保留为负对照。

C1 比较实际排序范围与输出 K，记录额外比较和访存的源码依据，进入算法选择候选。C2 阅读[Sort/TopK 模板](../../ascendc-aprof-parallel-planning/knowledge/families/sort-topk/templates/merge.md)，比较局部 TopK、归并和完整排序。性能计数按实际版本映射 Vector/Scalar 指令，源码工作量比与设备 PMU 运算比分别记录。

## two_pass_softmax

baseline 第一遍在线更新 running max 与归一化和，第二遍输出。injected 分别扫描最大值、扫描指数和、最后输出，共三遍输入读取。两者保持最大值平移及完整归一化。在线更新与分阶段归约可能产生浮点舍入差异，正确性按完整输出误差规则验证。

C1 核对全行重复扫描与归约依赖，提出算法/访存放大的假设。C2 阅读[统计归约](../../ascendc-aprof-parallel-planning/knowledge/families/reduction/templates/statistics.md)与[Split-KV](../../ascendc-aprof-parallel-planning/knowledge/families/flash-attention/templates/splitkv.md)，检查驻留容量及数值合并条件。最终输入流量从同层级同方向的硬件数据核对，缓存命中会改变 GM/HBM 的实测差异。

## 验证与 alignment

CPU oracle 覆盖小输入、重复值、负值、K=1、K=N 和大数值跨度。实际生成的 baseline/injected 源码使用相同输入、输出类型和长度。构建两份 kernel 后，分别对全部输出和 TopK 索引执行设备正确性验证，再测完整调用。

盲测诊断者仅接收源码、workload 和已采集证据。生成器标签单独保留，完成诊断后再比较预先声明的算法 family 与实际判断，逐 case 记录 hit/miss/unsupported。标签不进入诊断输入。尚未执行的硬件验证和盲测保持 pending。

## 已核验的设备入口

生成器还提供 `baseline-run.asc` 和 `injected-run.asc`，包含 ACL 启动、固定输入、完整输出 oracle 与非零失败退出码。CANN 8.5 / dav-2201 使用纯 AIV 编译，命令中的源码路径选择刚生成的文件。

```bash
bisheng -std=c++17 --cce-aicore-arch=dav-c220-vec --cce-aicore-lang baseline-run.asc \
  -I "$ASCEND_HOME_PATH/include" \
  -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw" \
  -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw/interface" \
  -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw/impl" \
  -L "$ASCEND_HOME_PATH/lib64" -lascendcl -lruntime -lstdc++ -lm -o baseline-run
./baseline-run 0
```

第二个程序用相同命令替换源码和输出名。参数 0 是本次运行的可见设备 ID，按实际授权设备调整。硬件验证覆盖本次固定输入，扩展输入域仍须增加相应 oracle 与设备检查。
