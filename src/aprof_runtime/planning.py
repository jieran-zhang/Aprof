"""Strict, hash-bound planning artifacts; legacy episode wire formats stay intact.

Validation establishes declared identities, applicability and capacity, not the
truth of an algorithm or hardware measurement. Evidence remains auditable CAS.
"""
from __future__ import annotations

from copy import deepcopy
import math
import re
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
SCHEMAS = {"architecture_profile": ARCHITECTURE_PROFILE, "parallel_plan": PARALLEL_PLAN,
           "dispatch_plan": DISPATCH_PLAN}


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


def architecture_id(soc_name):
    """Never infer A3/910C from the ambiguous SocVersion enum or arch 2201."""
    name = (soc_name or "").lower()
    if re.fullmatch(r"ascend910_93[a-z0-9_]*", name) or name.startswith("ascend910c"):
        return "910c"
    if re.fullmatch(r"ascend910b[1-4][a-z0-9_]*", name):
        return "910b"
    if name.startswith("ascend950") or name.startswith("ascend910_95"):
        return "950"
    return "unknown"


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
    for entry in [*dispatch["entries"], dispatch["fallback"]]:
        if entry["group_id"] not in groups:
            raise ContractError("dispatch references an unknown parallel group")
        if not _supported(profile, entry["required_capabilities"]):
            raise ContractError("dispatch requires unsupported capabilities")
    selected = select_dispatch(dispatch, context.workload.get("metadata"))
    if selected["tiling_key"] != context.workload.get("tiling_key") or selected["group_id"] != context.workload.get("workload_group"):
        raise ContractError("workload dispatch key/group binding mismatch")
    return profile, plan, dispatch


def select_dispatch(plan, workload):
    """Evaluate order-independent host metadata dispatch; ambiguous branches fail."""
    validate_planning_contract("dispatch_plan", plan)
    _validate(WORKLOAD, workload, "workload")
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
