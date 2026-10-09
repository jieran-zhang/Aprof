#!/usr/bin/env python3
"""CPU-only requested-device-byte planner for explicitly audited adapters.

CLI: --audit resource-preflight-audit.json --sizeof sizeof.json --request case.json
Request: {"roles":{"A":"<absolute adapter.asc>","B":"..."},
          "case":{"numel":1024,"dtype":"float32"},"cores":48,
          "buffer_configs":["normal","swapped"]}
sizeof.json: {"entries":[{"adapter_sha256":"...","header_sha256":"...",
 "source_sha256":"...","kernel_sha256":"...","type":"ExpTilingData",
 "bytes":<measured sizeof>,"alignof":<measured alignof>,"size_t_bytes":8,
 "compiler_command":["<actual same build command>"],"compiler_sha256":"...",
 "compiler_version":"...","cmake_parameters":["..."],
 "evidence_path":"<CPU probe output>","evidence_sha256":"..."}]}

The audit is a trusted reviewed allowlist, not an automatically inferred source
contract. All source/header/harness hashes must still match. sizeof entries are
explicit caller-supplied compiler evidence; this tool cannot authenticate a
compiler execution. Never use guessed sizes. Unknown adapters require a new
reviewed audit. Output covers explicit aclrtMalloc requests only; ACL runtime,
allocator overhead, context, modules and events are not bounded by this plan.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def digest(path):
    path = Path(path)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError(f"refuse large metadata/source file: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def positive(value, name, maximum=(1 << 64) - 1):
    if type(value) is not int or not 0 < value <= maximum:
        raise ValueError(f"invalid {name}: positive bounded integer required")
    return value


def role_plan(entry, meta, case, cores):
    """Compute audited formula using explicit target sizeof (no allocation)."""
    for name in ("adapter_sha256", "header_sha256", "kernel_sha256", "source_sha256", "type"):
        if meta.get(name) != entry[name]:
            raise ValueError(f"sizeof metadata mismatch: {name}")
    width = meta.get("size_t_bytes")
    if width not in (4, 8):
        raise ValueError("missing/unsupported target size_t_bytes")
    maximum = (1 << (8 * width)) - 1
    tiling = positive(meta.get("bytes"), "sizeof", maximum)
    alignment = positive(meta.get("alignof"), "alignof", maximum)
    if tiling % alignment or alignment & (alignment - 1):
        raise ValueError("invalid sizeof/alignof combination")
    op = entry["operator"]
    if op not in ("exp", "mish", "sigmoid", "gelu", "masked_scale",
                  "foreach_addcdiv_scalar", "foreach_norm"):
        raise ValueError("unknown audited formula")
    sizes = {"float32": 4, "float16": 2, "bfloat16": 2}
    dtype = case.get("x_dtype" if op == "masked_scale" else "dtype")
    if dtype not in sizes:
        raise ValueError("unsupported input dtype")
    elem = sizes[dtype]
    totals = {"input": 0, "output": 0, "tiling": 0, "workspace": 0}
    # Compact ordered groups preserve layout compatibility without constructing
    # millions of identical chunk records. Each group repeats its pattern.
    groups = []
    exported = 0

    def add(pattern, count=1):
        positive(count, "resource repetition")
        for kind, size in pattern:
            positive(size, "allocation bytes", maximum)
            totals[kind] += size * count
        groups.append({"repeat": count, "pattern": pattern})

    if op.startswith("foreach_"):
        lengths = case.get("lengths")
        if not isinstance(lengths, list) or not lengths:
            raise ValueError("nonempty lengths required")
        lengths = [positive(n, "tensor length") for n in lengths]
        if op == "foreach_norm":
            add([("workspace", positive(cores, "cores", (1 << 63) - 1) * 32)])
            for n in lengths:
                add([("input", n * elem), ("output", 32), ("tiling", tiling)])
            exported = len(lengths) * elem
        else:
            chunk = positive(entry.get("chunk_elements"), "audited chunk size")
            for n in lengths:
                full, tail = divmod(n, chunk)
                for length, count in ((chunk, full), (tail, int(bool(tail)))):
                    if count:
                        b = length * elem
                        add([("input", b)] * 3 + [("output", b), ("tiling", tiling)], count)
            exported = sum(lengths) * elem
    else:
        n = positive(case.get("numel"), "numel")
        pattern = [("input", n * elem)]
        if op == "masked_scale":
            mask = {**sizes, "int8": 1, "uint8": 1}.get(case.get("mask_dtype"))
            if mask is None:
                raise ValueError("unsupported mask dtype")
            pattern.append(("input", n * mask))
        add(pattern + [("output", n * elem), ("tiling", tiling)])
        exported = n * elem
    total = sum(totals.values())
    positive(total, "role requested bytes", maximum)
    return {"operator": op, "requested_bytes_by_kind": totals,
            "requested_bytes": total, "export_bytes": exported,
            "ordered_resource_groups": groups}


def mutable_layout(role):
    # Normalize adjacent equal mutable patterns so differing input/tiling types
    # do not spuriously reject an otherwise identical swap layout.
    out = []
    for group in role["ordered_resource_groups"]:
        pattern = [x for x in group["pattern"] if x[0] in ("output", "workspace")]
        if not pattern:
            continue
        if out and out[-1][1] == pattern:
            out[-1][0] += group["repeat"]
        else:
            out.append([group["repeat"], pattern])
    return out


def plan(audit, sizeof, request):
    if audit.get("version") != "shared_context_resource_audit_v1":
        raise ValueError("unsupported audit schema")
    for item in audit["harness"]:
        if digest(item["path"]) != item["sha256"]:
            raise ValueError("audited harness changed")
    configs = request.get("buffer_configs", ["normal"])
    if not isinstance(configs, list) or not configs or len(set(configs)) != len(configs) or any(c not in ("normal", "swapped") for c in configs):
        raise ValueError("invalid buffer configurations")
    if set(request.get("roles", {})) != {"A", "B"}:
        raise ValueError("exactly roles A and B required")
    roles = {}
    for role in ("A", "B"):
        path = str(Path(request["roles"][role]).resolve())
        entries = [e for e in audit["adapters"] if e["adapter_path"] == path]
        if len(entries) != 1 or entries[0]["role"] != role:
            raise ValueError("adapter absent from reviewed allowlist or wrong role")
        entry = entries[0]
        if digest(path) != entry["adapter_sha256"] or digest(entry["header_path"]) != entry["header_sha256"] or digest(entry["kernel_path"]) != entry["kernel_sha256"]:
            raise ValueError("audited source changed")
        matches = [m for m in sizeof.get("entries", []) if m.get("adapter_sha256") == entry["adapter_sha256"]]
        if len(matches) != 1:
            raise ValueError("exactly one explicit sizeof evidence entry required")
        meta = matches[0]
        if not isinstance(meta.get("compiler_command"), list) or not meta["compiler_command"]:
            raise ValueError("compiler provenance required")
        if not re.fullmatch(r"[0-9a-f]{64}", str(meta.get("compiler_sha256", ""))) or not meta.get("compiler_version") or not meta.get("cmake_parameters"):
            raise ValueError("compiler hash/version and CMake provenance required")
        if not meta.get("evidence_path") or digest(meta["evidence_path"]) != meta.get("evidence_sha256"):
            raise ValueError("sizeof evidence hash mismatch or missing")
        evidence = json.loads(Path(meta["evidence_path"]).read_text())
        for key in ("adapter_sha256", "header_sha256", "kernel_sha256", "source_sha256", "type", "bytes", "alignof", "size_t_bytes"):
            if evidence.get(key) != meta.get(key):
                raise ValueError(f"sizeof evidence contents mismatch: {key}")
        roles[role] = role_plan(entry, meta, request["case"], request.get("cores"))
    if roles["A"]["operator"] != roles["B"]["operator"]:
        raise ValueError("role operators differ")
    if "swapped" in configs and mutable_layout(roles["A"]) != mutable_layout(roles["B"]):
        raise ValueError("buffer swap unsupported: incompatible mutable layout")
    total = sum(r["requested_bytes"] for r in roles.values())
    saved = total if len(configs) > 1 else 0
    return {"version": "shared_context_memory_plan_v1", "roles": roles,
            "steady_requested_bytes": total, "pointer_swap_extra_device_bytes": 0,
            "retained_pool_bytes_during_reprepare": saved,
            "peak_requested_device_bytes": total + saved,
            "scope": "explicit aclrtMalloc requested bytes only",
            "physical_device_memory_bound_available": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("audit", "sizeof", "request"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    try:
        result = plan(*(json.loads(getattr(args, n).read_text()) for n in ("audit", "sizeof", "request")))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f"memory plan refused: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
