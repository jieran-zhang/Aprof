# gcd AscendC 直调算子

面向 Ascend910 / `dav-2201` 的独立编译、运行和精度验证框架，支持 `int16`、
`int32`、`int64`、最多 8 维广播、零值、负数和各 dtype 的最小值语义。

```bash
./run.sh --case 1 --device 2
./run.sh --all --device 2
```

`run.sh --all` 严格执行上游 `cases.yaml/cases.csv` 的 20 个原始 case；每个 case 的
逐元素精确比对写入 `build/cases/case_XX/result.json`，汇总写入 `results.json`。

实现与语义说明见 `docs/gcd/`，环境证据见 `docs/environment.md`。
