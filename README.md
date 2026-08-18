# AProf

AProf is a profile-grounded, trace-producing Ascend C optimization system. It
keeps the foundation model frozen and separates two layers:

- a small Agent-facing skill/plugin layer for interaction, evidence collection,
  and candidate proposal;
- a machine-authoritative runtime and immutable SkillGraph for routing,
  validation, episode storage, and post-training.

The current `v0001` graph is an expert seed compiled from the repository's
static diagnosis and optimization knowledge. It is a starting prior, not a
trained taxonomy.

See [the training roadmap](docs/training_roadmap.md) for the current fixed-graph
training boundary, episode eligibility rules, operator-disjoint data protocol,
and the staged plan for evidence acquisition, graph evolution, parameter
learning, and transfer evaluation.

## Architecture

```text
Agent-facing skills
  -> versioned context/evidence draft
  -> immutable SkillGraph + compatible policy
  -> isolated candidate proposal
  -> machine candidate gate
  -> content-addressed artifacts + attested append-only candidate episode
  -> fixed-graph policy update
  -> separately validated future graph version
```

The six historical performance families are non-exclusive facets. Runtime
mechanisms and atomic transformations use stable IDs and versions. Agents never
assign `selected_as_best`, terminal utility, or graph updates.

## Repository layout

```text
plugins/aprof-performance-workflow/  # thin Agent orchestration adapters
skills/aprof/                        # user-facing capability skills and human references
skillgraph/source/                   # typed expert seed sources
skillgraph/versions/                 # immutable compiled graph snapshots
schemas/                             # versioned runtime JSON contracts
src/aprof_runtime/                   # validation, routing, gate, episode store, policy runtime
scripts/                             # registry sync and deterministic graph compiler
tests/                               # executable contract/runtime/compiler tests
docs/                                # architecture, decision-surface, and training plans
```

Task-local runtime state belongs under `<op_dir>/.aprof/` and is not committed
to Git.

## Capability packages

`skillgraph/registry.json` is the only source of truth for names, roles,
dependencies, marketplace metadata, and host installation.

- `aprof-skills`: core workflow, diagnosis, profiling, optimization, and
  direct-invoke scaffolding.
- `aprof-performance-workflow`: thin orchestration plugin depending on the core
  skills.
- `aprof-benchmark-tools`: independent benchmark/data-generation package. Its
  injection recipes and labels are not core SkillGraph priors.
- `ascendc-remote-kernel-deploy`: optional execution adapter.

Validate generated installation metadata:

```bash
python3 scripts/sync_aprof_registry.py check
```

Install the core Cursor capabilities:

```bash
bash plugins/aprof-performance-workflow/init.sh
```

Optional adapters are explicit:

```bash
bash plugins/aprof-performance-workflow/init.sh --with-remote
bash plugins/aprof-performance-workflow/init.sh --with-benchmark-tools
```

### Install as a Codex plugin

The Codex plugin and the Python runtime are separate installations. From this
repository root, register the repo-local marketplace and install the workflow
plugin:

```bash
codex plugin marketplace add "$PWD"
codex plugin list --marketplace aprof --available --json
codex plugin add aprof-performance-workflow@aprof
python3 -m pip install -e .
```

`marketplace add` is only needed the first time this checkout is registered.
The marketplace is defined by `.agents/plugins/marketplace.json`; the plugin
manifest is `plugins/aprof-performance-workflow/.codex-plugin/plugin.json`.
Start a new Codex thread after installation so the plugin skills are loaded.

To invoke the workflow explicitly, name its skill:

```text
Use $ascendc-aprof-workflow.
Build and validate an AProf plan, but do not modify source or run hardware.
op_dir: <path/to/direct-invoke-op>
budget:
  candidate_limit: 1
  build_limit: 0
  timing_limit: 0
  full_profile_limit: 0
```

During local development, refresh Codex's cached plugin after changing plugin
skills or metadata:

```bash
python3 /root/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py \
  plugins/aprof-performance-workflow
codex plugin add aprof-performance-workflow@aprof
```

Then start a new Codex thread. The helper replaces the single Codex cachebuster
suffix; it does not require hand-editing the marketplace or Codex config.

To remove only the plugin, and optionally the marketplace registration and
runtime, run:

```bash
codex plugin remove aprof-performance-workflow@aprof
codex plugin marketplace remove aprof
python3 -m pip uninstall aprof-runtime
```

Do not remove the `aprof` marketplace if other plugins from this repository are
still installed. Removing the plugin does not uninstall `aprofctl`, and
uninstalling `aprof-runtime` does not remove the plugin.

## Runtime

Install the dependency-free Python 3.11 runtime if a command entry point is
needed:

```bash
python3 -m pip install -e .
```

The same CLI can be invoked without installation with
`PYTHONPATH=src python3 -m aprof_runtime`.

Core commands:

