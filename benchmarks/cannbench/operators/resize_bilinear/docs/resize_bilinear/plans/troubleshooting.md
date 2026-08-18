# Troubleshooting

## dav-2201 B16 数据路径

- Risk：2B GM 标量写可能产生近零/丢失输出。
- Prevention：FP16/BF16 输出统一经 FP32 UB、向量 Cast、DataCopyPad DMA 写回；输入软件解码。

## 当前 agent NPU 隔离

- Symptom：同线程此前 `aclInit` 返回 500000。
- Resolution：本地编译后把 binary hash 与 case 命令交给可访问真实 NPU 的主线程，读取共享 result 迭代。

## FP32 align=true 大倍率上采样近零误差

- Symptom：case 5 首版 MERE 很低但 MARE=40.38，max_abs=0.00257。
- Root cause：kernel 使用 `o*(I-1)/(O-1)`，而 PyTorch 先计算 FP32 scale 再执行 `o*scale`；非结合浮点运算放大坐标舍入。
- Resolution：align=true 改为 `scale=(I-1)/(O-1); coord=o*scale`，false 同样先算 `scale=I/O`。新 binary 的 case 5 max_abs 降为 `2.29e-5` 并通过原始门槛。
- Prevention：插值坐标不仅公式相同，FP32 运算顺序也必须与 golden 对齐。
