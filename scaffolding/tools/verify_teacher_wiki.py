#!/usr/bin/env python3
"""Check the frozen 1.0.0 teacher inventory and Wiki references."""
from __future__ import annotations

import argparse
import ast
import tomllib
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import sys


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text())


def source(path: Path, workspace: Path) -> dict[str, str]:
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(workspace):
        raise ValueError(f"source escapes workspace: {path}")
    return {"path": resolved.relative_to(workspace).as_posix(), "sha256": digest(resolved.read_bytes())}


def checked_file(reference: dict, workspace: Path) -> Path:
    """Resolve a receipt attachment without trusting its location or checksum."""
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise ValueError("receipt requires a path and sha256")
    relative = Path(reference["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("receipt path must be workspace-relative")
    path = workspace / relative
    if source(path, workspace) != reference:
        raise ValueError(f"receipt attachment hash differs: {relative}")
    return path.resolve()


# Actual stable 0.5.1 manifest after successful independent publication replay.
TASK_BASELINE_MANIFEST_SHA256 = "sha256:1beca6ff9ea1fa3cda83904c8637ce5d047860cbefe86b3ad4d247ff22309b1b"
TASK_BASELINE_RUNTIME_VERSION = "0.2.2"
TASK_RUNTIME_VERSION = "0.2.3"
TASK_RUNTIME_BUILD = "aprof-runtime/" + TASK_RUNTIME_VERSION
# User-authorized Task v5, complete-call PMU, unkeyed dispatch and frozen-parent
# budget replay and explicitly scoped replay of retained producer bytes.
# Only dispatch-plan adds a schema branch; the graph, other
# contracts and acceptance thresholds remain frozen. These source identities do
# not grant hardware qualification or permission to publish.
TASK_RUNTIME_PATCH_FILES = {
    'runtime/pyproject.toml': 'sha256:c6c92780cb97f12e4c34b35c3f025275b698d8d9d3b3b00f5cd50adaff4af339',
    'runtime/src/aprof_runtime/__init__.py': 'sha256:05bcf6eb428f97bd09454cfc460f48808c58fa640742dc1a6793544dee2ca6f3',
    'runtime/src/aprof_runtime/store.py': 'sha256:f9e0630b5bdbaa5944571fbe53698ca28f1332e6d04a7f1c3ba574e5e31bd05e',
    'runtime/src/aprof_runtime/measurement_admission.py': 'sha256:6a168fa9f04dba02b5dfe78ed1d8bd3dee90753f66ae7331894960ee77ad18d6',
    'runtime/src/aprof_runtime/task_window_timing.py': 'sha256:347a7049173fe5a178ddfa9fcbd5598c4ededc49e6cdcf072e010370ec42ca2b',
    'runtime/src/aprof_runtime/task_window_measurement_admission.py': 'sha256:674cf69ad37ff7aa92700255b0bf0c6542e2a8df1682537aaeb74055c538f0b8',
    'runtime/src/aprof_runtime/exploration.py': 'sha256:39d6567fd4dd836576f4409385e2fc7b2e5f991da2fa7b3741dac1ac3553c5c6',
    'runtime/src/aprof_runtime/full_call_pmu.py': 'sha256:6dd6818b6a7da82e8f5f8449d8981e315eda06685b25da27bed8dc76142978e3',
    'runtime/src/aprof_runtime/planning.py': 'sha256:e4ab1bcc92ff56e0074f67d7223a3c11c510200b2b159bfd89b19512f2f5f3b2',
    'runtime/src/aprof_runtime/episodes.py': 'sha256:a391735e7399894661a9e95be31ab73206290a839b58ee2cd37ec92795dc177a',
    'schemas/dispatch-plan.schema.json': 'sha256:8f33520a31c808a1756cedaf58aa8b888446b0a2febd632669e699d6f6fde4ad',
    'runtime/src/aprof_runtime/measurement_entry.py': 'sha256:232117501d1988d65533ec307bd6687d59d43b35e6a745a379620b6a00490616',
    'runtime/src/aprof_runtime/task_measurement_admission.py': 'sha256:94ac9a989abb326dfc2dee50c26e7bdb42e33eba15ad13f65ef894c8491daba8',
}


def verify_frozen_machine_rules(repo: Path, release: Path) -> dict:
    """Bind the authorized Task runtime, retaining the old graph/contracts/math."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from verify_measurement_publication import BASELINE_MANIFEST, protected_rules, release_tool
    canonical = repo / "skill-libs/graph-base/0.5.0"
    baseline = repo / "skill-libs/graph-base/0.5.1"
    old_path, task_path = canonical / "release.json", baseline / "release.json"
    # Authenticate the verifier source before executing code from a release.
    if old_path.is_symlink() or digest(old_path.read_bytes()) != "sha256:" + BASELINE_MANIFEST:
        raise ValueError("canonical sealed 0.5.0 manifest changed")
    old = read_json(old_path)
    verifier = canonical / "tools/release.py"
    if (any(path.is_symlink() for path in (verifier, *verifier.parents))
            or digest(verifier.read_bytes()) != old["files"].get("tools/release.py")):
        raise ValueError("trusted release verifier changed")
    if not task_path.is_file() or task_path.is_symlink():
        raise ValueError("Task baseline requires an existing sealed 0.5.1 manifest")
    if (TASK_BASELINE_MANIFEST_SHA256 is None
            or digest(task_path.read_bytes()) != TASK_BASELINE_MANIFEST_SHA256):
        raise ValueError("Task baseline manifest is not bound to the accepted stable seal")
    tool = release_tool(canonical)
    manifest = tool.verify(baseline)
    if (manifest.get("release_id") != "graph-base/0.5.1"
            or manifest.get("skill_version") != "0.5.1"
            or manifest.get("runtime_version") != TASK_BASELINE_RUNTIME_VERSION
            or manifest.get("default_graph") != "v0002"
            or manifest.get("graphs") != old.get("graphs")):
        raise ValueError("sealed Task baseline identity differs")
    method = manifest.get("publication_evidence", {}).get("measurement_method", {})
    if (method.get("accepted") is not True
            or method.get("purpose") != "measurement_method_only_no_optimization_promotion"
            or method.get("protocol") != "shared_buffer_msprof_task_window_v4"
            or method.get("metric") != "msprof.op_summary.Task_Duration"):
        raise ValueError("sealed baseline lacks the Task method qualification identity")
    # This is static source/manifest checking, not historical hardware re-audit.
    protected_rules(baseline, canonical)
    runtime_metadata = tomllib.loads((baseline / "runtime/pyproject.toml").read_text())
    versions = [ast.literal_eval(node.value) for node in ast.parse(
        (baseline / "runtime/src/aprof_runtime/__init__.py").read_text()).body
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
            and target.id == "__version__" for target in node.targets)]
    if (runtime_metadata["project"]["version"] != TASK_BASELINE_RUNTIME_VERSION
            or versions != [TASK_BASELINE_RUNTIME_VERSION]):
        raise ValueError("sealed Task runtime package versions differ")
    prefixes = ("runtime/", "skillgraph/versions/", "schemas/")
    expected = {name: value for name, value in manifest["files"].items() if name.startswith(prefixes)}
    expected.update(TASK_RUNTIME_PATCH_FILES)
    if (not all(any(name.startswith(prefix) for name in expected) for prefix in prefixes)
            or "skillgraph/versions/v0002/graph.json" not in expected):
        raise ValueError("sealed Task baseline lacks protected machine-rule inventory")
    actual = {}
    for prefix in prefixes:
        directory = release / prefix
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("frozen machine-rule directory missing or symlinked")
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise ValueError("frozen machine-rule symlink")
            if not path.is_file():
                continue
            if path.suffix == ".pyc":
                py_source = (path.parent.parent / (path.name.split(".")[0] + ".py")
                             if path.parent.name == "__pycache__" else path.with_suffix(".py"))
                if py_source.relative_to(release).as_posix() in expected:
                    continue
            actual[path.relative_to(release).as_posix()] = digest(path.read_bytes())
    if actual != expected:
        changed = sorted(name for name in actual.keys() | expected.keys() if actual.get(name) != expected.get(name))
        raise ValueError("frozen machine-rule inventory differs from authorized 0.2.3 sources: " + ", ".join(changed[:12]))
    return {"protected_files": len(expected), "baseline_manifest_sha256": digest(old_path.read_bytes()),
            "task_baseline_manifest_sha256": digest(task_path.read_bytes()), "runtime_build": TASK_RUNTIME_BUILD}


def verify_promotion_runtime(release: Path, *, runtime_build=None, require_loaded=False) -> None:
    """Historical 0.2.1 records remain data; current promotion cannot mix runtimes."""
    if runtime_build is not None and runtime_build != TASK_RUNTIME_BUILD:
        raise ValueError("promotion runtime_build differs from authorized Task candidate")
    package = (release / "runtime/src/aprof_runtime").resolve(strict=True)
    for name, module in tuple(sys.modules.items()):
        if name != "aprof_runtime" and not name.startswith("aprof_runtime."):
            continue
        filename = getattr(module, "__file__", None)
        if not filename or not Path(filename).resolve().is_relative_to(package):
            raise ValueError("promotion must not mix runtime modules from another release")
    runtime = sys.modules.get("aprof_runtime")
    if ((require_loaded and runtime is None)
            or (runtime is not None and getattr(runtime, "__version__", None) != TASK_RUNTIME_VERSION)):
        raise ValueError("promotion must use the authorized Task runtime version")


@contextmanager
def campaign_store(database: Path):
    from aprof_runtime.store import _ReadOnlyArtifacts, default_object_directory, verify_store_connection
    connection = sqlite3.connect(database.resolve(strict=True).as_uri() + "?mode=ro", uri=True)
    try:
        objects = default_object_directory(database)
        verify_store_connection(connection, objects)
        yield _ReadOnlyArtifacts(connection, objects)
    finally:
        connection.close()


def verify_campaign(store, campaign_report_ref: str, *, anchor_path: Path, workspace: Path,
                    selected_registration_ref: str) -> dict:
    """Bind every preregistered attempt, including failures, to the repository anchor.

    The report contains anchor_ref, amendment_ref and attempts[operator][kind]
    with closure_ref, execution_ref, and (for passed v2 attempts) control_report_ref.
    A not_run closure has a failed prerequisite_ref and an empty/absent roster;
    no events or hardware executions are synthesized for blocked attempts.
    """
    from timing_admission import read, require, number, checked_path, verify_timing_admission
    anchor = read_json(anchor_path)
    anchor_ref = digest(anchor_path.read_bytes())
    report = read(store, campaign_report_ref)
    require(report.get("schema_version") == 1 and report.get("anchor_ref") == anchor_ref
            and anchor.get("schema_version") == 1 and anchor.get("max_attempts_per_kind") == 1,
            "promotion campaign does not match the repository preregistration")
    round_plan = read_json(checked_file(anchor["round_plan"], workspace))
    operators, kinds = anchor["operators"], anchor["attempt_order"]
    require(len(operators) == len(set(operators)) and len(kinds) == len(set(kinds))
            and round_plan["operators"] == operators and round_plan["attempt_order"] == kinds
            and round_plan["max_attempts_per_kind"] == 1
            and set(report.get("attempts", {})) == set(operators), "campaign attempt inventory differs")
    amendment_path = anchor_path.with_name(anchor_path.stem.removesuffix("-plan") + "-amendment-screen.json")
    amendment = read_json(amendment_path)
    require(report.get("amendment_ref") == digest(amendment_path.read_bytes())
            and amendment.get("schema_version") == 1 and amendment.get("kind") == "explore_screen_aggregate_api_fix"
            and amendment.get("campaign_anchor_ref") == anchor_ref
            and amendment.get("applies_to") == ["candidate-qualification"], "campaign amendment identity differs")
    new_driver = checked_file(amendment["new_driver"], workspace)
    checked_file(amendment["formula_source"], workspace)
    checked_file(amendment["diff"], workspace)
    selected = False
    count = 0
    for operator in operators:
        manifest_path = checked_file(anchor["attempt_manifests"][operator], workspace)
        manifest = read_json(manifest_path)
        entries = report["attempts"][operator]
        require(manifest.get("operator") == operator and set(manifest["attempts"]) == set(kinds)
                and set(entries) == set(kinds) and manifest["round_plan_ref"] == anchor["round_plan"]["sha256"],
                "campaign omitted or added a preregistered attempt")
        with campaign_store(manifest_path.parent / "evidence.sqlite") as archive:
            old_driver = Path(archive.verify_artifact(manifest["driver_ref"])).read_bytes()
            old = b"report['speedup']>=1.0"
            new = b"math.exp(statistics.fmean(math.log(r['speedup']) for r in report['per_case']))>=1.0"
            require(manifest["driver_ref"] == amendment["old_driver_ref"] and old_driver.count(old) == 1
                    and new_driver.read_bytes() == old_driver.replace(old, new, 1),
                    "campaign permits only the registered exploration aggregate API fix")
            previous_finish = number(anchor["inventory_anchored_at"])
            outcomes = {}
            for kind in kinds:
                binding, item = manifest["attempts"][kind], entries[kind]
                protocol = read(archive, binding["protocol_ref"])
                registration = read(archive, binding["registration_ref"])
                closure = read(archive, item["closure_ref"])
                wanted_sources = {role: manifest["source_hashes"][role if kind == "candidate-qualification" else "baseline"]
                                  for role in ("baseline", "candidate")}
                wanted_binaries = {role: manifest["binary_hashes"][role if kind == "candidate-qualification" else "baseline"]
                                   for role in ("baseline", "candidate")}
                require(closure.get("operator") == operator and closure.get("kind") == kind
                        and closure.get("protocol_ref") == binding["protocol_ref"]
                        and closure.get("registration_ref") == binding["registration_ref"]
                        and closure.get("status") in {"passed", "failed", "not_run"}
                        and closure.get("resampling") == "none"
                        and registration.get("protocol_ref") == binding["protocol_ref"]
                        and registration.get("run_id") == protocol.get("run_id")
                        and registration.get("candidate_id") == protocol.get("candidate_id")
                        and protocol.get("operator") == operator
                        and registration.get("max_attempts") == 1 and registration.get("stop_on_failure") is True
                        and registration.get("resampling") == "none"
                        and protocol.get("round_plan_ref") == manifest["round_plan_ref"]
                        and protocol.get("driver_ref") == manifest["driver_ref"]
                        and protocol.get("source_hashes") == wanted_sources and protocol.get("binary_hashes") == wanted_binaries
                        and number(protocol["created_at"]) <= number(registration["created_at"])
                        <= number(anchor["inventory_anchored_at"]), "campaign attempt identity or preregistration differs")
                for ref in protocol.get("history_refs", []):
                    archive.verify_artifact(ref)
                require(protocol.get("history_refs"), "campaign omitted prior failed qualification")
                roster_ref = closure.get("attempt_roster_ref")
                roster = read(archive, roster_ref) if roster_ref else None
                if roster is not None:
                    require(roster.get("schema_version") == 1 and roster.get("registration_ref") == binding["registration_ref"],
                            "campaign roster registration differs")
                    live = manifest_path.parent / kind / "attempt-roster.json"
                    if live.exists():
                        require(read_json(live) == roster, "campaign omitted events from the current attempt roster")
                live_closure = manifest_path.parent / kind / "closure.json"
                if live_closure.exists():
                    require(read_json(live_closure) == closure, "campaign closure differs from the recorded attempt")
                status = closure["status"]
                predecessor = {"v2-confirmation": "v2-diagnostic", "candidate-qualification": "v2-confirmation"}.get(kind)
                if status != "not_run" and predecessor is not None:
                    require(predecessor in outcomes and outcomes[predecessor]["status"] == "passed",
                            "campaign executed an attempt after its prerequisite failed")
                if status == "not_run":
                    require(predecessor in outcomes and outcomes[predecessor]["status"] != "passed"
                            and closure.get("prerequisite_ref") == entries[predecessor]["closure_ref"]
                            and (roster is None or roster.get("events") == [])
                            and not item.get("execution_ref") and not closure.get("collected"),
                            "campaign not_run attempt lacks a failed prerequisite or has executed evidence")
                    live_roster = manifest_path.parent / kind / "attempt-roster.json"
                    if live_roster.exists():
                        require(read_json(live_roster).get("events") == [], "campaign hides an executed attempt as not_run")
                    require(not (manifest_path.parent / kind / "job/execution.json").exists(),
                            "campaign hides an executed job as not_run")
                else:
                    require(roster is not None and len(roster.get("events", [])) % 2 == 0 and roster["events"],
                            "campaign executed attempt lacks terminal stage events")
                    stages = registration["stages"]
                    require(len(roster["events"]) <= 2 * len(stages)
                            and (status != "passed" or len(roster["events"]) == 2 * len(stages)),
                            "campaign attempt stage count differs")
                    previous, clock = binding["registration_ref"], previous_finish
                    failed = False
                    first_at = None
                    for index, event_ref in enumerate(roster["events"]):
                        event = read(archive, event_ref)
                        require(event.get("sequence") == index and event.get("previous_ref") == previous
                                and event.get("registration_ref") == binding["registration_ref"]
                                and event.get("stage") == stages[index // 2]
                                and event.get("state") == ("started", "completed")[index % 2]
                                and number(event["at"]) >= clock, "campaign history was reordered, replayed or omitted")
                        first_at = event["at"] if first_at is None else first_at
                        if index % 2:
                            require(event.get("evidence_refs") and type(event.get("exit_status")) is int,
                                    "campaign completed stage lacks actual evidence")
                            for ref in event["evidence_refs"]:
                                archive.verify_artifact(ref)
                            failed |= event["exit_status"] != 0
                            require(kind == "legacy-diagnostic" or not failed or index == len(roster["events"]) - 1,
                                    "campaign continued after a mandatory failure")
                        previous, clock = event_ref, event["at"]
                    require(number(closure["finished_at"]) >= clock and (status != "passed" or not failed),
                            "campaign closure contradicts stage results")
                    execution = read(archive, item["execution_ref"])
                    checked_path(archive, manifest_path.parent / kind / "job/execution.json", item["execution_ref"])
                    argv = execution["job"]["argv"]
                    require(len(argv) == 5 and argv[2:] == ["execute", operator, kind]
                            and (status != "passed" or execution.get("status") == "passed" and execution.get("exit_code") == 0),
                            "campaign job receipt identity/result differs")
                    driver_ref = amendment["new_driver"]["sha256"] if kind == "candidate-qualification" else manifest["driver_ref"]
                    checked_path(archive, argv[1], driver_ref)
                    if kind == "candidate-qualification":
                        require(number(amendment["registered_at"]) < first_at
                                and Path(argv[1]).resolve() == new_driver.resolve(),
                                "campaign driver amendment was not registered before candidate execution")
                    start = datetime.fromisoformat(execution["started_at"].replace("Z", "+00:00")).timestamp()
                    finish = datetime.fromisoformat(execution["finished_at"].replace("Z", "+00:00")).timestamp()
                    require(previous_finish <= start <= first_at <= closure["finished_at"] <= finish,
                            "campaign execution chronology differs")
                    for key in ("stdout", "stderr"):
                        checked_path(archive, execution[key]["path"], execution[key]["sha256"])
                    previous_finish = finish
                    for phase, pointers in closure.get("collected", {}).items():
                        require(pointers["config_ref"] == protocol["phases"][phase]["config_ref"],
                                "campaign measured an unregistered config")
                        for ref in pointers.values():
                            archive.verify_artifact(ref)
                    if status == "passed" and kind != "legacy-diagnostic":
                        control = read(archive, item["control_report_ref"])
                        require(control.get("protocol_ref") == binding["protocol_ref"]
                                and control.get("attempt_roster_ref") == roster_ref
                                and all(control.get(phase) == refs for phase, refs in closure["collected"].items()),
                                "campaign control report differs from the actual attempt")
                        expected = {key: protocol[key] for key in ("run_id", "candidate_id", "operator", "source_hashes", "purpose")}
                        expected["registration_ref"] = binding["registration_ref"]
                        verify_timing_admission(archive, item["control_report_ref"], expected=expected)
                outcomes[kind] = closure
                if binding["registration_ref"] == selected_registration_ref:
                    require(kind == "candidate-qualification" and status == "passed"
                            and outcomes["v2-diagnostic"]["status"] == "passed"
                            and outcomes["v2-confirmation"]["status"] == "passed",
                            "selected promotion did not pass the preregistered prerequisite chain")
                    selected = True
                count += 1
    require(selected, "promotion selected an unregistered replacement run")
    return {"anchor_ref": anchor_ref, "attempts": count, "selected_registration_ref": selected_registration_ref}


def verify_promotion(event: dict, entry: dict, records: dict, repo: Path, release: Path) -> dict:
    """Admission replays a formal graph or exploration gate using frozen CAS.

    Accepted evolution events reference a hash-bound receipt with proposal_id,
    wiki_id, source_keys, target_skill, skill_before (path/sha256),
    skill_after (path/sha256) and validations. Each validation contains run_id,
    store/trace (path/sha256), correctness_report_ref, boundary_report_ref and
    hardware_report_ref, control_report_ref and registration_ref. Reports are
    CAS artifacts linked by the episode; controls are replayed independently.
    """
    workspace = repo.parent.resolve()
    receipt = read_json(checked_file(event.get("validation_receipt"), workspace))
    for key in ("proposal_id", "wiki_id", "target_skill"):
        if not event.get(key) or receipt.get(key) != event[key]:
            raise ValueError(f"promotion receipt {key} mismatch")
    if receipt.get("schema_version") != 1 or receipt.get("source_keys") != entry["source_keys"]:
        raise ValueError("promotion receipt source inventory mismatch")
    skill = Path(event["target_skill"])
    if (skill.is_absolute() or len(skill.parts) != 3 or skill.parts[0] != "skills"
            or skill.name != "SKILL.md" or ".." in skill.parts
            or entry["skill_refs"] != [skill.as_posix()]):
        raise ValueError("promotion must modify exactly one canonical skill")
    target = (release / skill).resolve(strict=True)
    if not target.is_relative_to((release / "skills").resolve()):
        raise ValueError("promotion skill escapes release")
    before = checked_file(receipt.get("skill_before"), workspace)
    after = checked_file(receipt.get("skill_after"), workspace)
    if before.read_bytes() == after.read_bytes():
        raise ValueError("promotion skill edit is empty")
    validations = receipt.get("validations")
    if not isinstance(validations, list) or not validations:
        raise ValueError("promotion needs independent formal validation")

    machine_rules = verify_frozen_machine_rules(repo, release)
    verify_promotion_runtime(release)
    runtime = release / "runtime/src"
    sys.path.insert(0, str(runtime))
    from aprof_runtime.contracts import CandidateEpisode
    from aprof_runtime.planning import architecture_id
    from aprof_runtime.store import (_ReadOnlyArtifacts, default_object_directory,
                                     verify_store_connection)
    from aprof_runtime.traces import validate_optimization_trace
    import aprof_runtime
    verify_promotion_runtime(release, require_loaded=True)

    class ReadOnlyReplay(_ReadOnlyArtifacts):
        # Exploration replay re-registers its request; it must already be in CAS.
        def object_path(self, ref):
            return self.verify_artifact(ref)

        def register_artifact(self, path, **_kwargs):
            ref = digest(Path(path).read_bytes())
            self.verify_artifact(ref)
            return ref

    members = split_members(repo)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "collection/scripts"))
    from timing_admission import verify_timing_admission, verify_boundary_report, verify_profile_window
    source_operators = {records[key]["operator"] for key in entry["source_keys"]}
    historical_names = {part for row in records.values() for ref in row["sources"]
                        for part in Path(ref["path"]).parts}
    seen, validated_operators = set(), set()
    for validation in validations:
        trace = read_json(checked_file(validation.get("trace"), workspace))
        identity = trace["identity"]
        run_id = validation.get("run_id")
        if not run_id or run_id != identity["run_id"] or run_id in historical_names:
            raise ValueError("promotion must use an independent run identity")
        key = (run_id, identity["candidate_id"])
        if key in seen:
            raise ValueError("duplicate promotion validation")
        seen.add(key)
        operator = identity["operator"]
        if members.get(operator) != "train" or identity["split"] != "train":
            raise ValueError("validation/test run cannot promote a skill")
        if operator not in source_operators:
            raise ValueError("promotion operator has no curated source")
        database = checked_file(validation.get("store"), workspace)
        connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
        try:
            objects = default_object_directory(database)
            verify_store_connection(connection, objects)
            store = ReadOnlyReplay(connection, objects)
            validate_optimization_trace(trace, store)
            result = trace["result"]
            if result["verdict"] != "production_safe_gain":
                raise ValueError("promotion requires formal production_safe_gain")
            if trace["routing"]["mode"] == "graph" and result["episode_ref"]:
                row = connection.execute("SELECT payload_json FROM episodes WHERE episode_hash=?",
                                         (result["episode_ref"],)).fetchone()
                episode = CandidateEpisode.from_dict(json.loads(row[0]))
                verify_promotion_runtime(release, runtime_build=episode.runtime_build, require_loaded=True)
                if (episode.runtime_build != machine_rules["runtime_build"]
                        or episode.graph_snapshot != read_json(release / "skillgraph/versions/v0002/graph.json")
                        or episode.context.operator != operator or episode.context.task_id != identity["task_id"]
                        or episode.draft.session_id != identity["session_id"]
                        or episode.context.hardware_fingerprint != trace["workload"]["hardware_fingerprint"]):
                    raise ValueError("promotion episode identity or frozen graph differs")
                artifacts = episode.evidence.artifacts
                sources = {"baseline": episode.draft.source_hashes.baseline,
                           "candidate": episode.draft.source_hashes.candidate}
            elif trace["routing"]["mode"] == "exploration" and result["exploration_outcome_ref"]:
                outcome = read_json(store.verify_artifact(result["exploration_outcome_ref"]))
                request = read_json(store.verify_artifact(outcome["request_hash"]))
                manifest = read_json(store.verify_artifact(request["frozen_manifest_hash"]))
                if any(manifest[name] != identity[name] for name in ("run_id", "task_id", "split")):
                    raise ValueError("promotion exploration run differs from frozen manifest")
                draft = next(row for row in request["candidates"] if row["candidate_id"] == identity["candidate_id"])
                measured = next(row for row in request["evidence"] if row["candidate_id"] == identity["candidate_id"])
                if draft["session_id"] != identity["session_id"]:
                    raise ValueError("promotion exploration session differs")
                artifacts, sources = measured["artifacts"], draft["source_hashes"]
            else:
                raise ValueError("promotion lacks a replayable formal machine outcome")
            if (validation.get("original_baseline_hash") != sources["baseline"]
                    or validation.get("direct_parent_hash") != identity["source_parent_hash"]):
                raise ValueError("promotion must bind original baseline and direct parent")
            store.verify_artifact(validation["direct_parent_hash"])
            if validation["direct_parent_hash"] != sources["baseline"]:
                ref = validation.get("parent_comparison_ref")
                if not ref or ref != artifacts.get("parent_comparison"):
                    raise ValueError("promotion lacks direct-parent comparison evidence")
                store.verify_artifact(ref)
            reports = {}
            for name, role in (("correctness", "accuracy_report"), ("boundary", "boundary_report"),
                               ("hardware", "hardware_report")):
                ref = validation.get(name + "_report_ref")
                if not ref or ref != artifacts.get(role):
                    raise ValueError(f"promotion lacks gate-bound {name} report")
                reports[name] = read_json(store.verify_artifact(ref))
            hardware = reports["hardware"]
            if (architecture_id(hardware.get("soc", "")) != "910c"
                    or not (hardware.get("cann_version") or hardware.get("toolchain_identity"))
                    or hardware.get("hardware_fingerprint", validation["hardware_report_ref"])
                    != trace["workload"]["hardware_fingerprint"]):
                raise ValueError("promotion hardware/toolchain scope is not verified 910C/A3")
            mechanism = read_json(store.verify_artifact(artifacts["mechanism_report"]))
            for metric in mechanism["metrics"]:
                for role in ("baseline", "candidate"):
                    profile = read_json(store.verify_artifact(metric[role + "_profile_hash"]))
                    if profile.get("schema_version") != "1.1.0":
                        raise ValueError("promotion requires source-bound independent v1.1 profiles")
                    capture = read_json(store.verify_artifact(profile["capture_manifest_hash"]))
                    if capture["hardware_hash"] != validation["hardware_report_ref"]:
                        raise ValueError("promotion hardware report differs from measured captures")
            for name in ("correctness", "boundary"):
                report = reports[name]
                cases = report.get("case_ids", [])
                if (report.get("run_id") != run_id or report.get("candidate_id") != identity["candidate_id"]
                        or report.get("source_hashes") != sources or report.get("status") != "passed"
                        or not cases or len(cases) != len(set(cases)) or report.get("passed_case_ids") != cases):
                    raise ValueError(f"promotion {name} report incomplete or source identity differs")
                execution = report.get("execution", {})
                if execution.get("exit_status") != 0 or not execution.get("log_ref"):
                    raise ValueError(f"promotion {name} execution receipt missing")
                store.verify_artifact(execution["log_ref"])
            declared = trace["workload"]["case_ids"]
            if (reports["correctness"]["case_ids"] != declared
                    or trace["validation"]["case_count"] != len(declared)
                    or trace["validation"]["passed_count"] != len(declared)
                    or any(trace["validation"][stage]["status"] != "passed"
                           for stage in ("correctness", "runtime", "timing", "profile"))):
                raise ValueError("promotion did not pass full declared correctness and measurement")
            if set(reports["boundary"]["case_ids"]) & set(declared):
                raise ValueError("promotion boundary checks must be additional cases")
            control_ref = validation.get("control_report_ref")
            registration_ref = validation.get("registration_ref")
            if (not control_ref or control_ref != artifacts.get("control_report")
                    or not registration_ref or registration_ref != artifacts.get("qualification_registration")):
                raise ValueError("promotion lacks gate-bound control report or preregistration")
            expected = {"run_id": run_id, "candidate_id": identity["candidate_id"], "operator": operator,
                        "source_hashes": sources, "registration_ref": registration_ref, "purpose": "promotion",
                        "hardware_report_ref": validation["hardware_report_ref"],
                        "formal_refs": {"raw_ref": artifacts.get("timing_raw"),
                                        "config_ref": artifacts.get("timing_config"),
                                        "report_ref": artifacts.get("measurement_report")}}
            admission = verify_timing_admission(store, control_ref, expected=expected)
            verify_profile_window(store, artifacts["mechanism_report"], window=admission["stage_windows"]["profile"],
                                  control_report_ref=control_ref)
            expected["boundary_window"] = admission["stage_windows"]["boundary"]
            verify_boundary_report(store, validation["boundary_report_ref"],
                                   protocol_ref=admission["protocol_ref"], expected=expected)
            campaign_ref = validation.get("campaign_report_ref")
            if not campaign_ref or campaign_ref != artifacts.get("qualification_campaign"):
                raise ValueError("promotion lacks gate-bound complete qualification campaign")
            verify_campaign(store, campaign_ref,
                            anchor_path=repo / "scaffolding/curation/graph-base-1.0.0-round2-plan.json",
                            workspace=workspace, selected_registration_ref=registration_ref)
            validated_operators.add(operator)
        finally:
            connection.close()
    if validated_operators != source_operators:
        raise ValueError("validated Wiki scope lacks independent receipts for every source operator")
    return {"target_skill": skill.as_posix(), "before": digest(before.read_bytes()),
            "after": digest(after.read_bytes())}


def split_members(repo: Path) -> dict[str, str]:
    root = repo / "scaffolding/benchmarks/cannbench"
    result = {}
    for split in ("train", "validation", "test"):
        names = (root / split / "operators.txt").read_text().splitlines()
        if names != read_json(root / split / "manifest.json")["active_operators"]:
            raise ValueError(f"split list differs from frozen manifest: {split}")
        for name in names:
            if name in result:
                raise ValueError(f"operator in multiple splits: {name}")
            result[name] = split
    return result


def inventory(repo: Path, traces: Path) -> dict[str, dict]:
    workspace = repo.parent.resolve()
    members = split_members(repo)
    result = {}
    for item in read_json(traces / "level1/lesson-catalog.json"):
        occurrence = item["occurrences"][0]
        path = traces / occurrence["path"]
        line = path.read_bytes().splitlines()[occurrence["line"] - 1]
        lesson = json.loads(line)
        body = lesson["body"]
        if lesson["id"] != item["id"] or lesson["record_hash"] != occurrence["record_hash"]:
            raise ValueError(f"lesson catalog mismatch: {item['id']}")
        operator = body["operator"]
        split = members.get(operator) if operator else body["split"]
        if split is None:
            raise ValueError(f"unknown operator: {operator}")
        result["l1:" + item["id"]] = {
            "level": 1, "operator": operator, "split": split,
            "sources": [{"path": path.resolve().relative_to(workspace).as_posix(),
                         "sha256": digest(line), "record_hash": lesson["record_hash"]}],
        }

    level2 = read_json(traces / "index.json")["level2"]
    feedback_paths = [traces / name for name in level2["readable_files"]
                      if "/feedback/" in name and name.endswith(".json")]
    feedback_paths += [Path(value["path"]) for key, value in level2["live_continuation"].items()
                       if key.startswith("cummin") and key.endswith("_feedback")]
    for path in feedback_paths:
        feedback = read_json(path)
        candidate = feedback.get("candidate_id")
        if not candidate or candidate == "baseline":
            continue
        operator = path.parts[path.parts.index("tasks") + 1]
        split = members.get(operator)
        if split is None:
            raise ValueError(f"unknown Level2 operator: {operator}")
        key = "l2:" + candidate
        row = result.setdefault(key, {"level": 2, "operator": operator,
                                      "split": split, "sources": []})
        if row["operator"] != operator:
            raise ValueError(f"candidate reused by operators: {candidate}")
        row["sources"].append(source(path, workspace))
    for row in result.values():
        row["sources"].sort(key=lambda value: value["path"])
    if len([key for key in result if key.startswith("l1:")]) != 26:
        raise ValueError("Level1 lesson inventory changed")
    if len([key for key in result if key.startswith("l2:")]) != level2["closed_attempts"]:
        raise ValueError("Level2 closed-attempt inventory changed")
    return result


def verify(repo: Path, traces: Path, release: Path, audit_path: Path, *, task_promotion=None) -> dict:
    verify_frozen_machine_rules(repo, release)
    workspace = repo.parent.resolve()
    audit = read_json(audit_path)
    if audit["trace_index_sha256"] != digest((traces / "index.json").read_bytes()):
        raise ValueError("trace index changed")
    split_path = repo / "scaffolding/benchmarks/cannbench/split_index.json"
    if audit["split_index_sha256"] != digest(split_path.read_bytes()):
        raise ValueError("split index changed")
    actual = inventory(repo, traces)
    records = audit["records"]
    if set(records) != set(actual):
        raise ValueError(f"source inventory differs: missing={set(actual)-set(records)}, extra={set(records)-set(actual)}")
    wiki = read_json(release / "wiki/index.json")
    entries = wiki["entries"]
    events = [json.loads(line) for line in (release / "wiki/evolution.jsonl").read_text().splitlines()]
    accepted = {}
    for event in events:
        if event["wiki_id"] not in entries or event["decision"] not in ("deferred", "rejected", "accepted"):
            raise ValueError("unknown evolution decision or Wiki entry")
        if not event.get("reason"):
            raise ValueError("evolution decision lacks reason")
        for reference in event.get("evidence_refs", []):
            checked_file(reference, repo.parent.resolve())
        if event["decision"] == "accepted":
            if event["wiki_id"] in accepted:
                raise ValueError("duplicate accepted Wiki promotion")
            accepted[event["wiki_id"]] = event
    graph = read_json(release / "skillgraph/versions/v0002/graph.json")
    graph_ids = {node["id"] for group in ("anchors", "predicates", "mechanisms", "transformations")
                 for node in graph[group]}
    for key, row in records.items():
        original = {name: row[name] for name in ("level", "operator", "split", "sources")}
        if original != actual[key]:
            raise ValueError(f"source or current split changed: {key}")
        if row["decision"] not in ("include", "merge", "exclude") or not row["reason"]:
            raise ValueError(f"missing teacher decision: {key}")
        refs = row["wiki_ids"]
        if row["decision"] == "exclude" and refs or row["decision"] != "exclude" and not refs:
            raise ValueError(f"invalid Wiki decision: {key}")
        if row["split"] != "train" and row["decision"] != "exclude":
            raise ValueError(f"validation/test source entered Wiki: {key}")
        if any(ref not in entries for ref in refs):
            raise ValueError(f"missing Wiki entry for {key}")
    for wiki_id, entry in entries.items():
        page = (release / "wiki" / entry["page"]).resolve(strict=True)
        if not page.is_relative_to((release / "wiki").resolve()):
            raise ValueError(f"Wiki page escapes release: {wiki_id}")
        body = page.read_text()
        if any(heading not in body for heading in ("## 适用条件", "## 证据与反例", "## 验证与结论")):
            raise ValueError(f"incomplete Wiki page: {wiki_id}")
        if (entry["status"] == "draft" and (entry["skill_refs"] or wiki_id in accepted)
                or entry["status"] == "validated" and wiki_id not in accepted
                or entry["status"] not in ("draft", "validated")):
            raise ValueError(f"unverified 1.0.0 knowledge promoted: {wiki_id}")
        if not entry["source_keys"] or any(key not in records or wiki_id not in records[key]["wiki_ids"]
                                             for key in entry["source_keys"]):
            raise ValueError(f"Wiki source mismatch: {wiki_id}")
        expected_refs = [{"key": key, "sha256": [item["sha256"] for item in records[key]["sources"]]}
                         for key in entry["source_keys"]]
        if entry["source_refs"] != expected_refs or not entry["toolchain_scope"]:
            raise ValueError(f"Wiki evidence hash or toolchain scope mismatch: {wiki_id}")
        if any(node not in graph_ids for node in entry["graph_nodes"]):
            raise ValueError(f"unknown graph node: {wiki_id}")
    if task_promotion is not None and set(accepted) != {'exp-tile8192'}:
        raise ValueError('scoped Task publication requires exactly one accepted exp rule')
    skill_heads = {}
    for wiki_id, event in accepted.items():
        if task_promotion is None:
            edit = verify_promotion(event, entries[wiki_id], records, repo, release)
        else:
            # The trusted publication caller supplies a replay function, not a verdict.
            result = task_promotion(event)
            edit = result['edit']
            if (result.get('valid') is not True or result.get('operator') != 'exp'
                    or result.get('eligible_for_teacher_edit') is not True
                    or not edit.get('applied') or entries[wiki_id]['skill_refs'] != [edit['target_skill']]):
                raise ValueError('Task promotion is not the applied single exp skill revision')
        target = edit["target_skill"]
        if target in skill_heads and skill_heads[target] != edit["before"]:
            raise ValueError(f"promotion skill edits do not form a local revision chain: {target}")
        skill_heads[target] = edit["after"]
    for target, expected in skill_heads.items():
        if digest((release / target).read_bytes()) != expected:
            raise ValueError(f"published skill differs from accepted proposal: {target}")
    return {"records": len(records), "wiki_pages": len(entries), "graph_version": graph["graph_version"],
            "promoted_skills": len(skill_heads)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    repo = args.repo.resolve()
    result = verify(repo, repo.parent / "optimization-traces", repo / "skill-libs/graph-base/1.0.0",
                    repo / "scaffolding/curation/graph-base-1.0.0.json")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
