# Repository layout and migration

1.1.0 的脚手架活动入口已收敛到 [两个高层 skill](../README.md)。
它们维护批次组织、独立 memory v3 与三个知识区的离线学习；旧 collection、
curation 和 evidence 留在原路径支持历史回放。以下描述原仓库迁移边界。

Two business roots own the project: complete canonical releases under
`skill-libs/`, and development/collection/evidence under `scaffolding/`.
`migration/paths.json` maps the old tracked paths to the new layout;
`migration/baseline.json` records source commit and frozen artifact hashes.

The first reorganized package is graph-base/0.4.1, based on skill 0.4.0 at
`d8f6837a565e4eb718605a289fa929ebc0c1496f`. Runtime remains 0.2.0. Graph v0001
and v0002, benchmark sources/splits and historical evidence are preserved.
The canonical graph source retains its logical provenance paths. A separate
locator and preserved source evidence support compiler inspection without
rewriting the frozen graphs. The known v0001 source-digest drift existed before
migration; snapshot validation and current-source reproducibility are separate.
The exact frozen and recompiled hashes are recorded in
[graph-reproducibility.json](migration/graph-reproducibility.json). Both compilers
produce the same result before and after migration; v0001's discrepancy is inherited.

## Dependency ownership

The main SKILL.md defines optimization. Workflow details and agent wrappers
reference it. Research campaign cases, pairing policy, recovery, compaction,
lesson generation and training instructions are collection workflows. Generic
runtime contracts and graph logic ship with each release; campaign/measurement/
memory/lesson schemas are collection-owned. Runtime modules stay cohesive.

Collectors select a concrete release through --skill-lib or APROF_SKILL_LIB.
New runs freeze that selection independently of collector producers. No runtime
import resolves catalog.default_release. Imported runtimes from a different
release are rejected rather than silently mixed in one Python process.

A frozen engineering inventory records skill files and collector files
separately while retaining the existing flat producer references needed by
archive readers. The selected release bytes, graph and manifest are hashed.

## Development and release

Copy a release into the next version directory on a development branch; delete
only that new directory's inherited seal and change its registry/plugin version.
Edit the canonical files there. Metadata tooling never produces another skill
copy. Run CPU regressions and independent-package verification, then seal once:

```bash
python3 scaffolding/tools/release_skill_lib.py seal --skill-lib <new-version> \
  --source-commit <source-commit> --source-version <parent-skill-version>
```

Existing seals cannot be overwritten by publication tooling. Update catalog and
root host metadata to select a tested release; keep prior release directories.
Installation environments and host links are not published source files.

## Historical runs

The original checkout and paused run remain in place. Producer absolute paths
and SHA-256 values are part of frozen authority. Do not rewrite them, replace
old directories with symlinks, or resume historical queues with relocated code.
A future execution migration needs the existing explicit continuation/handoff
procedure and a newly qualified engineering epoch. This refactor performs no
hardware execution or raw retirement.
The new report writer and guard runner have explicit migration identities in
[producer-epoch.json](migration/producer-epoch.json) and
[guard-epoch.json](migration/guard-epoch.json). Historical approved hashes remain
available for record validation; newly produced records bind the relocated code.

Compact evidence export selects named artifacts, checks available source hashes,
and retains original bytes. Its catalog is a navigation/byte-integrity view,
not a claim of full semantic closure, formal admission or training eligibility.
External raw locations must be interpreted with archive/maintenance receipts.
