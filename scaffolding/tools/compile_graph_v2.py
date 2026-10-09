#!/usr/bin/env python3
"""Reproducible v0002 overlay; never rebuild or rewrite the v0001 snapshot."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "collection/scripts"))

from aprof_layout import skill_lib

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = skill_lib()
sys.path.insert(0, str(skill_lib() / "runtime/src"))
from aprof_runtime.graph import load_snapshot, validate_graph


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def build_snapshot(root=ROOT):
    parent, _ = load_snapshot(root / "skillgraph/versions/v0001")
    source = root / "skillgraph/source/v0002/planning.json"
    overlay = json.loads(source.read_text())
    graph = deepcopy(parent)
    graph.update(graph_version="v0002", planning_contract="architecture_parallel_dispatch_v1")
    graph["created_from"] = {"kind": "expert_planning_overlay", "parent_graph_version": "v0001",
                             "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    for transform in graph["transformations"]:
        identifier = transform["id"]
        if identifier == "transformation.noop":
            transform["optimization_stage"] = "any"
            continue
        transform["optimization_stage"] = "algorithm_parallel" if identifier in overlay["algorithm_transformations"] else "execution"
        transform["required_capabilities"] = overlay["required_capabilities"].get(identifier, [])
    graph["predicates"].extend(overlay["predicates"])
    graph["mechanisms"].extend(overlay["mechanisms"])
    graph["transformations"].extend(overlay["transformations"])
    graph["edges"].extend(overlay["edges"])
    validate_graph(graph)
    lineage = {"schema_version": "1.0.0", "graph_version": "v0002", "parent_graph_versions": ["v0001"],
               "origin": "expert_planning_overlay", "source_files": ["skillgraph/source/v0002/planning.json"],
               "source_sha256": graph["created_from"]["source_sha256"]}
    payloads = {"graph.json": encoded(graph), "lineage.json": encoded(lineage)}
    manifest = {"schema_version": "1.0.0", "graph_version": "v0002", "immutable": True,
                "graph_sha256": hashlib.sha256(payloads["graph.json"]).hexdigest(),
                "counts": {k: len(graph[k]) for k in ("anchors", "predicates", "mechanisms", "transformations", "edges")},
                "files": {"graph": "graph.json", "lineage": "lineage.json", "checksums": "checksums.json"}}
    payloads["manifest.json"] = encoded(manifest)
    payloads["checksums.json"] = encoded({"schema_version": "1.0.0", "algorithm": "sha256",
                                          "files": {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()}})
    return payloads


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=skill_lib() / "skillgraph/versions/v0002")
    parser.add_argument("--skill-lib", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payloads = build_snapshot()
    if args.output.exists():
        if any(not (args.output / name).is_file() or (args.output / name).read_bytes() != data for name, data in payloads.items()):
            raise SystemExit("existing immutable v0002 snapshot differs; publish a new version")
    elif args.check:
        raise SystemExit("v0002 snapshot is missing")
    else:
        args.output.mkdir(parents=True)
        for name, data in payloads.items():
            (args.output / name).write_bytes(data)
    print(json.dumps({"valid": True, "graph_version": "v0002", "output": str(args.output)}))


if __name__ == "__main__":
    main()