```text
aprofctl contract validate
aprofctl graph validate
aprofctl graph route
aprofctl candidate gate
aprofctl episode finalize
aprofctl episode verify
aprofctl artifact add
aprofctl artifact verify
aprofctl policy train
aprofctl policy validate
```

Profiling execution is intentionally a separate draft-producing layer. From an
AProf checkout, use the bundled tools to enforce stage ordering, compress raw
msprof CSV, and collect AB/BA command timings:

```bash
python3 skills/aprof/profiling/scripts/run_profile_stages.py \
  --config <profile-stages.json> --report <stage-report.json> --dry-run
python3 skills/aprof/profiling/scripts/compress_msprof.py \
  --input <msprof-report-root> --op-name <exact-kernel-name> \
  --available-cores <count> --output <symptoms.json>
python3 skills/aprof/profiling/scripts/paired_timing.py \
  --config <paired-timing.json> --output <paired-timing-output.json>
```

These outputs are not runtime contract kinds. Map their measured evidence into
`context` or `gate_request`; `aprofctl candidate gate` remains authoritative
for stability, lower confidence bounds, and the verdict.

Finalize with the exact behavior graph and optional learned behavior policy.
Every source, patch, producer, and evidence digest referenced by the complete
gate batch must already exist in the store's CAS:

```bash
aprofctl episode finalize --context .aprof/context.json \
  --request .aprof/gate-request.json \
  --graph skillgraph/versions/v0001 \
  --store .aprof/episodes.sqlite
```

Train an immutable fixed-graph checkpoint only from a verified `EpisodeStore`
SQLite database. Policy training verifies the episode attestations, CAS bytes,
and append-only hash chain before reading any reward:

```bash
aprofctl policy train --graph skillgraph/versions/v0001 \
  --episodes .aprof/episodes.sqlite --policy-version p0001 \
  --output .aprof/policies/p0001.json
aprofctl policy validate --checkpoint .aprof/policies/p0001.json \
  --graph skillgraph/versions/v0001
aprofctl graph route --graph skillgraph/versions/v0001 \
  --context .aprof/context.json --policy .aprof/policies/p0001.json
```

All Agent JSON is draft input. Unknown fields are rejected, candidate gates are
recomputed by the runtime, routes are replayed from the exact graph/checkpoint,
and finalized episodes are append-only. Raw JSON/JSONL episode files are not a
production policy-training input because they cannot prove CAS existence.

## Seed SkillGraph

Compile or verify the expert seed deterministically:

```bash
python3 scripts/compile_seed_graph.py --check
```

The source graph contains:

- six non-trainable anchor facets;
- tri-state evidence predicates with explicit implementation status;
- actionable mechanism nodes plus `unknown_unresolved`;
- atomic transformation contracts plus `NOOP`;
- fixed evidence/facet edges and trainable problem-to-transformation priors.

Unimplemented predicates remain explicitly unimplemented. No threshold or
hardware fact is fabricated to make the graph appear executable.

### Decision surface

Audit the graph-only branch surface with:

```bash
python3 scripts/audit_skillgraph_decisions.py \
  --graph skillgraph/versions/v0001 \
  --output .aprof/v0001-decision-surface.json
```

See [the decision-surface contract](docs/skillgraph_decision_surface.md). The
current classification is
`fixed_graph_edge_ranking_with_handler_parameter_trace_collection`: raw
symptoms may have several candidate mechanisms, but v0001 collapses them into
one-target formal predicates; each actionable mechanism has only one positive
transformation plus `NOOP`; and the runtime does not learn handler parameters
or recovery transitions. A shape-validated `handler_attempt` sidecar can be
kept for offline exploration, but it is not EpisodeStore/CAS-attested and is
not policy-training input.

## Workflow rules

- Keep the baseline project read-only and modify only isolated candidates.
- Preserve the complete legal route candidate set, hard-mask reasons, selection
  mode/seed, selected edge, and true behavior probability.
- Stop a candidate after the first mandatory gate failure and retain the typed
  negative episode.
- Use paired hardware samples for production performance decisions; simulator
  data is feasibility/proxy evidence.
- Preserve build, accuracy, runtime, stable-no-gain, regression, specialized,
  and successful outcomes.
- Express observable session limits with `candidate_limit`, `build_limit`,
  `timing_limit`, and `full_profile_limit`; finalization and store append enforce
  them cumulatively per session.
- Never use legacy flat memory or historical FastGELU demonstrations as verified
  policy reward.

## Development checks

```bash
python3 scripts/sync_aprof_registry.py check
python3 scripts/compile_seed_graph.py --check
PYTHONPATH=src python3 -m unittest discover -s tests
python3 -m pytest -q
```

The minimum system milestone is one versioned route, one isolated candidate,
one machine verdict, one immutable episode, and a reproducible change in
fixed-graph candidate ranking after policy training.
