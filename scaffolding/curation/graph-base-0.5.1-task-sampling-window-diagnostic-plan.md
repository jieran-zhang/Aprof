# Exp Task sampling-window diagnosis (diagnostic only)

The proposed run changes only `APROF_SHARED_REPEAT` in the original exp confirmation binary. It compares cases 1 and 10 at R=100 and R=7300 over six fresh native processes per case and R. No build, kernel edit, prewarm prefix, threshold change, resampling, or publication decision is part of this diagnosis.

## Fixed roster

`diagnose_task_sampling_window.py matrix()` defines 24 unique slots. Even cycles run cases 1,10 and R 100,7300 within each case; odd cycles run cases 10,1 and R 7300,100. A new native process and a separate local msprof profile are required for every slot. The original 19-command confirmation file, warmup (10 per role), three 400-call primes, 30 two-role macro samples, two untimed output snapshots, original binary, inputs, and two independent Python oracles are fixed. The expected Task counts are `1222+30R`: 4222 at R100 and 220222 at R7300.

Each slot has a 1500-second shared deadline: capture at most 900 seconds, optional export at most 300 seconds, each oracle at most 120 seconds. The host and all device locks cover the whole 24-slot matrix. Any capture, CSV, source identity, transfer, or oracle failure stops the matrix; a statistical control failure is retained as a result and the fixed matrix continues. There is one attempt per slot and no resume.

## Evidence and interpretation

Before the native run and again after both oracles, the script hashes the original source, binary, selected prepared input, and profiler. Capture and export run under local `/tmp` scratch. The script copies the complete profile to persistent storage after checking full file inventories; replay needs only that persistent copy. Capture stdout/stderr, native PID, complete input-immutability receipt, all native messages, complete raw Task CSV, each Task's CSV row index in the 30 macro intervals, copy receipts, oracle stdout/results, and actual capture/export/copy/oracle/total-wall costs remain bound. The native message envelope used for validation is explicitly derived and is never represented as a controller acknowledgment.

The frozen Task parser checks every row for one device and stream, unique identities, positive finite durations, strict nonoverlap, no unknown or MIX task, and exact full count. `timeline_spans` then partitions the 30 complete macro samples. Task Duration is the primary metric: each macro value is the sum of all R kernel Task Durations divided by R. Event and host wall stay descriptive. Six cycles yield 30 pairs per case and R, regardless of R. The existing control arithmetic checks CV≤5%, A/A role bias≤2%, and drift≤2%; this same-source study also checks formal role bias. The report includes the long/short mean shift and per-slot phase costs.

R7300 submits much more work than R100. A change in variability or mean can reflect different device behavior under that load; this matrix cannot isolate measurement precision as its sole cause. All artifacts and replay results are diagnostic only: `accepted=false`, `eligible_for_publication=false`.

The plan binds the prewarm rejection, existing long-case diagnostic, and the new 19-reference history supplement. Root must review the script/tests, then approve a concrete prepare/freeze result and write the root anchor before any hardware run.
