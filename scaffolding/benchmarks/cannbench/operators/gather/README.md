# gather AscendC 直调算子

面向 Ascend910 / `dav-2201` 的 PyTorch `torch.gather` 语义直调实现，支持 rank 1-8、
dim 0 到 rank-1、六种数据 dtype 和 int8/int32/int64 index。

```bash
./run.sh --case 1 --device 2
./run.sh --all --device 2
```

`run.sh --all` 执行上游 `cases.yaml/cases.csv` 的 20 个原始 case；逐位精度结果写入
`build/cases/case_XX/result.json`，汇总写入 `results.json`。接口没有 `batch_dims`；负
index 和越界 index 属于无效输入并由 host 明确拒绝。

语义和设计见 `docs/gather/`，环境证据见 `docs/environment.md`。
