#!/usr/bin/env python3
"""Optional post-task import, owned by trace collection; never run by optimization."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

RELEASE = Path(__file__).resolve().parents[3] / "skill-libs/graph-base/0.5.1"
sys.path.insert(0, str(RELEASE / "runtime/src"))
from aprof_runtime.jsonio import file_hash
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.store import EpisodeStore


def archive(index, completion, store_path, receipt):
    started_at, started = time.time(), time.monotonic()
    original_index_ref = file_hash(index)
    local = LocalEvidence.from_index(index)
    completion_ref = file_hash(completion)
    terminal = json.loads(local.verify_artifact(completion_ref).read_text())
    if (terminal.get("kind") != "local_measurement_completion"
            or terminal.get("status") not in {"passed", "failed"}
            or type(terminal.get("finished_at")) not in {int, float}
            or not 0 < terminal["finished_at"] <= started_at):
        raise ValueError("archive requires an existing task completion; it cannot finish a task")
    store_path, receipt = Path(store_path).absolute(), Path(receipt).absolute()
    if (store_path.exists() or receipt.exists()
            or store_path.is_relative_to(local.directory.parent)
            or receipt.is_relative_to(local.directory.parent)):
        raise ValueError("archive destinations must be fresh and separate from the task workspace")
    saved = json.loads(Path(index).read_text())
    if file_hash(index) != original_index_ref:
        raise ValueError("local index changed before post-task import")
    refs = sorted(saved["artifacts"])
    # This is the only copy boundary. Original files and the task verdict stay unchanged.
    with EpisodeStore(store_path) as store:
        for ref in refs:
            if store.register_artifact(local.verify_artifact(ref)) != ref:
                raise ValueError("local evidence changed during post-task import")
        for ref in refs:
            store.verify_artifact(ref)
        index_ref = store.register_artifact(index)
        if index_ref != original_index_ref:
            raise ValueError("local index changed during post-task import")
    result = {"schema_version": 1, "owner": "trace_collection",
        "cost_scope": "post_task_archive", "admission_authority": False,
        "local_index": {"path": str(Path(index).resolve()), "sha256": index_ref},
        "completion_ref": completion_ref, "store": str(store_path),
        "artifact_refs": refs, "started_at": started_at, "finished_at": time.time(),
        "elapsed_seconds": time.monotonic() - started}
    with receipt.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("index", "completion", "store", "receipt"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(archive(args.index, args.completion, args.store, args.receipt), indent=2))


if __name__ == "__main__":
    main()
