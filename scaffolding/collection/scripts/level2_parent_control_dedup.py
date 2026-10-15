#!/usr/bin/env python3
"""Losslessly deduplicate closed ResizeBilinear parent A/A outputs.

All logical files stay at their original paths. This is storage maintenance,
not a calibration, measurement, source attempt, or native-output archive.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import stat

VERSION = "level2_parent_control_output_dedup_v1"
CHUNK = 8 * 1024 * 1024
NAME = re.compile(r"resize_bilinear00[12]-aa-final-local-01\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe(path, *, directory=False):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts, "noncanonical path")
    require(not any(item.is_symlink() for item in (path, *path.parents)), "symlink evidence")
    info = path.stat()
    require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode), "unexpected file kind")
    return path


def digest(path):
    path = safe(path)
    before = path.stat()
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(CHUNK):
            value.update(block)
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
             before.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_size,
                                    after.st_mtime_ns, after.st_ctime_ns), "file changed during hash")
    return "sha256:" + value.hexdigest(), after


def ref(path):
    return {"path": str(path), "sha256": digest(path)[0]}


def read(path):
    return json.loads(safe(path).read_bytes())


def syncdir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save_new(path, value):
    payload = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    syncdir(path.parent)


def inventory(control):
    control = safe(control, directory=True)
    require(NAME.fullmatch(control.name) and control.parent.name == "parent-controls"
            and control.parent.parent.name == "resize_bilinear"
            and control.parent.parent.parent.name == "tasks", "unsupported control scope")
    cohort = safe(control / "cohort", directory=True)
    completion = read(control / "completion.json")
    require(completion.get("version") == "level2_candidate_parent_aa_control_v1"
            and completion.get("status") == "passed" and completion.get("error") is None
            and completion.get("source_attempt_added") is False, "parent control not closed passed")
    for key, path in (("report", cohort / "report.json"),
                      ("group_completion", cohort / "group-completion.json"),
                      ("request", control / "request.json")):
        require(completion.get(key) == ref(path), "control completion pointer differs")
    plan = read(cohort / "plan.json")
    group = read(cohort / "group-completion.json")
    report = read(cohort / "report.json")
    require(plan.get("comparison_kind") == report.get("comparison_kind") == "aa"
            and plan.get("protocol") == group.get("protocol") == report.get("protocol")
            == "msprof_task_time_exploration_v2"
            and plan.get("case_ids") == list(range(1, 21))
            and report.get("evidence_status") == "verified_complete"
            and report.get("metric") == "operator_task_sum_us"
            and report.get("operator") == "resize_bilinear"
            and group.get("status") == "passed", "full parent A/A report differs")
    schedule = plan.get("schedule", [])
    sessions = group.get("completed_sessions", [])
    require(len(schedule) == len(sessions) == len(report.get("sessions", [])) == 6
            and sessions == [str(cohort / row["name"]) for row in schedule]
            == [row["directory"] for row in report["sessions"]], "six-process roster differs")
    rows = []
    inodes = []
    refs = {"completion": ref(control / "completion.json"), "plan": ref(cohort / "plan.json"),
            "group": ref(cohort / "group-completion.json"), "report": ref(cohort / "report.json")}
    for session_name, reported in zip(sessions, report["sessions"]):
        session = safe(session_name, directory=True)
        validation_path = session / "validation.json"
        validation_ref = ref(validation_path)
        require(reported.get("artifacts", {}).get(str(validation_path)) == validation_ref["sha256"],
                "validation lacks independent report binding")
        validation = read(validation_path)
        observed = validation.get("outputs", [])
        expected = {(str(case), config, role) for case in range(1, 21)
                    for config in ("normal", "swapped") for role in ("A", "B")}
        require(len(observed) == 80
                and {(str(row.get("case_id")), row.get("buffer_config"), row.get("role"))
                     for row in observed} == expected
                and all(row.get("passed") is True for row in observed), "validation output roster differs")
        refs[session.name] = validation_ref
        native = safe(session / "native", directory=True)
        require({item.name for item in native.iterdir() if item.suffix == ".bin"}
                == {f"{case}_{config}_{role}.bin" for case, config, role in expected},
                "unexpected or absent native output")
        for row in observed:
            path = native / f"{row['case_id']}_{row['buffer_config']}_{row['role']}.bin"
            actual, info = digest(path)
            require(actual == row.get("output_hash"), "validated output hash differs")
            rows.append({"path": str(path), "sha256": actual, "bytes": info.st_size})
            inodes.append(((info.st_dev, info.st_ino), info.st_nlink))
    require(len(rows) == 480 and len({row["path"] for row in rows}) == 480,
            "incomplete control output roster")
    known_links = Counter(inode for inode, _ in inodes)
    require(all(links == known_links[inode] for inode, links in inodes),
            "output has a hardlink outside the closed control roster")
    return refs, sorted(rows, key=lambda row: row["path"])


def replace_duplicates(rows):
    """Atomic path replacement; reentry accepts only the exact seed hardlink."""
    seeds = {}
    linked = 0
    for row in rows:
        path = Path(row["path"])
        seed = seeds.setdefault(row["sha256"], path)
        if seed == path:
            continue
        seed_info, output_info = safe(seed).stat(), safe(path).stat()
        require(seed_info.st_size == output_info.st_size == row["bytes"], "duplicate size differs")
        require((stat.S_IMODE(seed_info.st_mode), seed_info.st_uid, seed_info.st_gid)
                == (stat.S_IMODE(output_info.st_mode), output_info.st_uid, output_info.st_gid),
                "duplicate file metadata differs")
        temporary = path.with_name(path.name + ".aprof-parent-dedup.tmp")
        if os.path.samefile(seed, path):
            require(not temporary.exists(), "orphan temporary link after replacement")
            linked += 1
            continue
        require(digest(seed)[0] == digest(path)[0] == row["sha256"], "duplicate content changed")
        if temporary.exists():
            require(safe(temporary).stat().st_ino == seed_info.st_ino
                    and temporary.stat().st_dev == seed_info.st_dev,
                    "foreign temporary link")
        else:
            os.link(seed, temporary, follow_symlinks=False)
            syncdir(path.parent)
        os.replace(temporary, path)
        syncdir(path.parent)
        require(os.path.samefile(seed, path), "hardlink replacement failed")
        linked += 1
    return linked


def run(control, *, writers_closed=False, apply=False):
    require(writers_closed is True, "closed writer attestation required")
    from level2_storage import exclusive_host, storage_lock
    control = Path(control)
    with exclusive_host(), storage_lock(control.parents[4] / "storage"):
        refs, rows = inventory(control)
        groups = {row["sha256"]: row["bytes"] for row in rows}
        total = sum(row["bytes"] for row in rows)
        saved = total - sum(groups.values())
        if not apply:
            return {"status": "verified_dry_run", "logical_outputs": len(rows),
                    "unique_contents": len(groups), "potential_duplicate_bytes": saved}
        destination = control / "output-dedup-v1"
        if not destination.exists():
            destination.mkdir()
            syncdir(control)
        safe(destination, directory=True)
        plan_path = destination / "plan.json"
        plan = {"version": VERSION, "control": str(control), "closed_evidence": refs,
                "outputs": rows, "logical_bytes": total, "potential_duplicate_bytes": saved,
                "writers_closed_attested": True}
        if plan_path.exists():
            require(read(plan_path) == plan, "dedup plan or authority changed")
        else:
            save_new(plan_path, plan)
        linked = replace_duplicates(rows)
        for row in rows:
            require(digest(row["path"])[0] == row["sha256"], "post-dedup output differs")
        receipt = {"version": VERSION, "status": "complete", "plan": ref(plan_path),
                   "logical_outputs": len(rows), "unique_contents": len(groups),
                   "linked_duplicate_paths": linked, "potential_duplicate_bytes": saved,
                   "logical_paths_preserved": True, "source_bytes_preserved": True,
                   "actual_quota_relief": "measure with df; hardlink accounting is not quota proof"}
        receipt_path = destination / "completion.json"
        if receipt_path.exists():
            require(read(receipt_path) == receipt, "dedup receipt changed")
        else:
            save_new(receipt_path, receipt)
        return {"status": "complete", "receipt": ref(receipt_path),
                "linked_duplicate_paths": linked, "potential_duplicate_bytes": saved}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--writers-closed", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.control, writers_closed=args.writers_closed, apply=args.apply), indent=2))


if __name__ == "__main__":
    main()
