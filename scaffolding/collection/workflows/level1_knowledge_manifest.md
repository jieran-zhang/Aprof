# Level1 knowledge manifests

`scaffolding/collection/scripts/prepare_level1_knowledge.py` prepares the starting context for a fresh
optimization agent. It does not build, profile, execute an operator, or alter
canonical source, skills, or graph state. The historical CANNBench dataset revision remains pinned for task parity. Skill
knowledge is now self-contained under `skills/aprof`; preparation hashes its
complete local registry inventory and requires no external skill checkout.
Existing frozen manifests keep their original provenance.

```bash
python3 scaffolding/collection/scripts/prepare_level1_knowledge.py audit \
  --output .aprof/dependency-audit/level1-task-parity.json

python3 scaffolding/collection/scripts/prepare_level1_knowledge.py prepare \
  --operator foreach_norm --split train \
  --run-id level1-001 --session-id foreach-norm-worker-001 \
  --output .aprof/runs/level1-001/train/foreach_norm/knowledge
```

The output directory cannot contain prior files. Optional `--commands` accepts a
JSON object containing the campaign's prepared build, correctness, timing and
profiling commands; the helper only records these commands. Each manifest
contains the task's 20 cases, sentinel cases, baseline file hashes, published
graph and schema hashes, dataset revision, required workflow/architecture/parallel-planning skills, targeted
local references and one applicable operator playbook. The seven authorized tasks have fixed train/validation roles;
sealed tasks and cross-split preparation are rejected.

The knowledge catalog is not an assertion that its contents were read. A fresh
agent reads actual content through:

```bash
python3 scaffolding/collection/scripts/prepare_level1_knowledge.py read \
  --manifest .aprof/runs/level1-001/train/foreach_norm/knowledge/manifest.json \
  --reference ascendc-aprof-workflow \
  --used-for 'Start the frozen trace-producing workflow' --role optimizer
```

Only this command returns content and appends a purpose, resolved path, content
hash, manifest hash and chained read hash to `knowledge_reads.jsonl`. All reads
are locked and flushed before content is returned. Changed manifests/references
and incomplete or corrupt read logs are rejected. The campaign coordinator can
import these exact records and files into its event stream and CAS. Repository
skill names and historical aliases resolve through the capability registry;
local reference files can resolve to the generated portable bundle, whose
real path/hash are explicitly recorded. External skill paths are rejected;
benchmark-injection materials are outside this catalog.

The parity audit compares every shape, dtype, attribute, input range and
per-dtype threshold with frozen upstream task files. Its active accuracy
contract is the user-selected local baseline verifier: finite-value MERE/MARE
and NaN/Inf position matching. This is distinct from the complete upstream
evaluator's FP64/native, small-value and cancellation behavior. In particular,
the local Mish oracle uses stable NumPy softplus, while the upstream task calls
`torch.nn.functional.mish`. The audit preserves both oracle/checker hashes and
these limitations; it never claims official evaluator equivalence.

Portable Codex bundles use a byte-identical per-skill copy of shared legacy
contracts. The registry generator also rewrites cross-skill links to the flattened plugin
layout; the canonical source remains under `skills/aprof`. Regenerate and validate with:

```bash
python3 scaffolding/tools/sync_aprof_registry.py write
python3 scaffolding/tools/sync_aprof_registry.py check
python3 -m unittest discover -s tests -p 'test_level1_knowledge.py'
```
