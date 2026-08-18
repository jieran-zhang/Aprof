# AProf Workflow Quickstart

## Install in Codex

From the AProf repository root:

```bash
codex plugin marketplace add "$PWD"
codex plugin list --marketplace aprof --available --json
codex plugin add aprof-performance-workflow@aprof
python3 -m pip install -e .
```

The first command registers `.agents/plugins/marketplace.json` and is only
needed once per checkout. The last command installs the separate `aprofctl`
runtime; plugin installation alone does not install the Python entry point.
Start a new Codex thread after installation.

## Install in Cursor

```bash
bash plugins/aprof-performance-workflow/init.sh
python3 -m pip install -e .
```

Remote execution and benchmark generation are separate opt-ins:

```bash
bash plugins/aprof-performance-workflow/init.sh --with-remote
bash plugins/aprof-performance-workflow/init.sh --with-benchmark-tools
```

The benchmark option installs the independent injection system. It does not
become a dependency or prior of the production workflow.

## Verify the static library

```bash
python3 scripts/sync_aprof_registry.py check
python3 scripts/compile_seed_graph.py --check
aprofctl graph validate --graph skillgraph/versions/v0001
```

## Invoke in Codex

Name the skill explicitly when you want deterministic selection:

```text
Use $ascendc-aprof-workflow.
Optimize this Ascend C operator within the stated candidate and profiling
budget. Preserve a versioned AProf trace for every attempted candidate.

op_dir: <path/to/direct-invoke-op>
build_cmd: <command>
verify_cmd: <command>
profile_cmd: <command>
budget:
  candidate_limit: 3
  build_limit: 3
  timing_limit: 2
  full_profile_limit: 1
constraints: production_safe
```

For a safe first run:

```text
Use $ascendc-aprof-workflow.
Build and validate the evidence context and route, but do not execute a patch or
hardware command.
op_dir: <path/to/direct-invoke-op>
budget:
  candidate_limit: 1
  build_limit: 0
  timing_limit: 0
  full_profile_limit: 0
```

## Invoke in Cursor

```text
@aprof-performance-workflow
Optimize this Ascend C operator within the stated candidate and profiling
budget. Preserve a versioned AProf trace for every attempted candidate.

op_dir: <path/to/direct-invoke-op>
build_cmd: <command>
verify_cmd: <command>
profile_cmd: <command>
budget:
  candidate_limit: 3
  build_limit: 3
  timing_limit: 2
  full_profile_limit: 1
constraints: production_safe
```

For planning only:

```text
@aprof-performance-workflow
Build and validate the evidence context and route, but do not execute a patch or
hardware command.
op_dir: <path/to/direct-invoke-op>
```

## Collect profiling evidence from a checkout

Create the stage config described by the profiling skill, preview it, then run
it only after the commands and hardware use are authorized:

```bash
python3 skills/aprof/profiling/scripts/run_profile_stages.py \
  --config .aprof/profile-stages.json \
  --report .aprof/profile-stages.dry-run.json --dry-run
python3 skills/aprof/profiling/scripts/run_profile_stages.py \
  --config .aprof/profile-stages.json \
  --report .aprof/profile-stages.json
```

Compress an exported msprof report without inventing missing counters:

```bash
python3 skills/aprof/profiling/scripts/compress_msprof.py \
  --input <msprof-report-root> --op-name <exact-kernel-name> \
  --available-cores <count> --output .aprof/profile-symptoms.json
```

For cheap paired timing, save a timing-only config (no build, data generation,
or verification inside either command):

```json
{
  "schema_version": "1.0.0",
  "baseline": {"cwd": "/abs/path/baseline", "command": ["bash", "run_timing.sh"]},
  "candidate": {"cwd": "/abs/path/candidate", "command": ["bash", "run_timing.sh"]},
  "pairs": 30,
  "warmup": 5,
  "timeout_seconds": 120
}
```

```bash
python3 skills/aprof/profiling/scripts/paired_timing.py \
  --config .aprof/paired-timing.json \
  --output .aprof/paired-timing-output.json
```

All three outputs are drafts. The compressor keeps ambiguous candidate
mechanisms and `unknown` fields; it does not finalize root cause. The paired
timer does not issue an LCB verdict. Map the evidence into `context` or
`gate_request` and let `aprofctl` validate and gate the candidate.

## Update or uninstall the Codex plugin

After editing the local plugin, replace its cachebuster, reinstall it, and
start a new Codex thread:

```bash
python3 /root/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py \
  plugins/aprof-performance-workflow
codex plugin add aprof-performance-workflow@aprof
```

Uninstalling the plugin and the runtime are independent operations:

```bash
codex plugin remove aprof-performance-workflow@aprof
python3 -m pip uninstall aprof-runtime
```

If this checkout no longer supplies any installed Codex plugins, also remove
its marketplace registration:

```bash
codex plugin marketplace remove aprof
```

## Runtime sequence

1. Validate the task context and evidence drafts.
2. Route on an immutable graph/policy pair and retain the complete candidate
   distribution and hard masks.
3. Apply one atomic transformation in an isolated candidate tree.
4. Submit raw gate evidence to `aprofctl candidate gate`.
5. Add referenced objects to the task-local CAS.
6. Finalize with the exact graph and behavior policy:

   ```bash
   aprofctl episode finalize --context .aprof/context.json \
     --request .aprof/gate-request.json \
     --graph skillgraph/versions/v0001 \
     --store .aprof/episodes.sqlite
   ```

Runtime state is written under `<op_dir>/.aprof/`. A build or correctness
failure is a valid typed negative episode; it does not require timing samples.

For the first trace study, keep a `handler_attempt` JSON beside each episode
and validate its shape with:

```bash
aprofctl contract validate --kind handler_attempt --input <handler-attempt.json>
```

This sidecar is not part of the strict v1 episode, is not CAS-attested, and is
not consumed by the current policy trainer. From the AProf checkout root, run
`python3 scripts/audit_skillgraph_decisions.py --graph
skillgraph/versions/v0001` before making claims about graph learning.

## Boundaries

- Agents cannot set `selected_as_best`, terminal utility, or policy weights.
- Six historical families are non-exclusive facets, not root-cause labels.
- Missing evidence routes to `unknown_unresolved` or `NOOP`.
- Simulator evidence cannot train production performance value.
- Legacy `optimization_memory.jsonl` and historical demo summaries are not
  verified training data.
