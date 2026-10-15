# AProf remote deployment quickstart

The optional `ascendc-remote-kernel-deploy` adapter uses the local AProf profiling collectors and the configured SSH connection. Install with `python3 tools/install.py --runtime --with-remote (from the release root)`; no external skill checkout is required.

Configure the existing server configuration or APROF_REMOTE environment variables, provide a complete operator directory and follow `SKILL.md`. `sim` collects simulator proxy evidence; `hw-msprof` and `hw-op` collect hardware data after successful build and correctness. The local `skills/aprof/support/ops-profiling/scripts` directory contains the scripts uploaded with the operator.

Preserve raw artifacts and inspect `deploy_results.json` plus `artifact_manifest.json` before diagnosis. The adapter does not choose parallel plans, inject benchmark problems or sign candidate verdicts. Keep connection secrets out of checked-in files and traces.
