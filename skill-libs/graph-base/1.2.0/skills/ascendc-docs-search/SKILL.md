---
name: ascendc-docs-search
description: 从已安装的 CANN 头文件和匹配版本的官方文档核实 Ascend C API，不依赖外部搜索技能。
---

# AProf API 来源查找

从实际构建、执行所用的 `ASCEND_HOME_PATH` 开始，用 `rg` 查准确 API 名，检查声明、特化与目标宏，并记录 SDK 版本和文件 hash。平台 API 重点看 `include/platform/soc_spec.h` 与 `asc/include/utils/tiling/platform/platform_ascendc.h`；目录随版本变化。

本地头文件不能确定语义时，查匹配 CANN 版本的 [官方文档](https://www.hiascend.com/document) 或 [CANN 源码](https://gitcode.com/cann/asc-devkit)。[asc.gitcode.com](https://asc.gitcode.com) 跟随 master，需记录修订版本，不能视为已安装版本。

返回准确声明、支持架构/dtype、单位、对齐、生命周期、证据位置和剩余不确定性。文档不能证明性能收益；无需为此安装外部 skill、配置 API key、自建搜索后端或复制私有文档。
