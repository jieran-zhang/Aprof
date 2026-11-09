# BT、FP Buffer 与频率口径

## 独立的存储用途

BT 是 Bias Table Buffer，用于矩阵乘的 bias 输入，Ascend C 的位置名称包含 `TPosition::C2`。FP Buffer 服务于 Fixpipe 的随路转换或量化参数。分别核算两类存储的有效数据、对齐、驻留次数和重叠生命周期。

平台提供 `CoreMemType::BT` 时，用其可用字节数约束 bias tile。令本次同时驻留的 bias 块数为 q，元素数为 N，元素字节为 s，接口要求对齐 a，则 `q * ceil(N*s/a)*a <= available_bt_bytes`。例如已核实 q=2、N=256、s=4、a=32 时需要 2048 B，仍须与本机返回的 BT 容量比较。缺 BT 容量或接口单位时记录 unknown，交回规划者选取有依据的方案。

FP Buffer 容量与 BT 容量分别记录。核实当前 SDK 的 FP 存储位置、量化模式、参数宽度、对齐和可见容量，再计算 `q * align(parameter_count * parameter_bytes)`。SDK 没有公开容量查询时引用对应版本接口约束或设备实测，缺失值保持 unknown。GM workspace、UB、L0C、BT、FP 采用独立的容量账本。

官方示例分别说明 bias 搬运至 C2 参与 Mmad，以及量化参数进入 FP Buffer 参与 Fixpipe。平台版本和数据类型以实际 SDK 为准。[BT 用法](https://www.hiascend.com/document/detail/zh/canncommercial/850/opdevg/Ascendcopdevg/atlas_ascendc_best_practices_10_0028.html)

## Current Freq 与 Rated Freq

`OpBasicInfo.csv` 的 `Current Freq` 表示采集时昇腾 AI 处理器当前运行频率，`Rated Freq` 表示该处理器的理论频率。字段描述以已安装 msprof 对应版本为准。[官方字段定义](https://www.hiascend.com/document/detail/en/canncommercial/850/devaids/optool/atlasopdev_16_0098.html)

原始频率记录必须携带 device/die、core_type、时钟域、单位、采集窗口、工具版本和数据文件 hash。保留 CSV 中的原字段名。Cube、Vector、Scalar、HBM 时钟分别核实，只有原始表头无法定位时钟域时填写 unknown，并补采设备时钟资料。

`Current Freq / Rated Freq` 仅在同一设备、同一时钟域和相同单位下计算。它用于观察运行频率与参考值的差异。周期换算使用同窗口、同引擎的实际时钟 `time_s = cycles / frequency_hz`。DVFS 下保留采样时序，单个瞬时频率不能覆盖整个调用。SKU 配置中的 Cube 理论频率单列为估算依据。

## 消费者与检查位置

C0 架构档案保存容量与时钟来源，C2 将 BT/FP 预算实例化，C3 独立 reviewer 核对最终分配与接口，C4 核对性能比较的频率可比性。指标的统一维护位置见[指标字典](../../ascendc-aprof-profiling/references/metrics.md)。
