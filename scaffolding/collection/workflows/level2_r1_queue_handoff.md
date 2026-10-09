# Append-only R1 queue handoff

`prepare-handoff` creates the next numbered queue after an exited candidate child
was conservatively blocked and a later, reviewed classifier closed an explicit
append-only recovery observation. It never modifies an old queue, runs a child,
registers a source, or resets execution costs.

The new `level2_r1_serial_queue_handoff_v1` request preserves the original fixed
schedule and takes its exact remaining suffix. It binds the predecessor request,
blocked state, child argv/exit/logs, completed baseline and earlier R1 receipts,
checkpoints, original blocked observation, recovery request, and new closed
positive source-failure observation. Ancestor continuation/handoff proofs are
recursively reaudited against their own frozen producer snapshots. The new queue
requires current producers to match a fresh engineering snapshot. Finished prefix
receipts keep their original observation IDs, so later R2/R3 work is permitted
only when the recorded R1 evidence remains identical. Unknown infrastructure
failure, incomplete child execution, a changed source, or work already started
in the pending suffix prevents publication.

For the actual queue02 RMSNorm block, after the V6 producer commit and fresh
engineering snapshot, explicitly close `rms_norm001-feedback-01` with the new
observation `rms_norm001-reclassification-01` through the feedback recovery tool.
Then use the following sequence (paths shown relative to the repository):

```sh
python scaffolding/collection/scripts/level2_r1_queue.py prepare-handoff \
  --previous-queue .aprof/runs/level2-skill-graph-base-20261005-experiment/preflight/r1-queue-02 \
  --engineering .aprof/runs/level2-skill-graph-base-20261005-experiment/bootstrap/FRESH-ENGINEERING.json \
  --output .aprof/runs/level2-skill-graph-base-20261005-experiment/preflight/r1-queue-03 \
  --observation-id rms_norm001-reclassification-01
```

The fresh engineering filename must be the actual, already frozen manifest.
Preparation binds AdamW/GN through queue01→queue02, the completed RMS baseline
and failed RMS child, and the remaining 12 original R1 entries beginning at
ArgMax. It requires the actual closed recovery observation, not a draft.
Preparation is serialized with the predecessor's read-only lock and audits its
proof twice. Both new request and initial state are fsynced in a private sibling
directory before one rename publishes them. Write/staging-sync/rename failures
leave no official partial queue. A parent-directory fsync failure after rename
can leave the complete queue published: inspect it explicitly before continuing.
There is no automatic retry of native work.

Only the device owner should subsequently execute:

```sh
python scaffolding/collection/scripts/level2_r1_queue.py run \
  --queue .aprof/runs/level2-skill-graph-base-20261005-experiment/preflight/r1-queue-03 \
  --max-new-operators 1
```

Existing direct and queue02 request versions remain readable. Every new child
phase reaudits the entire inherited prefix. The existing strict producer checks,
source-preview equality, normal/swapped measurement protocol, explicit recovery,
and complete-operator pause semantics are unchanged.
