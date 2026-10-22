#!/usr/bin/env python3
"""Deduplicate passed Cummin A/A sessions without changing logical evidence.

The six-process control can be incomplete. This maintenance accepts only passed,
fully verified sessions from its frozen schedule. It never turns an incomplete
control into a calibration or removes a logical output path. A live coordinator
must be stopped between native processes by the serial operator before use.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from level2_storage import digest, exclusive_host, safe, sync_directory, write_new

VERSION = "level2_partial_control_output_dedup_v1"
SESSION = re.compile(r"aa-[A-Za-z0-9_-]+-p0[1-6]\Z")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(safe(path).read_bytes())


def pointer(path):
    return {"path": str(path), "sha256": digest(path)[0]}


def paused(pid, stage):
    require(type(pid) is int and pid > 1, "paused coordinator PID required")
    proc = Path("/proc") / str(pid)
    status = (proc / "status").read_text()
    require(re.search(r"^State:\s+T\b", status, re.M), "coordinator is not stopped")
    raw_argv = (proc / "cmdline").read_bytes()
    argv = raw_argv.replace(b"\0", b" ").decode(errors="replace")
    require("level2_iteration.py" in argv and "baseline" in argv
            and str(stage.parents[4]) in argv, "stopped process is not the Level2 baseline coordinator")
    return {"pid": pid, "cmdline_sha256": "sha256:" + hashlib.sha256(raw_argv).hexdigest()}


def inventory(stage, last_session, *, writers_closed=False, paused_pid=None):
    stage = Path(stage)
    require(stage.is_absolute() and ".." not in stage.parts and stage == stage.resolve(), "noncanonical stage")
    require(stage.parent.name == "stages" and stage.parent.parent.name == "cummin"
            and stage.name.startswith("aa-") and stage.parent.parent.parent.name == "tasks",
            "only Cummin baseline A/A control is supported")
    plan_path = safe(stage / "stage-plan.json")
    plan = read(plan_path)
    require(plan.get("control_type") == "aa" and plan.get("group") == stage.name
            and plan.get("case_ids") == list(range(1, 21))
            and plan.get("protocol") == "msprof_task_time_exploration_v2", "full A/A plan required")
    schedule = plan.get("cohort", {}).get("schedule", [])
    names = [row.get("name") for row in schedule]
    require(len(names) == 6 and len(set(names)) == 6
            and all(isinstance(name, str) and SESSION.fullmatch(name) for name in names)
            and last_session in names, "six-process schedule or selected session differs")
    selected = names[:names.index(last_session) + 1]
    stage_result = stage / "result.json"
    if stage_result.exists():
        result = read(stage_result)
        require(writers_closed is True and paused_pid is None and result.get("status") in ("passed", "failed")
                and result.get("kind") == "control" and result.get("ended_at") is not None,
                "closed control stage and writer affirmation required")
        authority = {"stage_result": pointer(stage_result)}
    else:
        require(writers_closed is False and paused_pid is not None, "open stage needs stopped coordinator")
        authority = {"paused_coordinator": paused(paused_pid, stage)}
    rows, session_refs, bundle_refs = [], [], []
    for name in selected:
        session = stage / "cohort" / name
        require(safe(session, directory=True), "missing session")
        completion_path, validation_path = session / "completion.json", session / "validation.json"
        completion, validation = read(completion_path), read(validation_path)
        require(completion.get("status") == "passed" and completion.get("error") is None,
                "session is not terminal passed")
        observed = validation.get("outputs", [])
        expected = {(str(case), config, role) for case in range(1, 21)
                    for config in ("normal", "swapped") for role in ("A", "B")}
        require(len(observed) == 80 and
                {(str(x.get("case_id")), x.get("buffer_config"), x.get("role")) for x in observed} == expected
                and all(x.get("passed") is True for x in observed), "complete 20-case output validation required")
        session_refs.append({"name": name, "completion": pointer(completion_path),
                             "validation": pointer(validation_path)})
        native = session / "native"
        for record in observed:
            stem = f"{record['case_id']}_{record['buffer_config']}_{record['role']}.bin"
            packed = safe(native / stem, stage)
            require(re.fullmatch(r"sha256:[0-9a-f]{64}", record.get("output_hash", "")), "packed hash missing")
            rows.append({"path": str(packed), "sha256": record["output_hash"],
                         "size_bytes": packed.stat().st_size})
            bundle_path = safe(native / (stem + ".outputs.json"), stage)
            bundle = read(bundle_path)
            bundle_refs.append(pointer(bundle_path))
            require(bundle.get("version") == "level2_output_bundle_v1" and bundle.get("operator") == "cummin"
                    and {x.get("name") for x in bundle.get("outputs", [])} == {"values", "indices"}
                    and len(bundle["outputs"]) == 2, "Cummin multi-output bundle differs")
            for part in bundle["outputs"]:
                path = safe(native / (stem + "." + part["name"]), stage)
                require(part.get("path") == str(path) and part.get("bytes") == path.stat().st_size
                        and re.fullmatch(r"sha256:[0-9a-f]{64}", part.get("sha256", "")),
                        "named output path, size or hash differs")
                rows.append({"path": str(path), "sha256": part["sha256"],
                             "size_bytes": part["bytes"]})
    require(len(rows) == 240 * len(selected) and len({x["path"] for x in rows}) == len(rows),
            "incomplete or duplicate logical output roster")
    return {"version": VERSION, "stage": str(stage), "selected_sessions": selected,
            "plan": pointer(plan_path), "authority": authority, "sessions": session_refs,
            "bundles": bundle_refs,
            "outputs": sorted(rows, key=lambda x: x["path"])}


def deduplicate(stage, last_session, *, writers_closed=False, paused_pid=None, apply=False):
    lock = exclusive_host() if writers_closed else nullcontext()
    with lock:
        value = inventory(stage, last_session, writers_closed=writers_closed, paused_pid=paused_pid)
        stage = Path(stage)
        groups = {}
        for row in value["outputs"]:
            path = safe(row["path"], stage)
            require(path.stat().st_size == row["size_bytes"] and digest(path, row["sha256"])[0] == row["sha256"],
                    "recorded output changed before maintenance")
            groups.setdefault((row["sha256"], row["size_bytes"]), []).append(path)
        if not apply:
            return {"status": "verified_dry_run", "logical_files": len(value["outputs"]),
                    "unique_payloads": len(groups), "duplicate_files": len(value["outputs"]) - len(groups)}
        destination = stage / "partial-output-dedup" / last_session
        require(not destination.is_symlink(), "maintenance destination is symlink")
        destination.mkdir(parents=True, exist_ok=True)
        sync_directory(stage)
        sync_directory(destination.parent)
        manifest = destination / "manifest.json"
        if manifest.exists():
            prior = read(manifest)
            # A resumed closed transaction may have replaced a live PID proof.
            require(prior == value, "immutable maintenance manifest differs")
        else:
            write_new(manifest, value)
        saved = 0
        for paths in groups.values():
            source = paths[0]
            for target in paths[1:]:
                original = safe(target, stage).stat()
                if original.st_ino == source.stat().st_ino:
                    continue
                require(original.st_dev == source.stat().st_dev, "different filesystem")
                temporary = target.with_name(target.name + ".aprof-link-" + uuid.uuid4().hex)
                try:
                    os.link(source, temporary, follow_symlinks=False)
                    os.replace(temporary, target)
                    sync_directory(target.parent)
                finally:
                    temporary.unlink(missing_ok=True)
                require(target.stat().st_ino == source.stat().st_ino, "hardlink replacement differs")
                saved += original.st_blocks * 512
        for (sha, size), paths in groups.items():
            require(digest(paths[0], sha)[0] == sha and paths[0].stat().st_size == size,
                    "canonical output changed after linking")
            require(all(path.stat().st_ino == paths[0].stat().st_ino for path in paths),
                    "logical aliases do not replay from the same verified bytes")
        receipt_path = destination / "completion.json"
        receipt = {"version": VERSION, "status": "complete", "manifest": pointer(manifest),
                   "logical_files": len(value["outputs"]), "unique_payloads": len(groups),
                   "source_bytes_preserved": True, "logical_paths_preserved": True,
                   "space_reclaimed_estimate_bytes": saved}
        if receipt_path.exists():
            prior = read(receipt_path)
            require({k: v for k, v in prior.items() if k != "space_reclaimed_estimate_bytes"} ==
                    {k: v for k, v in receipt.items() if k != "space_reclaimed_estimate_bytes"},
                    "immutable maintenance receipt differs")
            receipt = prior
        else:
            write_new(receipt_path, receipt)
        return {"receipt": pointer(receipt_path), **receipt}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, type=Path)
    parser.add_argument("--last-session", required=True)
    parser.add_argument("--writers-closed", action="store_true")
    parser.add_argument("--paused-coordinator-pid", type=int)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(deduplicate(args.stage, args.last_session, writers_closed=args.writers_closed,
                                 paused_pid=args.paused_coordinator_pid, apply=args.apply)))


if __name__ == "__main__":
    main()
