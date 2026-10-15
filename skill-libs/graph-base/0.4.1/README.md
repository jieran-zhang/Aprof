# AProf graph-base 0.4.1

This directory is the complete, canonical skill library. Copy it anywhere to use
it independently. It contains the optimization workflow, core/support skills,
an optional remote adapter, runtime 0.2.0, contracts and immutable v0001/v0002
graphs. It derives from skill lib 0.4.0 at `d8f6837`.

## Install and verify

From this directory, use Python 3.11 or later:

```bash
python3 tools/install.py --runtime
python3 tools/release.py
./tools/aprofctl graph validate --graph skillgraph/versions/v0002
```

The installer creates a version-local `.runtime-env` and installs the declared
Python dependencies. The launcher always selects this directory's runtime, even
if another version is on PATH. Hardware execution additionally needs the target
CANN SDK, compiler, profiling tools and NPU access. Plan-only use does not execute
hardware. Remote execution is optional; add `--with-remote` to install its Python
dependency and explicitly select the adapter when needed.

For a filesystem skill host, expose the core/support skills with
`python3 tools/install.py --skills-dir <host-skills-directory>`. This creates
links to this complete release, so retain the directory. Add `--with-remote`
only to expose the optional adapter. Switching versions requires removing the
previous managed links; the installer refuses to overwrite other skills.

The release root is also the plugin root: `.codex-plugin/plugin.json` and
`.claude-plugin/plugin.json` discover `skills/`. A host must retain the whole
package, including runtime, graphs and tools. After a plugin host copies the
package into its cache, run the runtime installer in that installed copy. Do not
edit a stable manifest or add a cachebuster; a changed package gets a new version.

## Invoke

Use `ascendc-aprof-workflow` with a complete operator directory, its workload and
correctness contract, execution commands and budget. For example:

```text
Use $ascendc-aprof-workflow.
Prepare a validated optimization plan; do not build or execute hardware.
op_dir: <complete operator project>
budget: {candidate_limit: 1, build_limit: 0, timing_limit: 0, full_profile_limit: 0}
```

The [main skill](skills/ascendc-aprof-workflow/SKILL.md) owns the optimization
procedure. [Stage interfaces](workflows/aprof-performance-workflow.md) describe
handoff. Use `tools/aprofctl` in examples that name `aprofctl`; pass the graph
inside this package explicitly. New stage-aware sessions use v0002.

## Version and evidence boundary

`release.json` seals package bytes and binds independent skill/runtime/graph
versions. Installation state is excluded from the seal. Runtime state belongs
under the operator's `.aprof/`, never in this library. Campaign policy, lesson
curation and training are external callers; they cannot change this release.

Graph snapshots and their logical provenance paths are preserved byte for byte.
`skillgraph/provenance-paths.json` locates the retained source evidence. v0001
validates as a historical snapshot, but its original compilation digest differs
from the documents at the 0.4.0 source commit. Do not overwrite it to make a
recompilation match. v0002 is a reproducible overlay on the frozen v0001 graph.
