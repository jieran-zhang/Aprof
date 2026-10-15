# Cummin partial A/A output maintenance

`level2_partial_control_output_dedup.py` preserves every logical native output
path and byte while hardlinking identical packed, `values`, and `indices`
payloads. It does not turn a failed or incomplete six-process control into a
calibration, publish a report, change msprof timing, or retire raw/verification
evidence. Use it only for Cummin's full 20-case baseline A/A schedule.

The tool verifies the frozen six-process stage plan, each selected terminal
passed session, all 80 validation rows per session, all 80 output bundles, and
the recorded SHA-256 of every packed and named output. A read-only invocation
is the default. `--apply` writes a durable manifest before any hardlink
replacement, then a completion receipt after rehashing each canonical payload
and checking every logical alias. Reentry rechecks all paths and the immutable
manifest. A failed transaction retains all logical paths and can be audited
again; it does not delete a bundle or raw profiler file.

For a terminal failed stage, all writers must have exited. Use
`--writers-closed --last-session NAME`; only the passed session prefix through
`NAME` is admitted. For an open stage, the serial coordinator must stop its
Python process with `SIGSTOP` **after** a selected session's `completion.json`
is terminal passed and before the next native process starts. The tool then
requires `--paused-coordinator-pid PID`, checks the stopped process and exact
session prefix, and does not take the host lock held by that process. The
coordinator must remain stopped until the maintenance receipt and reader
replay finish. Resume it with `SIGCONT`. The pause is between independent
native processes, never inside a timed sample. Do not run a second NPU task or
the ordinary stage-level dedup tool concurrently.

The preexisting `level2_storage.py` correctly rejects a failed whole stage and
an incomplete six-process cohort. The partial-session receipt is a separate
maintenance record, not a substitute for those authorities. Subsequent final
calibration still requires a new six-process A/A report and all original
protocol checks. Existing raw/native/verification archive admission rules
remain unchanged; evidence outside their reader scope stays loose.
