"""Synthetic raw captures for current-runtime regression fixtures, never hardware claims."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import json

from aprof_runtime import __version__
from aprof_runtime.contracts import Context, GateRequest
from aprof_runtime.episodes import finalize_episodes
from aprof_runtime.jsonio import to_primitive
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import register_json_artifact


def bind_profiles(value, store, *, preserve_sources=False):
    """Give every positive fixture real CAS raw sources instead of a bare boolean."""
    if __version__ == "0.2.0":
        return value, {}
    from test_profile_evidence_v11 import blob, fixture, seal_capture
    from aprof_runtime.profile_evidence import normalize_profile
    value = deepcopy(value)
    replacements = {}
    by_id = {item["candidate_id"]: item for item in value["candidates"]}
    for evidence in value["evidence"]:
        if evidence.get("mechanism_alignment") is not True:
            continue
        draft = by_id[evidence["candidate_id"]]
        if draft.get("transformation_id") == "transformation.noop":
            continue
        profiles = []
        for role, duration in (("baseline", 100), ("candidate", 80)):
            source = draft["source_hashes"][role]
            if preserve_sources:
                store.verify_artifact(source)
            else:
                replacements.setdefault(source, blob(store, "synthetic source " + source))
                source = replacements[source]
                draft["source_hashes"][role] = source
            manifest, _, spec = fixture(store, role, [duration] * 5)
            manifest["source_hash"] = source
            for i, warmup in enumerate(manifest["warmup_runs"]):
                identity = {"binary_hash": manifest["binary_hash"], "tool_hash": manifest["tool"]["executable_hash"], "source_hash": source}
                warmup["log_hash"] = register_json_artifact(store, {"argv": warmup["argv"], "exit_code": 0, "warmup": i,
                    "identity_checks": {"before": identity, "after": identity}})
            for capture in manifest["captures"]:
                seal_capture(store, manifest, capture)
            profiles.append(register_json_artifact(store, normalize_profile(store, register_json_artifact(store, manifest), spec)))
        report = {"schema_version": "1.0.0", "candidate_id": evidence["candidate_id"], "hypothesis_basis": "measured",
                  "metrics": [{"name": "duration", "baseline": 100, "candidate": 80, "expected_direction": "decrease",
                               "unit": "us", "baseline_profile_hash": profiles[0], "candidate_profile_hash": profiles[1]}]}
        evidence["artifacts"]["mechanism_report"] = register_json_artifact(store, report)
    return value, replacements


def finalize_with_profile_fixture(context, request, *, graph, **kwargs):
    """Keep routing/planning tests complete while testing new source admission."""
    if __version__ == "0.2.0":
        return finalize_episodes(context, request, graph=graph, **kwargs)
    with tempfile.TemporaryDirectory() as directory, EpisodeStore(Path(directory) / "proof.sqlite") as store:
        value, replacements = bind_profiles(to_primitive(request), store)
        text = json.dumps(to_primitive(context))
        for before, after in replacements.items():
            text = text.replace(before, after)
        context_value = json.loads(text)
        if "architecture_profile" in context_value["evidence"]:
            from test_planning import rebind
            rebind(context_value)
        return finalize_episodes(Context.from_dict(context_value), GateRequest.from_dict(value), graph=graph, store=store, **kwargs)
