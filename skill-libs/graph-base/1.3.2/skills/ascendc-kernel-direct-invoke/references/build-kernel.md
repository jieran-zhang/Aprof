# kernel 编译命令与 SDK 兼容

从完整包根取得脚本绝对路径，再从包含 `op_kernel`、`op_host` 的工程目录调用，显式传入目标 ISA。

```bash
bash /path/to/skills/tool-ops-optimize/skills/ascendc-kernel-direct-invoke/references/build_kernel_o.sh probe probe.asc build_probe dav-2201 aiv
```

编译器与链接器取当前 `ASCEND_HOME_PATH/bin`。脚本检查输入文件、工具可执行权限，从 `bisheng --help` 选择已公布的 `--asc-aicore-lang` 或 `--cce-aicore-lang`，使用设备侧单编译选项，再由 `ld.lld -m aicorelinux -Ttext=0 -static` 生成 simulator 所需设备 ELF。host include 目录按 `uname -m` 选择。

2026-11-09 在现有 CANN 8.5 环境复现旧命令失败，诊断为不支持 `--asc-aicore-lang`。实际 SDK 公布 `--cce-aicore-lang`。950/dav-3510 还要求编译器支持该 ISA，编译器明确拒绝时停止并升级到匹配 SDK。输出 ELF 的链接成功状态与设备正确性分别记录。

完整日志与 review 对应关系见[评审修复说明](../../../references/review-repairs.md)。

显式 AIV/AIC 选择作为第五个参数传入，当前已核验 dav-2201 对应 dav-c220-vec / dav-c220-cube。auto 保留 SDK 默认选择。直接使用 --npu-arch 在该 SDK 下可能生成混合核代码，纯 Vector 案例须选 AIV。其他 ISA 的单核类型选择需核实匹配 SDK 后使用。
