#!/usr/bin/env python3
"""Seal 0.5.1 with an explicit, historical-producer-only archive supplement.

The frozen publisher, hardware producers, package and old history stay unchanged.
The original publisher still independently replays every check. This entry only
supplies one previously archived source version missing from the history reader's
archive list; it does not substitute experiment data or reuse a passed summary.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path[:0] = [str(TOOLS), str(REPO / "scaffolding/collection/scripts")]
import verify_task_window_publication as publisher
from replay_timing_diagnosis import digest, read, require
from measurement_source_archive import HistoricalEvidence


def bound(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": digest(path)}


def checked(ref):
    require(isinstance(ref, dict) and set(ref) == {"path", "sha256"}, "invalid supplement reference")
    path = Path(ref["path"]).resolve(strict=True)
    require(str(path) == ref["path"] and digest(path) == ref["sha256"], "supplement reference changed")
    return path


def plan_value(path, expected_sha, root, report_path):
    path = checked({"path": str(Path(path).resolve()), "sha256": expected_sha})
    plan = read(path)
    require(set(plan) == {"schema_version", "purpose", "root", "publication_report_ref",
                         "history_ref", "source_archive_ref", "failed_publication_ref", "program_refs",
                         "reference_format_repair"}
            and plan["schema_version"] == 1
            and plan["purpose"] == "historical_producer_source_resolution_only"
            and plan["root"] == str(Path(root).resolve())
            and Path(root).resolve() == REPO / "skill-libs/graph-base/0.5.1"
            and checked(plan["publication_report_ref"]) == Path(report_path).resolve(),
            "wrong source supplement scope")
    expected_programs = {
        "entry": Path(__file__).resolve(), "publisher": TOOLS / "verify_task_window_publication.py",
        "sealer": TOOLS / "release_skill_lib.py",
        "history_reader": REPO / "scaffolding/collection/scripts/replay_task_window_method_history.py",
        "source_resolver": REPO / "scaffolding/collection/scripts/measurement_source_archive.py",
    }
    require(set(plan["program_refs"]) == set(expected_programs)
            and all(checked(plan["program_refs"][name]) == file for name, file in expected_programs.items()),
            "supplement program identity changed")
    report = read(report_path)
    require(report["history_ref"] == plan["history_ref"], "supplement belongs to another history")
    checked(plan["history_ref"])
    history = read(plan["history_ref"]["path"])
    checked(plan["source_archive_ref"])
    require(plan["source_archive_ref"] not in history["source_archive_refs"], "redundant source supplement")
    failed = read(checked(plan["failed_publication_ref"]))
    require(failed.get("kind") == "aprof_execution_report" and failed.get("status") == "failed"
            and failed.get("exit_code") != 0, "original failed publication receipt missing")
    for key in ("stdout", "stderr"):
        checked(failed[key])
    repair = plan["reference_format_repair"]
    require(set(repair) == {"purpose", "failed_publication_ref", "observation_terminals"}
            and repair["purpose"] == "normalize_sha256_prefix_only", "wrong reference repair scope")
    rejected = read(checked(repair["failed_publication_ref"]))
    require(rejected.get("kind") == "aprof_execution_report" and rejected.get("status") == "failed"
            and rejected.get("exit_code") != 0, "reference-format rejection receipt missing")
    for key in ("stdout", "stderr"):
        checked(rejected[key])
    directory = Path(report["qualification_dir"]).resolve(strict=True)
    wanted = {f"{op}-observation-{case:02d}" for op in publisher.OPERATORS for case in publisher.TIMELINES[op]}
    require(set(repair["observation_terminals"]) == wanted, "observation terminal repair scope differs")
    for slot, ref in repair["observation_terminals"].items():
        require(checked(ref) == directory / "observations" / slot / "terminal.json",
                "observation repair path differs")
        terminal = read(directory / "campaign" / slot / "terminal.json")
        require(terminal["online_completion"] == ref, "observation repair differs from actual online terminal")
    # Fail fast on the small original code dependencies; the full publisher still
    # replays the studies and all original data below without a summary shortcut.
    evidence = HistoricalEvidence([*history["source_archive_refs"], plan["source_archive_ref"]])
    for study in history["offline_export_studies"]:
        study_plan = read(checked(study["plan_ref"]))
        for ref in study_plan["dependencies"]:
            evidence.bind(ref["path"], ref["sha256"])
    return plan, history


def audit(root, report_path, supplement_path, supplement_sha):
    plan, history = plan_value(supplement_path, supplement_sha, root, report_path)
    import replay_task_window_method_history as history_reader
    original = history_reader.HistoricalEvidence
    original_bound = publisher.bound
    calls = []
    format_calls = []
    repaired_refs = {ref["path"]: ref for ref in plan["reference_format_repair"]["observation_terminals"].values()}

    def with_supplement(references, **kwargs):
        require(references == history["source_archive_refs"], "unexpected historical archive scope")
        require(not calls, "historical supplement used more than once")
        calls.append(True)
        return original([*references, plan["source_archive_ref"]], **kwargs)

    def prefixed_terminal(path):
        # Rehash using the original helper. Only its representation changes for
        # the four exact online-terminal references; no expected bytes are substituted.
        value = original_bound(path)
        if value["path"] in repaired_refs:
            require(value["path"] not in format_calls, "observation terminal compared more than once")
            value = dict(value, sha256="sha256:" + publisher.common.hex_digest(value["sha256"]))
            require(value == repaired_refs[value["path"]], "observation terminal content changed")
            format_calls.append(value["path"])
        return value

    history_reader.HistoricalEvidence = with_supplement
    publisher.bound = prefixed_terminal
    try:
        result = publisher.verify_in_process(Path(root), Path(report_path))
    finally:
        history_reader.HistoricalEvidence = original
        publisher.bound = original_bound
    require(calls == [True] and result.get("accepted") is True,
            "full independent publication replay did not accept")
    require(set(format_calls) == set(repaired_refs), "full observation reference checks did not run")
    plan_value(supplement_path, supplement_sha, root, report_path)
    result["historical_source_replay_supplement"] = {
        "authority": "historical_producer_source_resolution_only",
        "plan_ref": bound(supplement_path), "program_refs": plan["program_refs"],
        "history_ref": plan["history_ref"], "source_archive_ref": plan["source_archive_ref"],
        "failed_publication_ref": plan["failed_publication_ref"],
        "reference_format_repair": plan["reference_format_repair"],
        "original_publisher_full_replay": True,
    }
    return result


def independent(root, report_path, supplement_path, supplement_sha):
    plan_value(supplement_path, supplement_sha, root, report_path)
    result = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "audit",
                             "--root", str(root), "--report", str(report_path),
                             "--supplement", str(supplement_path), "--supplement-sha256", supplement_sha],
                            capture_output=True, text=True, timeout=1800)
    require(result.returncode == 0, result.stderr[-6000:] or "independent supplemented publication failed")
    value = json.loads(result.stdout)
    require(value.get("accepted") is True
            and value["historical_source_replay_supplement"]["plan_ref"] == bound(supplement_path),
            "independent supplemented publication did not accept")
    plan_value(supplement_path, supplement_sha, root, report_path)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("audit", "seal"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--supplement", required=True, type=Path)
    parser.add_argument("--supplement-sha256", required=True)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    if args.command == "audit":
        value = audit(args.root, args.report, args.supplement, args.supplement_sha256)
    else:
        if not args.source_commit:
            parser.error("seal requires --source-commit")
        import release_skill_lib
        original = publisher.verify_task_window_publication
        publisher.verify_task_window_publication = lambda root, report: independent(
            root, report, args.supplement, args.supplement_sha256)
        try:
            value = release_skill_lib.seal(args.root, args.source_commit, "0.5.0",
                                           measurement_validation=args.report)
        finally:
            publisher.verify_task_window_publication = original
        value = {"valid": True, "release_id": value["release_id"], "files": len(value["files"])}
    print(json.dumps(value, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
