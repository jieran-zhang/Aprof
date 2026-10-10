#!/usr/bin/env python3
"""Bind a new producer and skill epoch to an unchanged historical Level2 prefix."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from aprof_layout import identity
from level2_campaign import freeze_engineering
from msprof_exploration_campaign import Campaign, _active
from msprof_exploration_execute import load, pointer, save, sha

VERSION = "level2_legacy_epoch_handoff_v1"
EPOCH = "graph-base-050-search-lite-01"


def prefix(run):
    result = {}
    for split in ("train", "validation"):
        ledger = Campaign(run / split / "ledger")
        state = ledger.status(split=split)
        if ledger.unsealed_checkpoints or _active(ledger.state):
            raise ValueError(f"{split} has open work or unsealed checkpoints")
        result[split] = {
            "head_hash": state["head_hash"],
            "event_count": state["event_count"],
            "config_hash": state["config_hash"],
            "source_attempts": sum(t["new_source_attempts"] for t in state["tasks"].values()),
        }
    return result


def prepare(run, output):
    run, output = Path(run).resolve(), Path(output).resolve()
    if output.exists() or output.parent != run / "preflight" or (run / "skill-lib.json").exists():
        raise ValueError("fresh historical continuation under preflight required")
    pause = run / "preflight/pause-20261008T0300/checkpoint.json"
    old = run / "bootstrap/frozen-engineering-026.json"
    paused = load(pause)
    heads = prefix(run)
    if (paused.get("status") != "paused_by_user" or paused.get("source_attempts_feedback_closed") != 26
            or not 26 <= sum(v["source_attempts"] for v in heads.values()) <= 48
            or any(len(Campaign(run / s / "ledger").events) <= paused["counts"][s]["last_event_sequence"]
                   or Campaign(run / s / "ledger").events[paused["counts"][s]["last_event_sequence"]]["hash"]
                       != paused["counts"][s]["last_event"] for s in heads)):
        raise ValueError("historical ledger no longer matches paused 26-attempt prefix")
    if load(old).get("version") != "level2_frozen_engineering_v1":
        raise ValueError("historical engineering identity differs")
    selected = identity()
    if selected["release_id"] != "graph-base/0.5.0":
        raise ValueError("continuation requires graph-base 0.5.0")
    engineering = freeze_engineering(run, historical_continuation=True)
    record = {
        "version": VERSION, "status": "resumed", "recorded_at": datetime.now(timezone.utc).isoformat(),
        "run": str(run), "epoch": EPOCH, "historical_pause": pointer(pause),
        "historical_engineering": pointer(old), "new_engineering": engineering,
        "skill_library": selected, "runtime_version": selected["runtime_version"],
        "graph": pointer(run / "graph/v0002/graph.json") if (run / "graph/v0002/graph.json").is_file() else None,
        "ledger_prefix": heads, "inherited_source_attempts": 26,
        "source_attempts_at_handoff": sum(v["source_attempts"] for v in heads.values()),
        "remaining_source_attempts": 48 - sum(v["source_attempts"] for v in heads.values()),
        "search_protocol": "msprof_task_time_search_lite_v1",
        "final_protocol": "msprof_task_time_exploration_v2",
        "metric": "operator_task_sum_us", "capture_storage": "local_tmp_full_copyback_v1",
        "historical_records_immutable": True,
    }
    output.mkdir()
    save(output / "request.json", record)
    return pointer(output / "request.json")


def check(path):
    path = Path(path).resolve()
    record = load(path)
    run = Path(record["run"])
    if (path.parent.parent != run / "preflight" or record["version"] != VERSION
            or record["epoch"] != EPOCH or record["status"] != "resumed"
            or record["skill_library"] != identity()):
        raise ValueError("continuation epoch or release differs")
    for field in ("historical_pause", "historical_engineering", "new_engineering"):
        ref = record[field]
        if pointer(ref["path"]) != ref:
            raise ValueError(field + " changed")
    frozen = load(record["new_engineering"]["path"])
    if frozen.get("skill_library") != record["skill_library"]:
        raise ValueError("new engineering release differs")
    for row in frozen["files"]:
        if sha(row["path"]) != row["sha256"] or sha(row["snapshot"]) != row["sha256"]:
            raise ValueError("new engineering producer or snapshot differs")
    for split, head in record["ledger_prefix"].items():
        ledger = Campaign(run / split / "ledger")
        if (ledger.config_hash != head["config_hash"] or len(ledger.events) < head["event_count"]
                or ledger.events[head["event_count"] - 1]["hash"] != head["head_hash"]
                or sum(t["new_source_attempts"] for t in ledger.state["tasks"].values()) < head["source_attempts"]):
            raise ValueError("historical ledger prefix or source budget differs")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "check"))
    parser.add_argument("--run", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--request", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        if args.run is None or args.output is None:
            parser.error("prepare requires --run and --output")
        print(prepare(args.run, args.output))
    else:
        if args.request is None:
            parser.error("check requires --request")
        print(check(args.request)["status"])


if __name__ == "__main__":
    main()
