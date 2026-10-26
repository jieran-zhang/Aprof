# 结构回放示例

`single/`和`multiple/`各自包含完整的任务内reasoning、decision/v3、C1/C2/C3 v4、源码文本引用和真实D6/P3/O6文档快照。引用均相对于各自任务目录；复制整个技能包后仍可回放。

这是开发验收fixture：源码是合成文本，事实是纸面假设，没有编译、oracle或硬件测量。校验结果`implemented`只说明该fixture满足交接结构与身份条件，不证明真实AscendC已实施或性能提高。

- `single`覆盖一个搬运合并Action及完整配套步骤。
- `multiple`刻意覆盖`coalesce_contiguous_transfers`与`batch_writeback`两个注册Action的独立实例/路由和共同计划；不是要求把同一工作拆成两个Action。优化中是否需要组合仍由共同工作和代价比较决定。

开发者可按需使用现有`knowledge validate-chain`入口回放，`--root`指技能包，`--task-root`指对应示例目录，`--c1/--c2/--c3`指该目录中的JSON。没有新必跑命令，也不需要timing。真实无工具方案及其正文采用见[行为报告](../BEHAVIOR.md)，联合工作与资源规则见[方案说明](../../../../../skill-libs/graph-base/1.3.1/workflows/references/optimization-schemes.md)。
