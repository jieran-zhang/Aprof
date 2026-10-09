# R1 queue continuation after the GroupNorm guard block

The suffix coordinator starts with `rms_norm` and runs the 13 remaining R1 operators in the original frozen schedule. It uses a new request version, `level2_r1_serial_queue_suffix_v1`, and a new engineering snapshot. The original `r1-queue-01` remains blocked with its original producer identities, logs, checkpoints, and receipts unchanged.

Before preparation, the coordinator must finish the explicit, append-only GroupNorm feedback reclassification. That recovery must positively classify the recorded guard failure, close the original source round in a new observation, and preserve its source, original blocked feedback, stages, guard completion, and execution costs. A generic nonzero verifier exit is insufficient. No native rerun is part of queue preparation.

Prepare the new queue while other controllers are quiescent:

```text
python scaffolding/collection/scripts/level2_r1_queue.py prepare-continuation \
  --previous-queue <run>/preflight/r1-queue-01 \
  --engineering <run>/bootstrap/<new-frozen-engineering>.json \
  --output <run>/preflight/r1-queue-02 \
  --observation-id <closed-group_norm001-reclassification-observation>
```

Preparation binds the original queue request/state/block, Adam's baseline and candidate finished receipts, GroupNorm's baseline finished receipt, both operator checkpoints, the complete exited GroupNorm candidate child record and logs, and the new GroupNorm recovery request/closed observation. All are SHA-256 pointers in the immutable new request. Historical producer bytes are checked against their original frozen snapshots. New producer bytes must match the new engineering snapshot and the current files. The suffix keeps the original source previews, proposals, case policies, local profiler storage, `local-raw-01` epoch, `aa-local-01` calibration group, and output deduplication settings.

The previous queue's exclusive lock prevents concurrent preparation or a live predecessor. All new request/state data are written and synchronized in a private sibling staging directory before one directory rename publishes queue-02. A write or rename failure before publication leaves no official partial queue. A failure of the parent-directory fsync after rename can leave a complete published directory with an unconfirmed durability result; the command reports failure and a coordinator must inspect it instead of retrying or replacing it.

Run the new queue with the existing operator-boundary pause:

```text
python scaffolding/collection/scripts/level2_r1_queue.py run \
  --queue <run>/preflight/r1-queue-02 --max-new-operators 1
```

Each run, and each phase within a run, reaudits the inherited evidence before launching a child. It does not create new execution receipts for Adam or GroupNorm. Completed suffix receipts are reaudited and skipped on resumption. Existing baseline stages outside the old queue remain subject to the normal iteration controller's identity checks; the queue does not synthesize their results. Unknown infrastructure failures still stop the entire queue. Missing child exits still require explicit recovery. Source failures count only when the classifier proves them and feedback is closed.

This is a bounded transfer for queue-01's Adam/GroupNorm prefix and the original RMS-first suffix. It does not implement arbitrary queue slicing, source authoring, a fourth source round, automatic repairs, producer rebinding of an existing request, or a new measurement protocol. Later registered sources for the two inherited completed R1 operators are permitted while their pinned R1 observations and evidence remain unchanged. The 13 pending entries remain restricted to their original R1 source until each finishes.
