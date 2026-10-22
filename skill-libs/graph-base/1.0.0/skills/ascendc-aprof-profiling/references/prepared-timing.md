# Reusable preparation and persistent device timing

The preparation helper below remains supported. The two-process timing example
is retained for diagnostic compatibility. Its role-specific contexts and
allocations do not establish comparable measurement conditions; runtime 0.2.3
requires the [shared-buffer protocol](shared-timing.md) for new measured
admission, even when a legacy report says `stable=true` or `mode=formal`.

Use these helpers for a project with explicit preparation, execution and
verification commands. They do not automatically convert an arbitrary operator
or supply its mathematical oracle. Keep the baseline read-only and instrument
isolated copies consistently before comparing them.

## Prepare inputs and oracle files once

```bash
python3 scripts/prepare_workload.py --config <preparation.json> \
  --cache-dir <task-prepared-cache> --receipt <new-preparation-receipt.json>
```

Example configuration, with actual existing files substituted:

```json
{
  "schema_version": "1.0.0",
  "workload": {"shape": [1024, 1024], "dtype": "float16"},
  "dependencies": {
    "python": "/absolute/python3",
    "generator": "/absolute/scripts/generate.py",
    "oracle": "/absolute/scripts/oracle.py"
  },
  "commands": [
    ["{dep:python}", "{dep:generator}", "--output", "{output_dir}"]
  ],
  "outputs": ["input.bin", "expected.bin", "metadata.json"],
  "timeout_seconds": 300,
  "environment": {}
}
```

Every preparation command starts with an explicit `{dep:name}` executable.
Declare all files affecting generation/oracle semantics as dependencies, even
when imported rather than directly invoked. Declare any environment values
that affect preparation. The helper cannot discover undeclared dependencies.
Only the helper's default `PATH`, `LANG` and `LC_ALL` plus the explicit
`environment` are passed to preparation commands. Ambient CANN, `PYTHONPATH` or
library-path settings are not inherited; declare required values explicitly.

The cache key binds workload, dependency bytes, command templates, expected
outputs, declared environment and producer identity. Dependency locations are
excluded so byte-identical project copies can share preparation. A cache hit
requires verified dependency/output integrity; it emits a new hit receipt and
references the immutable preparation evidence. This caches data generation,
**never candidate correctness**.

Outputs live at stable paths from the beginning so metadata containing absolute
input paths remains usable. Only a successful, verified attempt is published as
ready. Failed attempts remain inspectable and cannot become hits. Output/cache
symlinks are refused. A busy per-key lock fails explicitly; do not remove a
stale-looking lock without first resolving its owner and retained attempt.
Moving the cache to another absolute location is refused because metadata may
embed the original paths; regenerate preparation at the new location.

Keep candidate output files outside the shared prepared cache. Every changed
candidate still runs the full correctness contract using the prepared inputs
and oracle; each timing role also verifies its final timed-path output.

## Instrument the complete operator call

The bundled `assets/device_timer.h` supplies `aprof::Run` for an ACL stream,
logical device, operator name, launch count and a callback performing **one
complete operator invocation**. Integrate it in the host path where inputs,
allocations and H2D are already prepared. The callback must include all kernels
and required in-stream dependencies of that invocation. Preserve the ordinary
correctness path and copy/write outputs after timing completes.

Baseline and candidate must use the same timing adapter and interval boundary.
Record each role's actual launches per complete invocation; algorithm changes
can legitimately change that count. Keep setup, file IO, D2H and verification
outside the event interval. Do not substitute a single convenient kernel for a
multi-kernel operator. This helper uses device-event intervals, not msprof task
duration or command wall-clock time.

`aprof::Run` returns `void`: with timing disabled it invokes the callback once;
in interactive timing mode it serves samples until `quit`, then returns. Keep
the host's normal D2H/output path after the call in both modes.

## Legacy two-process diagnostic job

```bash
python3 scripts/device_paired_timing.py --config <timing.json> \
  --output <new-timing-directory>
```

