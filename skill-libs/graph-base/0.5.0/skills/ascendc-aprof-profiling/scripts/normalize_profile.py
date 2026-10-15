#!/usr/bin/env python3
"""Normalize one capture manifest by replaying raw CAS evidence in the runtime.

Metrics JSON can contain exact runtime specs (unit, aggregation, sources) or a
convenient selector repeated independently for every capture:
{"aiv_time": {"unit":"us", "file":"summary.jsonl", "format":"jsonl",
 "field":"aiv_time(us)", "where":{"category":"PipeUtilization"},
 "row_aggregation":"mean", "aggregation":"median"}}.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

RELEASE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RELEASE / "runtime" / "src"))
from aprof_runtime.profile_evidence import load_capture_manifest, normalize_profile
from aprof_runtime.store import EpisodeStore
from aprof_runtime.errors import ContractError


def expand_specs(manifest, specs):
    result = {}
    for name, spec in specs.items():
        if "sources" in spec:
            result[name] = spec
            continue
        allowed = {"unit", "file", "format", "field", "where", "row_aggregation", "aggregation"}
        if set(spec) - allowed or not {"unit", "file", "format", "field"}.issubset(spec):
            raise ValueError("metric selector requires unit,file,format,field; optional where,row_aggregation,aggregation")
        sources = []
        for capture in manifest["captures"]:
            exact = str(Path(capture["collection"]) / spec["file"])
            matches = [item for item in capture["files"] if item["path"] == exact and item["format"] == spec["format"]]
            if len(matches) != 1:
                raise ValueError(f"metric {name!r}: capture {capture['capture_id']} does not contain exact selected file {exact!r}")
            sources.append(dict(capture_id=capture["capture_id"], path=exact, format=spec["format"], field=spec["field"], where=spec.get("where", {}), row_aggregation=spec.get("row_aggregation", "mean")))
        result[name] = dict(unit=spec["unit"], aggregation=spec.get("aggregation", "median"), sources=sources)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", required=True, help="capture-manifest.json file or already registered sha256:<hash>")
    parser.add_argument("--metrics", required=True, help="JSON mapping metric names to selectors")
    parser.add_argument("--store", required=True, help="same EpisodeStore as capture, including adjacent .objects CAS")
    parser.add_argument("--output", required=True, help="new normalized-profile JSON file")
    args = parser.parse_args()
    try:
        target = Path(args.output)
        if target.exists():
            raise ValueError("normalized output already exists")
        specs = json.loads(Path(args.metrics).read_text())
        with EpisodeStore(args.store) as store:
            digest = args.manifest if args.manifest.startswith("sha256:") else store.register_artifact(args.manifest)
            manifest = load_capture_manifest(store, digest)
            profile = normalize_profile(store, digest, expand_specs(manifest, specs))
            with target.open("x") as stream:
                json.dump(profile, stream, indent=2, sort_keys=True, allow_nan=False)
                stream.write("\n")
            profile_hash = store.register_artifact(target)
        print(json.dumps({"profile": str(target.resolve()), "profile_hash": profile_hash,
                          "statuses": {name: metric["status"] for name, metric in profile["metrics"].items()},
                          "performance_gate": False}, indent=2))
    except (ContractError, ValueError, KeyError, OSError) as exc:
        parser.exit(2, f"normalize_profile: {exc}\n")


if __name__ == "__main__":
    main()
