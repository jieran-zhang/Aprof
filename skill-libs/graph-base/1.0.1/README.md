# AProf graph-base 1.0.1 — unsealed candidate

This complete package contains the workflow, skills, Wiki, immutable SkillGraph,
schemas, collector scripts and runtime 0.2.4. It is an **unsealed development
candidate**. Installing it does not approve publication, switch a default or
establish hardware qualification for its changes.

## Install the complete package

Keep the whole package at a retained location outside an optimization task's
scratch directory. Do not extract individual skill folders: they reference
sibling skills, `wiki/`, `experience/`, `schemas/`, `skillgraph/` and `runtime/`.
The installer creates symbolic links to the package; keep the source package
for as long as those links are installed. It refuses to replace existing skills
or links owned by another release.

For an explicitly selected development installation:

```bash
APROF_PACKAGE=/absolute/retained/graph-base/1.0.1
APROF_HOST_SKILLS=/absolute/host/skills
python3 "$APROF_PACKAGE/tools/release.py" --allow-unsealed
python3 "$APROF_PACKAGE/tools/install.py" --allow-unsealed \
  --runtime --skills-dir "$APROF_HOST_SKILLS"
"$APROF_PACKAGE/tools/aprofctl" graph validate \
  --graph "$APROF_PACKAGE/skillgraph/versions/v0002"
```

`--allow-unsealed` checks package structure, registry and graph checksums. It
neither creates nor bypasses `release.json`, and it grants no performance or
publication verdict. Without that flag, the tools require a sealed manifest
and verify every payload file. Do not manufacture a stable manifest to install
a candidate. If a future release is explicitly sealed, omit the flag and use
`python3 tools/release.py` from that package for the standard integrity check.

`tools/aprofctl` chooses this package's runtime and uses `.runtime-env` when
available. Invoke it by its package path, or use that environment's installed
`aprofctl`; a bare system command may select another version. Resolve installed
skill symlinks before deriving the package root. No development checkout or
`scaffolding/` scripts are needed for the packaged entry points.

## Optimize an operator

Start with [the workflow skill](skills/ascendc-aprof-workflow/SKILL.md). It follows
architecture and semantics → diagnosis → parallel design → execution
optimization → validation. Load the stage skill and, when relevant conditions
or counterexamples matter, one page from [the Wiki index](wiki/index.json).
SkillGraph governs legal routes; the runtime governs machine admission.
Missing predicates stay unknown.

Use `tools/aprofctl task workspace-create --task-id <task-id>` to create owned
`scratch/` and `final/` directories. Add `--collect` only when post-task collection
was requested. The [lifecycle commands](workflows/references/workflow-details.md#task-workspace-and-budget-commands)
cover budget replay and cleanup; [local gate commands](references/contracts.md#task-local-gates)
keep evidence local and emit a new index without overwriting its input.
Before `task run`, the trusted controller freezes this complete package with
`local_archive.freeze_package_identity(local)` and includes its reference as
the job's `package_identity_ref`. Execution and collection verify that identity;
the current default cannot reinterpret a task created with another package.

Use the packaged [collector interface](skills/ascendc-aprof-profiling/references/collector-interface.md)
and [Task v5 protocol](skills/ascendc-aprof-profiling/references/shared-timing.md).
Task v5 binds each case and role to the complete ordered task sequence. Its
complete-call coverage, controls and gate thresholds are unchanged; an
installation check is not an independent measurement qualification.

Keep builds, generated inputs, raw profiles, receipts and local indexes in
private task-local storage. The shared task budget covers generation, review,
build, correctness, timing, profiling and online admission. Record actual model
tokens as cost. A child cannot renew the original deadline; a frozen collection
reserve allows an already started unit to finish without dropping required
samples or checks.

Return the final code and a small report with the exact machine result. A local
index is an online tool input and optional handoff, not an extra permanent
deliverable. The optimization agent does not copy profiles into persistent
storage or perform CAS import. If trace/training collection was requested, a
separate collector receives the complete local evidence after task completion,
before cleanup, and reports its own copying and audit cost. Otherwise clean
only task-owned scratch after delivery and online checks. Preserve user sources,
final deliverables, installed packages and every live symlink target. See
[the lifecycle details](workflows/references/workflow-details.md#runtime-state).

## Inherited evidence and limits

The knowledge inherited from 1.0.0 validates only `exp-tile8192` on 910C/A3 with
CANN 9.0.0. Its successful gate-only continuation retained both preceding
failed attempts. The broader `tile-amortization` page and other optimization
rules remain draft. The 45-run validation comparison and post-seal full test
were not run under the exp-only scope. This candidate makes no five-operator
agent-improvement claim and does not reinterpret old v4 or v5 receipts as
qualification of runtime 0.2.4 changes.

Raw archives and development publication tools are outside this package.
`skillgraph/provenance/` is an immutable historical source snapshot used for
graph lineage; its old links and wording are archival, not online instructions.
Use the current `skills/` and their linked references during optimization.
Neither historical JSONL nor Wiki observations establish policy rewards.
Publication or default changes require a separate explicit release action.
