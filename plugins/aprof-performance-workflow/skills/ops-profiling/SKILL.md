---
name: ops-profiling
description: Collect and summarize msprof hardware artifacts using the AProf-bundled collector and parsers; acceptance remains the AProf runtime gate.
---

# AProf hardware collectors

After build and full correctness, select the mode matching the required metrics: `msprof op` for operator CSVs, or the bundled collector for full hardware groups. Resolve scripts from this installed skill directory:

```bash
bash scripts/msprof_profile_run.sh --help
bash scripts/msprof_profile_run.sh --warm-up=10 --output=<unique-dir> -- <timing-binary> <args>
python3 scripts/msprof_perf_summary.py <PROF_GROUP-dir> <archive-dir>
python3 scripts/perf_summary.py <OPPROF-dir> <archive-dir>
```

The inherited `--compare`/`--batch` modes are compatibility utilities, not the AProf correctness or paired-timing protocol. Full hardware metrics default to five independent repeats, ten warmups; production gain needs at least thirty alternating AB/BA timing-only pairs with the runtime's stability and confidence checks. Never include build, data generation or verification in the timed region.

Preserve raw CSV/trace, exact commands, samples, source hashes, target profile and dispatch key. Use `ascendc-aprof-profiling` to normalize evidence, preserve missing fields as unknown and submit it to the runtime. A summary is not a candidate verdict or attested policy reward.
