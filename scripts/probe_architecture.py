#!/usr/bin/env python3
"""Query ACL SoC identity and SDK PlatformAscendC capabilities without benchmarks.

--soc-name queries SDK tables only. --device explicitly initializes ACL briefly,
and must be run in an exclusive device window. Unknown values remain null.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aprof_runtime.jsonio import content_hash, file_hash, canonical_json
from aprof_runtime.planning import MEMORIES, architecture_id, validate_planning_contract

CPP = r'''#include <csignal>
#include <iostream>
#include "utils/tiling/platform/platform_ascendc.h"
int main(int argc, char **argv) {
  if (argc != 2) return 2;
  auto *p = platform_ascendc::PlatformAscendCManager::GetInstance(argv[1]);
  if (!p) return 3;
  std::cout << "{\"npu_arch\":" << static_cast<unsigned>(p->GetCurNpuArch())
    << ",\"core_counts\":{\"aic\":" << p->GetCoreNumAic()
    << ",\"aiv\":" << p->GetCoreNumAiv() << "},\"memory_bytes\":{";
  const char *names[] = {"UB","L1","L0_A","L0_B","L0_C","L2","BT"};
  using M=platform_ascendc::CoreMemType;
  M kinds[] = {M::UB,M::L1,M::L0_A,M::L0_B,M::L0_C,M::L2,M::BT};
  for (int i=0;i<7;++i) { uint64_t size=0; p->GetCoreMemSize(kinds[i],size);
    if(i) std::cout << ","; std::cout << "\"" << names[i] << "\":" << size;
  }
  std::cout << "}}\n";
}
'''


def device_soc(sdk, device):
    library = ctypes.CDLL(str(sdk / "lib64/libascendcl.so"))
    library.aclInit.argtypes = [ctypes.c_char_p]
    library.aclrtSetDevice.argtypes = [ctypes.c_int32]
    library.aclrtGetSocName.restype = ctypes.c_char_p
    library.aclrtResetDevice.argtypes = [ctypes.c_int32]
    init = library.aclInit(None)
    if init != 0:
        raise RuntimeError(f"aclInit failed: {init}")
    selected = False
    try:
        code = library.aclrtSetDevice(device)
        if code != 0: raise RuntimeError(f"aclrtSetDevice failed: {code}")
        selected = True
        name = library.aclrtGetSocName()
        if not name: raise RuntimeError("aclrtGetSocName returned null")
        visible, queries = {}, []
        get_info = getattr(library, 'aclrtGetDeviceInfo', None)
        if get_info is not None:
            get_info.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.POINTER(ctypes.c_int64)]
        # acl_rt.h: CUBE_CORE_NUM=102, VECTOR_CORE_NUM=201. Do not substitute
        # PlatformAscendC table counts for a failed runtime visibility query.
        for core, attribute in (('aic', 102), ('aiv', 201)):
            count = ctypes.c_int64(0)
            code = get_info(device, attribute, ctypes.byref(count)) if get_info is not None else None
            visible[core] = count.value if code == 0 and count.value > 0 else None
            queries.append(dict(core=core, attribute=attribute, exit_status=code, value=visible[core]))
        return dict(soc_name=name.decode(), visible_core_counts=visible, device_info_queries=queries)
    finally:
        reset = library.aclrtResetDevice(device) if selected else 0
        final = library.aclFinalize()
        if reset or final:
            raise RuntimeError(f"ACL cleanup failed: reset={reset}, finalize={final}")


def compiler_identity(sdk, artifacts):
    """Read compiler identity on CPU; this does not attest any target feature."""
    choices = [sdk / 'compiler/ccec_compiler/bin/bisheng', sdk.parent / 'tools/bisheng_compiler/bin/bisheng']
    found = shutil.which('bisheng')
    if found: choices.append(Path(found))
    binary = next((p.resolve() for p in choices if p.is_file()), None)
    record = dict(path=str(binary) if binary else None, argv=[str(binary), '--version'] if binary else [],
                  hardware_executed=False, status='unknown', version=None)
    if binary:
        try:
            result = subprocess.run([str(binary), '--version'], capture_output=True, text=True, timeout=15)
            version = (result.stdout + result.stderr).strip()
            record.update(status='verified' if result.returncode == 0 and version else 'error',
                          exit_status=result.returncode, version=version or None, binary_sha256=file_hash(binary))
        except (OSError, subprocess.TimeoutExpired) as error:
            record.update(status='error', error=str(error))
    path = artifacts / 'compiler-identity.json'
    path.write_text(canonical_json(record))
    return {key: record[key] for key in ('status', 'path', 'version')} | {'evidence_refs': [file_hash(path)]}


def build_profile(raw, sdk_version, provenance):
    facts = raw.get("platform", {})
    cores = {key: facts.get("core_counts", {}).get(key) or None for key in ("aic", "aiv")}
    memories = {key: facts.get("memory_bytes", {}).get(key) or None for key in MEMORIES}
    capabilities = {}
    for capability, core in (("vector", "aiv"), ("cube", "aic")):
        capabilities[capability] = {"status": "supported" if cores[core] else "unknown",
            "basis": "PlatformAscendC core count; API-specific compile support is separate",
            "evidence_refs": [provenance["raw_probe_ref"]]}
    # Instruction families cannot be enabled by a product marketing name alone.
    for capability in ("simt", "ssbuffer", "mix_kernel", "datacopypad"):
        capabilities[capability] = {"status": "unknown", "basis": "requires a target SDK/compiler feature probe",
                                    "evidence_refs": []}
    profile = {"schema_version": "1.0.0", "hardware_fingerprint": content_hash(raw),
        "architecture_id": architecture_id(raw.get("soc_name")), "soc_name": raw.get("soc_name"),
        "npu_arch": facts.get("npu_arch") or None, "sdk_version": sdk_version,
        "probe_kind": raw["probe_kind"], "device_id": raw.get("device_id"),
        "core_counts": cores, "memory_bytes": memories, "capabilities": capabilities,
        "visible_core_counts": {key: raw.get('visible_core_counts', {}).get(key) or None for key in ('aic', 'aiv')},
        "compiler": raw.get('compiler', {'status': 'unknown', 'path': None, 'version': None, 'evidence_refs': []}),
        "provenance": provenance, "limitations": [
            "PlatformAscendC capacities describe the selected SDK SoC; no throughput or contention measurements were taken.",
            "core_counts are SDK capacities; only visible_core_counts attest successful aclrtGetDeviceInfo queries.",
            "Feature-specific APIs, compiler flags and process allocation limits require independent validation.",
            *raw.get("errors", [])]}
    return validate_planning_contract("architecture_profile", profile)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, default=Path(os.environ.get("ASCEND_HOME_PATH", "/usr/local/Ascend/cann-9.0.0/aarch64-linux")))
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--device", type=int)
    source.add_argument("--soc-name")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sdk = args.sdk.resolve()
    if not (sdk / "include/acl").is_dir() and (sdk / (platform.machine() + "-linux")).is_dir():
        sdk = sdk / (platform.machine() + "-linux")
    output = args.output.resolve()
    if output.exists(): raise FileExistsError(output)
    artifacts = output.parent / (output.stem + "-probe")
    artifacts.mkdir(parents=True, exist_ok=False)
    (artifacts / "probe_architecture.py").write_bytes(Path(__file__).read_bytes())
    header = sdk / "asc/include/utils/tiling/platform/platform_ascendc.h"
    if header.is_file():
        (artifacts / "platform_ascendc.h").write_bytes(header.read_bytes())
    acl_header = sdk / 'include/acl/acl_rt.h'
    if acl_header.is_file(): (artifacts / 'acl_rt.h').write_bytes(acl_header.read_bytes())
    raw = {"probe_kind": "device" if args.device is not None else "sdk_soc",
           "device_id": args.device, "soc_name": args.soc_name, "sdk": str(sdk), "errors": []}
    raw['compiler'] = compiler_identity(sdk, artifacts)
    raw['visible_core_counts'] = {'aic': None, 'aiv': None}
    if acl_header.is_file(): raw['acl_header_ref'] = file_hash(artifacts / 'acl_rt.h')
    try:
        if args.device is not None:
            raw.update(device_soc(sdk, args.device))
        if not re.fullmatch(r"[A-Za-z0-9_]+", raw["soc_name"] or ""):
            raise RuntimeError("missing or invalid SDK SoC name")
        cpp = artifacts / "platform_probe.cpp"
        cpp.write_text(CPP)
        binary = artifacts / "platform_probe"
        command = ["g++", "-std=c++17", str(cpp), "-I"+str(sdk/"asc/include"),
                   "-I"+str(sdk/"include"), "-L"+str(sdk/"lib64"), "-Wl,-rpath,"+str(sdk/"lib64"),
                   "-ltiling_api", "-lplatform", "-lunified_dlog", "-ldl", "-o", str(binary)]
        built = subprocess.run(command, capture_output=True, text=True, timeout=60)
        (artifacts / "compile.log").write_text(built.stdout + built.stderr)
        raw["compile"] = {"argv": command, "exit_status": built.returncode,
                          "log_ref": file_hash(artifacts / "compile.log")}
        if built.returncode: raise RuntimeError("PlatformAscendC probe compilation failed; see compile.log")
        queried = subprocess.run([str(binary), raw["soc_name"]], capture_output=True, text=True, timeout=30)
        (artifacts / "platform.log").write_text(queried.stdout + queried.stderr)
        raw["platform_execution"] = {"exit_status": queried.returncode, "log_ref": file_hash(artifacts / "platform.log")}
        if queried.returncode: raise RuntimeError("PlatformAscendC probe failed; see platform.log")
        raw["platform"] = json.loads(queried.stdout.strip().splitlines()[-1])
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        raw["errors"].append(str(error))
        if raw["soc_name"] is None: raw["probe_kind"] = "unavailable"
    raw_path = artifacts / "raw.json"
    raw_path.write_text(canonical_json(raw))
    sdk_version = next((p.name.removeprefix("cann-") for p in (sdk, *sdk.parents) if p.name.startswith("cann-")), "unknown")
    profile = build_profile(raw, sdk_version, {"probe_source_ref": file_hash(artifacts / "probe_architecture.py"),
        "raw_probe_ref": file_hash(raw_path), "sdk_header_ref": file_hash(artifacts / "platform_ascendc.h") if header.is_file() else None,
        "acl_header_ref": file_hash(artifacts / 'acl_rt.h') if acl_header.is_file() else None})
    output.write_text(canonical_json(profile))
    print(json.dumps({"profile": str(output), "profile_ref": content_hash(profile),
                      "architecture_id": profile["architecture_id"], "soc_name": profile["soc_name"],
                      "core_counts": profile["core_counts"], "visible_core_counts": profile['visible_core_counts'],
                      "compiler_status": profile['compiler']['status'], "errors": raw["errors"]}))


if __name__ == "__main__":
    main()
