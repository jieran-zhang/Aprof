"""Strict, hash-bound planning artifacts; legacy episode wire formats stay intact.

Validation establishes declared identities, applicability and capacity, not the
truth of an algorithm or hardware measurement. Evidence remains auditable CAS.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

from jsonschema import Draft202012Validator

from .errors import ContractError
from .jsonio import content_hash, require_json_value

VERSION = "1.0.0"
STAGES = ("algorithm_parallel", "execution")
S = {"type": "string", "minLength": 1}
H = {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}
I = {"type": "integer", "minimum": 0}
N = {"type": ["integer", "null"], "minimum": 1}
SS = {"type": "array", "items": S, "uniqueItems": True}
MEMORIES = ("UB", "L1", "L0_A", "L0_B", "L0_C", "L2", "BT")


def obj(fields, required=None):
    return {"type": "object", "additionalProperties": False, "properties": fields,
            "required": list(fields) if required is None else required}


def arr(item, **constraints):
    return {"type": "array", "items": item, **constraints}


CAPABILITY = obj({"status": {"enum": ["supported", "unsupported", "unknown"]},
                  "basis": S, "evidence_refs": arr(H)})
COMPILER = obj({"status": {"enum": ["verified", "unknown", "error"]},
                "path": {"anyOf": [S, {"type": "null"}]},
                "version": {"anyOf": [S, {"type": "null"}]}, "evidence_refs": arr(H)})
ARCHITECTURE_PROFILE = obj({
    "schema_version": {"const": VERSION}, "hardware_fingerprint": S,
    "architecture_id": {"enum": ["910b", "910c", "950", "unknown"]},
    "soc_name": {"type": ["string", "null"]}, "npu_arch": N,
    "sdk_version": S, "probe_kind": {"enum": ["device", "sdk_soc", "unavailable"]},
    "device_id": {"type": ["integer", "null"], "minimum": 0},
    "core_counts": obj({"aic": N, "aiv": N}),
    "memory_bytes": obj({name: N for name in MEMORIES}),
    "capabilities": {"type": "object", "additionalProperties": CAPABILITY},
    "provenance": obj({"probe_source_ref": H, "raw_probe_ref": H,
                       "sdk_header_ref": {"anyOf": [H, {"type": "null"}]} }),
    "limitations": SS,
})
# Additive fields preserve already frozen profiles. SDK capacities are not a
# claim about runtime-visible allocations or the compiler used by a candidate.
ARCHITECTURE_PROFILE['properties'].update(visible_core_counts=obj({"aic": N, "aiv": N}), compiler=COMPILER)
ARCHITECTURE_PROFILE['properties']['provenance']['properties']['acl_header_ref'] = {"anyOf": [H, {"type": "null"}]}
GROUP = obj({"group_id": S, "algorithm": S, "task_partition": S, "ownership": S,
             "reduction": S, "synchronization": S, "workspace_bytes": I,
             "workspace_formula": S, "required_capabilities": SS,
             "memory_requirements": obj({name: I for name in MEMORIES}, []),
             "alternatives": SS, "selection_evidence": arr(H, minItems=1)})
PARALLEL_PLAN = obj({"schema_version": {"const": VERSION}, "plan_id": S, "operator": S,
                     "source_hash": H, "architecture_profile_ref": H,
                     "semantic_invariants": {**SS, "minItems": 1},
                     "precision_invariants": {**SS, "minItems": 1},
                     "groups": arr(GROUP, minItems=1)})
SCALAR = {"type": ["string", "number", "boolean"]}
CONDITION = obj({"field": {"type": "string", "pattern": r"^(dtype|layout|numel|shape\.[0-9]+|attributes\.[A-Za-z][A-Za-z0-9_]*)$"},
                 "op": {"enum": ["eq", "ne", "lt", "le", "gt", "ge", "in"]},
                 "value": {"anyOf": [SCALAR, arr(SCALAR, minItems=1)]}})
ENTRY = obj({"group_id": S, "tiling_key": {**I, "maximum": 2**64 - 1},
             "kernel_entry": {"type": "string", "pattern": "^[A-Za-z_][A-Za-z0-9_]*$"},
             "conditions": arr(CONDITION), "required_capabilities": SS})
DISPATCH_PLAN = obj({"schema_version": {"const": VERSION}, "dispatch_id": S,
                     "operator": S, "source_hash": H, "architecture_profile_ref": H,
                     "parallel_plan_ref": H, "entries": arr(ENTRY), "fallback": ENTRY,
                     "plan_basis_source_hash": H, "implementation_source_hash": H},
                    ["schema_version", "dispatch_id", "operator", "source_hash", "architecture_profile_ref",
                     "parallel_plan_ref", "entries", "fallback"])
WORKLOAD = obj({"shape": arr(I), "dtype": S, "layout": S,
                "attributes": {"type": "object", "additionalProperties": SCALAR}},
               ["shape", "dtype", "layout", "attributes"])
UNKEYED_MODE = "unkeyed_complete_call"
UNKEYED_CASE = obj({"metadata_ref": H, "workload": WORKLOAD, "group_id": S,
    "role_kernel_names": obj({role: arr({"type": "string",
        "pattern": "^aprof_" + role + "_[A-Za-z_][A-Za-z0-9_]*$"}, minItems=1)
        for role in ("baseline", "candidate")})})
UNKEYED_DISPATCH = obj({
    **{key: DISPATCH_PLAN["properties"][key] for key in (
        "schema_version", "dispatch_id", "operator", "source_hash", "architecture_profile_ref",
        "parallel_plan_ref", "plan_basis_source_hash", "implementation_source_hash")},
    "mode": {"const": UNKEYED_MODE}, "scope": {"const": "declared_workloads_only"},
    "source_review_ref": H, "declared_workloads": arr(UNKEYED_CASE, minItems=20, maxItems=20),
})
SCHEMAS = {"architecture_profile": ARCHITECTURE_PROFILE, "parallel_plan": PARALLEL_PLAN,
           "dispatch_plan": {"oneOf": [DISPATCH_PLAN, UNKEYED_DISPATCH]}}



def schema(kind):
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"https://aprof.local/schemas/{kind.replace('_', '-')}.schema.json",
            **deepcopy(SCHEMAS[kind])}


def _validate(shape, value, label):
    require_json_value(value)
    error = next(Draft202012Validator(shape).iter_errors(value), None)
    if error:
        path = ".".join(str(p) for p in error.absolute_path)
        raise ContractError(f"{label}.{path}: {error.message}")


# Exact SoC identities reviewed in CANN 9.0.0 platform_config on 2026-10-05.
# This table classifies identities only; no resource or feature defaults follow.
# New SDK names stay unknown until reviewed. Ascend910B (without a SKU suffix)
# is an ambiguous older product name and is deliberately absent.
SOC_FAMILIES = {
    "910b": frozenset(name.lower() for name in (
        "Ascend910B1",
        "Ascend910B2",
        "Ascend910B2C",
        "Ascend910B3",
        "Ascend910B4-1",
        "Ascend910B4",
    )),
    "910c": frozenset(name.lower() for name in (
        "Ascend910_9362",
        "Ascend910_9372",
        "Ascend910_9381",
        "Ascend910_9382",
        "Ascend910_9391",
        "Ascend910_9392",
        "Ascend910C",  # Explicit legacy label; never a prefix match.
    )),
    "950": frozenset(name.lower() for name in (
        "Ascend950DT_950x",
        "Ascend950DT_950y",
        "Ascend950DT_9571",
        "Ascend950DT_9572",
        "Ascend950DT_9573",
        "Ascend950DT_9574",
        "Ascend950DT_9575",
        "Ascend950DT_9576",
        "Ascend950DT_9577",
        "Ascend950DT_9578",
        "Ascend950DT_9581",
        "Ascend950DT_9582",
        "Ascend950DT_9583",
        "Ascend950DT_9584",
        "Ascend950DT_9585",
        "Ascend950DT_9586",
        "Ascend950DT_9587",
        "Ascend950DT_9588",
        "Ascend950DT_9591",
        "Ascend950DT_9592",
        "Ascend950DT_9595",
        "Ascend950DT_9596",
        "Ascend950DT_95A1",
        "Ascend950DT_95A2",
        "Ascend950PR_950z",
        "Ascend950PR_9579",
        "Ascend950PR_957b",
        "Ascend950PR_957c",
        "Ascend950PR_957d",
        "Ascend950PR_9589",
        "Ascend950PR_958b",
        "Ascend950PR_9599",
    )),
}


def architecture_id(soc_name):
    """Match reviewed exact names, never the shared 2201 ISA or a prefix."""
    name = (soc_name or "").lower()
    return next((family for family, names in SOC_FAMILIES.items() if name in names), "unknown")

def validate_planning_contract(kind, value):
    if kind not in SCHEMAS:
        raise ContractError(f"unknown planning contract {kind!r}")
    _validate(SCHEMAS[kind], value, kind)
    if kind == "architecture_profile":
        if value["architecture_id"] != architecture_id(value["soc_name"]):
            raise ContractError("architecture_id disagrees with the exact SoC name")
        if value["probe_kind"] == "device" and value["device_id"] is None:
            raise ContractError("device probe requires device_id")
        expected_arch = {"910b": 2201, "910c": 2201, "950": 3510}.get(value["architecture_id"])
        if expected_arch and value["npu_arch"] not in {None, expected_arch}:
            raise ContractError("SoC and probed NPU architecture disagree")
        compiler = value.get("compiler", {})
        if compiler.get("status") == "verified" and not all(compiler.get(k) for k in ("path", "version", "evidence_refs")):
            raise ContractError("verified compiler requires path, version and evidence")
        for name, capability in value["capabilities"].items():
            if capability["status"] == "supported" and not capability["evidence_refs"]:
                raise ContractError(f"supported capability {name} lacks evidence")
            if capability["status"] == "supported" and name in {"vector", "cube"}:
                if not value["core_counts"]["aiv" if name == "vector" else "aic"]:
                    raise ContractError(f"supported {name} capability requires a positive core count")
            if capability["status"] == "supported" and name in {"simt", "ssbuffer"} and value["architecture_id"] != "950":
                raise ContractError(f"{name} requires a confirmed 950 architecture and compiler evidence")
            if capability["status"] == "supported" and name in {"simt", "ssbuffer"} and compiler.get("status") != "verified":
                raise ContractError(f"{name} requires a verified compiler plus API/flag compile evidence")
    elif kind == "parallel_plan":
        ids = [g["group_id"] for g in value["groups"]]
        if len(ids) != len(set(ids)):
            raise ContractError("duplicate parallel-plan group_id")
    else:
        if ("plan_basis_source_hash" in value) != ("implementation_source_hash" in value):
            raise ContractError("dispatch source lineage requires both plan basis and implementation hashes")
        if "implementation_source_hash" in value and value["source_hash"] != value["implementation_source_hash"]:
            raise ContractError("dispatch source_hash must identify its implementation")
        if value.get("mode") == UNKEYED_MODE:
            rows = value["declared_workloads"]
            if value["operator"] not in {"dynamic_quant", "gelu", "group_norm", "gqa", "weight_quant_batch_matmul"}:
                raise ContractError("unkeyed complete-call scope is the five declared validation operators")
            if len({row["metadata_ref"] for row in rows}) != 20:
                raise ContractError("unkeyed complete call needs 20 distinct original metadata artifacts")
            seen = {}
            for row in rows:
                names = row["role_kernel_names"]
                if ([name.removeprefix("aprof_baseline_") for name in names["baseline"]]
                        != [name.removeprefix("aprof_candidate_") for name in names["candidate"]]):
                    raise ContractError("unkeyed roles changed complete ordered kernel scope")
                if any(name.lower() in {"case", "case_id", "caseid", "test_id", "index"}
                       for name in row["workload"]["attributes"]):
                    raise ContractError("unkeyed selection uses workload metadata, never case identity")
                identity = content_hash(row["workload"])
                selected = {key: row[key] for key in ("group_id", "role_kernel_names")}
                if identity in seen and seen[identity] != selected:
                    raise ContractError("duplicate workload has inconsistent complete-call scope")
                seen[identity] = selected
            return deepcopy(value)
        entries = [*value["entries"], value["fallback"]]
        keys = [e["tiling_key"] for e in entries]
        if len(keys) != len(set(keys)):
            raise ContractError("duplicate dispatch tiling_key")
        if value["fallback"]["conditions"] or value["fallback"]["required_capabilities"]:
            raise ContractError("fallback must be unconditional with no optional capability requirements")
        for entry in value["entries"]:
            if not entry["conditions"]:
                raise ContractError("specialized entry requires metadata conditions")
            for condition in entry["conditions"]:
                field, op, target = (condition[k] for k in ("field", "op", "value"))
                if field.lower().split(".")[-1] in {"case", "case_id", "caseid", "test_id", "index"}:
                    raise ContractError("dispatch must use workload metadata, never benchmark case identity")
                if (op == "in") != isinstance(target, list):
                    raise ContractError("in requires an array; other operators require a scalar")
                if op in {"lt", "le", "gt", "ge"} and (isinstance(target, bool) or not isinstance(target, (int, float))):
                    raise ContractError("ordered dispatch conditions require numbers")
    return deepcopy(value)


def _bound(evidence, name):
    value = validate_planning_contract(name, evidence.get(name))
    if evidence.get(name + "_ref") != content_hash(value):
        raise ContractError(f"{name}_ref does not bind its canonical object")
    return value


def verify_profile_probe(profile, raw):
    """Recompute the SDK probe projection at the CAS admission boundary."""
    validate_planning_contract("architecture_profile", profile)
    if content_hash(raw) != profile["provenance"]["raw_probe_ref"]:
        raise ContractError("raw architecture probe does not match its reference")
    facts = raw.get("platform", {})
    expected = {
        "soc_name": raw.get("soc_name"), "probe_kind": raw.get("probe_kind"),
        "device_id": raw.get("device_id"), "npu_arch": facts.get("npu_arch") or None,
        "core_counts": {name: facts.get("core_counts", {}).get(name) or None for name in ("aic", "aiv")},
        "memory_bytes": {name: facts.get("memory_bytes", {}).get(name) or None for name in MEMORIES},
    }
    if "visible_core_counts" in profile:
        expected["visible_core_counts"] = {name: raw.get("visible_core_counts", {}).get(name) or None for name in ("aic", "aiv")}
    if "compiler" in profile:
        expected["compiler"] = raw.get("compiler", {"status": "unknown", "path": None, "version": None, "evidence_refs": []})
    if any(profile[name] != value for name, value in expected.items()):
        raise ContractError("architecture facts do not reproduce the bound raw probe")
    for name, core in (("vector", "aiv"), ("cube", "aic")):
        if profile["capabilities"].get(name, {}).get("status") == "supported" and not expected["core_counts"][core]:
            raise ContractError("architecture capability lacks a positive probed core count")


def _supported(profile, capabilities):
    return all(profile["capabilities"].get(c, {}).get("status") == "supported" for c in capabilities)


def validate_planning_context(context, *, execution=False):
    """Bind inline replayable objects to canonical CAS digests and source identity."""
    evidence = context.evidence
    profile = _bound(evidence, "architecture_profile")
    if profile["hardware_fingerprint"] != context.hardware_fingerprint:
        raise ContractError("architecture fingerprint does not match route context")
    if profile["architecture_id"] == "unknown":
        raise ContractError("unknown architecture permits only NOOP")
    if profile["npu_arch"] is None or not any(profile["core_counts"].values()):
        raise ContractError("architecture probe lacks target core capabilities")
    if not execution:
        return profile, None, None
    plan = _bound(evidence, "parallel_plan")
    dispatch = _bound(evidence, "dispatch_plan")
    if plan["architecture_profile_ref"] != evidence["architecture_profile_ref"]:
        raise ContractError("parallel plan targets a different architecture profile")
    if dispatch["architecture_profile_ref"] != evidence["architecture_profile_ref"] or dispatch["parallel_plan_ref"] != evidence["parallel_plan_ref"]:
        raise ContractError("dispatch architecture/parallel-plan binding mismatch")
    basis = context.workload.get("plan_basis_source_hash", context.workload.get("source_hash"))
    implementation = context.workload.get("implementation_source_hash", context.workload.get("source_hash"))
    if plan["source_hash"] != basis or dispatch["source_hash"] != implementation or dispatch.get("plan_basis_source_hash", dispatch["source_hash"]) != basis:
        raise ContractError("planning source identity differs from workload source")
    if plan["operator"] != context.operator or dispatch["operator"] != context.operator:
        raise ContractError("planning operator differs from route operator")
    groups = {g["group_id"]: g for g in plan["groups"]}
    for group in groups.values():
        if not _supported(profile, group["required_capabilities"]):
            raise ContractError(f"unsupported plan capabilities: {group['group_id']}")
        for memory, required in group["memory_requirements"].items():
            capacity = profile["memory_bytes"][memory]
            if required and (capacity is None or required > capacity):
                raise ContractError(f"{group['group_id']}: unknown or exceeded {memory} capacity")
    if dispatch.get("mode") == UNKEYED_MODE:
        if any(row["group_id"] not in groups for row in dispatch["declared_workloads"]):
            raise ContractError("unkeyed complete call references an unknown parallel group")
        if "tiling_key" in context.workload or "kernel_entry" in context.workload:
            raise ContractError("unkeyed complete call cannot claim a key or single kernel entry")
        selected = select_dispatch(dispatch, context.workload.get("metadata"))
        if (context.workload.get("complete_call_ref") != content_hash(selected)
                or context.workload.get("workload_group") != selected["group_id"]
                or not any(row["metadata_ref"] == context.workload.get("original_metadata_ref")
                    and row["workload"] == context.workload.get("metadata")
                    for row in dispatch["declared_workloads"])):
            raise ContractError("unkeyed workload differs from its declared original metadata/scope")
        return profile, plan, dispatch
    for entry in [*dispatch["entries"], dispatch["fallback"]]:
        if entry["group_id"] not in groups:
            raise ContractError("dispatch references an unknown parallel group")
        if not _supported(profile, entry["required_capabilities"]):
            raise ContractError("dispatch requires unsupported capabilities")
    key = context.workload.get("tiling_key")
    if type(key) is not int or not 0 <= key <= 2**64 - 1:
        raise ContractError("workload tiling_key requires a uint64 integer, not bool or float")
    selected = select_dispatch(dispatch, context.workload.get("metadata"))
    if selected["tiling_key"] != context.workload.get("tiling_key") or selected["group_id"] != context.workload.get("workload_group"):
        raise ContractError("workload dispatch key/group binding mismatch")
    return profile, plan, dispatch


def validate_planning_admission(context, draft):
    """Bind a completed v2 attempt to its output plan and actual implementation.

    Algorithm routing may start without a plan. Episode admission happens after
    the attempt and requires its complete, replayable output bundle. Callers
    retain legacy graphs and NOOP semantics by applying this only to v2 non-NOOP.
    """
    if context.workload.get("source_hash") != draft.source_hashes.baseline:
        raise ContractError("v0002 draft baseline differs from planning source identity")
    _, plan, dispatch = validate_planning_context(context, execution=True)
    if dispatch["source_hash"] != draft.source_hashes.candidate:
        raise ContractError("v0002 planning implementation differs from actual candidate source")
    if draft.transformation_id == "transformation.select_parallel_algorithm":
        if (draft.parameters.get("plan_id") != plan["plan_id"]
                or draft.parameters.get("group_id") != context.workload.get("workload_group")):
            raise ContractError("algorithm selection parameters differ from its output plan/group")


def select_dispatch(plan, workload):
    """Evaluate order-independent host metadata dispatch; ambiguous branches fail."""
    validate_planning_contract("dispatch_plan", plan)
    _validate(WORKLOAD, workload, "workload")
    if plan.get("mode") == UNKEYED_MODE:
        rows = [row for row in plan["declared_workloads"] if row["workload"] == workload]
        if not rows:
            raise ContractError("workload is outside declared complete-call evidence; no verified fallback")
        return {"mode": UNKEYED_MODE, "scope": "declared_workloads_only",
                **{key: deepcopy(rows[0][key]) for key in ("group_id", "role_kernel_names")}}
    metadata = {**workload, "numel": math.prod(workload["shape"])}
    def equal(a, b):
        if isinstance(a, (int, float)) and not isinstance(a, bool) and isinstance(b, (int, float)) and not isinstance(b, bool):
            return a == b
        return type(a) is type(b) and a == b
    def matches(condition):
        actual: Any = metadata
        for part in condition["field"].split("."):
            if isinstance(actual, list) and part.isdigit() and int(part) < len(actual):
                actual = actual[int(part)]
            elif isinstance(actual, dict) and part in actual:
                actual = actual[part]
            else:
                return False
        op, target = condition["op"], condition["value"]
        if op == "eq": return equal(actual, target)
        if op == "ne": return not equal(actual, target)
        if op == "in": return any(equal(actual, t) for t in target)
        if isinstance(actual, bool) or not isinstance(actual, (int, float)): return False
        return {"lt": actual < target, "le": actual <= target, "gt": actual > target, "ge": actual >= target}[op]
    matches_ = [e for e in plan["entries"] if all(matches(c) for c in e["conditions"])]
    if len(matches_) > 1:
        raise ContractError("overlapping dispatch conditions match this workload")
    entry = matches_[0] if matches_ else plan["fallback"]
    return {k: entry[k] for k in ("tiling_key", "kernel_entry", "group_id")} | {"fallback": not matches_}


def planning_mask_reasons(context, transformation):
    if transformation["id"] == "transformation.noop":
        return []
    stage = context.evidence.get("optimization_stage")
    if stage not in STAGES or stage != transformation.get("optimization_stage"):
        return ["optimization_stage_mismatch"]
    try:
        profile, _, _ = validate_planning_context(context, execution=stage == "execution")
        if not _supported(profile, transformation.get("required_capabilities", [])):
            return ["architecture_capability_unavailable"]
    except ContractError as exc:
        return ["planning_precondition: " + str(exc)]
    return []


def verify_unkeyed_task_binding(context, draft, evidence, resolve):
    """Link planning to already fully replayed Task-v5 evidence, without another replay.

    Prebuild adapters own mechanical source derivation. This reader boundary
    additionally binds its exact proof, sources and 20 inputs to the real build
    and complete Task config/registration. It never grants an execution verdict.
    """
    dispatch = context.evidence.get("dispatch_plan", {})
    if dispatch.get("mode") != UNKEYED_MODE or draft.transformation_id == "transformation.noop":
        return
    import json
    from .jsonio import file_hash, to_primitive
    def read(reference):
        path = resolve(reference)
        if file_hash(path) != reference:
            raise ContractError("unkeyed evidence bytes differ from their reference")
        return json.loads(path.read_text())
    def need(condition, message):
        if not condition:
            raise ContractError("unkeyed complete call: " + message)
    validate_planning_admission(context, draft)
    need(resolve is not None, "artifact reader required")
    sources = to_primitive(draft.source_hashes)
    review = read(dispatch["source_review_ref"])
    need(review["operator"] == context.operator and set(review["roles"]) == {"baseline", "candidate"},
         "mechanical source review operator/roles differ")
    for role in ("baseline", "candidate"):
        bundle = read(sources[role])
        need(bundle == {"schema_version": "1.0.0", "files": review["roles"][role]["files"]},
             "mechanical source review differs from actual role source")
        for reference in bundle["files"].values():
            need(file_hash(resolve(reference)) == reference, "role source bytes changed")
    completion = read(evidence.artifacts["measurement_admission"])
    proof = read(completion["proof_ref"])
    config = read(proof["config_ref"])
    registration = read(proof["registration_ref"])
    need(completion["protocol"] == proof["protocol"] == "shared_buffer_msprof_task_window_v5"
         and completion["status"] == "passed" and completion["error"] is None
         and completion["source_hashes"] == proof["source_hashes"] == sources
         and completion["candidate_id"] == draft.candidate_id and config["operator"] == context.operator,
         "actual Task completion/source scope differs")
    identity = registration["identity"]
    need(config["expected_case_ids"] == list(range(1, 21))
         and [row["case_id"] for row in config["cases"]] == list(range(1, 21))
         and set(identity["cases"]) == {str(i) for i in range(1, 21)}, "Task omitted original declared cases")
    receipts = identity["build"]["receipt_refs"]
    need(sum(ref == dispatch["source_review_ref"] for ref in receipts.values()) == 1
         and set(receipts) == set(config["build"]["receipt_files"]), "Task omitted mechanical proof receipt")
    window = read(evidence.artifacts["build_window"])
    need(window["kind"] == "reviewed_candidate_build" and window["receipt_ref"] in receipts.values(),
         "actual reviewed build is absent from Task registration")
    build = read(window["receipt_ref"])
    need(build["status"] == "passed" and build.get("error") is None
         and build["source_review_hash"] == dispatch["source_review_ref"]
         and build["binary"]["sha256"] == identity["build"]["binary_ref"], "Task binary differs from actual build")
    for role in ("baseline", "candidate"):
        need(config["roles"][role]["source_dir"] == review["roles"][role]["path"], "Task role path differs")
    for row, case in zip(dispatch["declared_workloads"], config["cases"], strict=True):
        cid = str(case["case_id"]); registered = identity["cases"][cid]
        metadata = read(row["metadata_ref"])
        need(workload_metadata(context.operator, metadata) == row["workload"], "declared workload differs from original metadata bytes")
        need(metadata["case_id"] == case["case_id"]
             and row["metadata_ref"] in registered["prepared_files"].values(), "Task original metadata differs")
        need(set(registered["prepared_files"]) == set(case["prepared_files"]), "Task prepared input roster differs")
        for role in ("baseline", "candidate"):
            names = row["role_kernel_names"][role]
            need(config["task_profile"]["role_kernel_names"][role][cid] == names
                 and config["roles"][role]["launches_per_operator"][cid] == len(names),
                 "Task changed ordered/repeated kernel sequence or count")


def workload_metadata(operator, value):
    """The five original contiguous-input ABIs; full metadata is retained too."""
    def require(condition, message):
        if not condition: raise ContractError(message)
    require(operator in ("dynamic_quant", "gelu", "group_norm", "gqa", "weight_quant_batch_matmul"), 'unknown original Context operator')
    shape = value['query_shape'] if operator == 'gqa' else (
        value['input_shape'][0] if operator == 'weight_quant_batch_matmul' else value['shape'])
    dtype = value['dtype'][0] if operator == 'weight_quant_batch_matmul' else value['dtype']
    require(isinstance(shape, list) and shape and all(type(n) is int and n > 0 for n in shape)
            and dtype in {'float16', 'bfloat16', 'float32'}, 'invalid original workload shape/dtype')
    attributes = {}
    for name in ('approximate', 'num_groups', 'epsilon', 'scaleValue', 'is_causal', 'm', 'k', 'n'):
        if name in value:
            item = value[name]
            require(isinstance(item, (str, int, float, bool)) and
                    (not isinstance(item, float) or math.isfinite(item)), 'invalid semantic attribute')
            attributes[name] = item
    if operator == 'gqa':
        for name in ('key_shape', 'value_shape'):
            dims = value[name]
            require(isinstance(dims, list) and len(dims) == 4 and
                    all(type(n) is int and n > 0 for n in dims), 'invalid original GQA shape')
            attributes.update({name + '_' + str(i): n for i, n in enumerate(dims)})
    elif operator == 'weight_quant_batch_matmul':
        require(len(value['input_shape']) == len(value['dtype']), 'WQ shape/type roster differs')
        for i, (dims, kind) in enumerate(zip(value['input_shape'], value['dtype'], strict=True)):
            attributes['input_present_' + str(i)] = dims is not None
            if dims is not None:
                require(isinstance(dims, list) and all(type(n) is int and n > 0 for n in dims)
                        and isinstance(kind, str), 'invalid original WQ input')
                attributes['input_dtype_' + str(i)] = kind
                attributes.update({'input_' + str(i) + '_dim_' + str(j): n for j, n in enumerate(dims)})
    return dict(shape=shape, dtype=dtype, layout='ND', attributes=attributes)