Configuration shape (this one-case example is an exploratory screen):

```json
{
  "schema_version": "1.0.0",
  "operator": "exp",
  "device": 0,
  "mode": "explore",
  "pairs": 6,
  "warmup": 10,
  "repeat": 100,
  "timeout_seconds": 180,
  "expected_case_ids": [1],
  "baseline": {
    "cwd": "/absolute/baseline",
    "source_dir": "/absolute/baseline",
    "binary": "/absolute/baseline/build/exp"
  },
  "candidate": {
    "cwd": "/absolute/candidate",
    "source_dir": "/absolute/candidate",
    "binary": "/absolute/candidate/build/exp"
  },
  "cases": [{
    "case_id": 1,
    "workload": {"shape": [1024, 1024], "dtype": "float16"},
    "prepared_files": [
      "/absolute/prepared/metadata.json",
      "/absolute/prepared/input.bin",
      "/absolute/prepared/expected.bin"
    ],
    "baseline": {
      "command": ["/absolute/baseline/build/exp", "<actual input/output arguments>"],
      "verify_command": ["/absolute/python3", "/absolute/baseline/scripts/verify.py", "<actual verification arguments>"],
      "output_files": ["/absolute/timing-outputs/baseline-case-01.bin"],
      "launches_per_operator": 1
    },
    "candidate": {
      "command": ["/absolute/candidate/build/exp", "<actual input/output arguments>"],
      "verify_command": ["/absolute/python3", "/absolute/candidate/scripts/verify.py", "<actual verification arguments>"],
      "output_files": ["/absolute/timing-outputs/candidate-case-01.bin"],
      "launches_per_operator": 1
    }
  }]
}
```

Use actual argv arrays matching the project's host and verifier. List all
metadata, input and oracle files read during verification in `prepared_files`;
the helper also binds source/binary and verifier executable/script identity.
Each case/role requires `output_files`: absolute paths that are absent before
the run, disjoint across roles/cases, and outside prepared-file directories and
both source snapshots. Bind the execution and verification argv to those actual
output paths. After both children quit, the helper requires regular nonsymlink
outputs and verifies their hashes remain unchanged across verification. Keep
the timing output directory outside both source snapshots as well; source
mutation during a run invalidates its evidence.
Timing and verification argv are literal; the helper performs no placeholder
substitution. The angle-bracket text above must be replaced before execution.
The target argv executable must resolve to that role's declared binary.

Each case starts two persistent children, baseline then candidate. The
coordinator requests alternating AB/BA samples sequentially; each event sample
contains `repeat` complete calls and reports time per call. Both children exit
before their final outputs are verified. This avoids a process launch per
sample, but it is **not** one shared A/B native process or context. ACL graph
capture/replay is not part of this protocol. The helper holds an advisory device
lock for collection; keep the mapped physical device exclusive and preserve
logical/physical mapping in session evidence. Top-level `physical_device`
defaults to `device` only without a visibility mask. When
`ASCEND_RT_VISIBLE_DEVICES` or `ASCEND_VISIBLE_DEVICES` is set, explicitly supply
`physical_device`; the helper checks numeric mask mappings before locking.

- `explore` defaults to six pairs, ten warmups and repeat 100. Its formal
  projection is empty even when samples look stable. The coordinator applies
  the predeclared screen/extension rule; the helper does not select a winner.
- The legacy `formal` setting collects thirty pairs but does not establish
  qualified A/A controls. Use the shared-buffer collector for a finalist.
- Keep `repeat` and comparison policy fixed before observing results. A repeat
  batch is one statistical sample; its internal calls are not extra pairs.

Outputs are `raw_measurements.json`, `measurement_report.json` and
`timing_draft.json`. Formal reports use equal-case geometric aggregation and
provide a gate projection only when the measurement checks pass. These remain
drafts: retain full correctness, collect compatible finalist mechanism evidence
through [the collector](collector-interface.md), then submit the existing
[machine contracts](../../../references/contracts.md). Neither helper grants
production eligibility, a formal verdict or training reward.
