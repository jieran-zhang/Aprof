#!/usr/bin/env python3
"""CPU regression against the actual CANN-Bench comparator, never a NPU result."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
import time

REPO = Path(__file__).resolve().parents[2]

ORACLE = '''import json
from pathlib import Path
import torch
from kernel_eval.utils.compare import compare_tensors
p = json.loads(Path('parameters.json').read_text())
def load(name):
    return torch.frombuffer(bytearray(Path(name).read_bytes()), dtype=getattr(torch, p['dtype'])).clone()
result = compare_tensors(load('actual.bin'), load('golden.bin'), dtype=p['dtype'],
    native_output=load('native.bin') if p['native'] else None,
    custom_thresholds=p['custom']).to_dict()
Path('result.json').write_text(json.dumps(result))
raise SystemExit(0 if result['passed'] else 1)
'''


def run(upstream, output, skill_lib):
    sys.path.insert(0, str(skill_lib / "runtime/src"))
    import torch
    from aprof_runtime.original_oracle import MODE, OracleFailure, contract
    from aprof_runtime.unified_timing import file_hash, replay_oracle
    started = time.monotonic()
    output.mkdir(parents=True, exist_ok=False)
    sources = output / "sources"
    sources.mkdir()
    (sources / "oracle.py").write_text(ORACLE)
    package = upstream / "src/kernel_eval"
    for src in [*package.glob("*.py"), *(package / "utils").glob("*.py")]:
        dest = sources / src.relative_to(package.parent)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    environment = {"python": str(Path(sys.executable).resolve()), "sha256": file_hash(sys.executable),
                   "packages": {name: importlib.metadata.version(name) for name in ("torch", "numpy")}}
    cases = [
        ("int32-identical", "int32", [1, -2, 3], [1, -2, 3], None, None, True),
        ("int32-mismatch", "int32", [1, -2, 4], [1, -2, 3], None, None, False),
        ("fp32-identical", "float32", [1, 2], [1, 2], None, None, True),
        ("bf16-identical", "bfloat16", [1, 2], [1, 2], None, None, True),
        ("fp16-saturation", "float16", [float("inf")], [65504], None, None, True),
        ("two-small-errors", "float32", [1e-5, 1e-5, 0, 0], [0, 0, 0, 0], None, None, True),
        ("three-small-errors", "float32", [1e-5, 1e-5, 1e-5, 0], [0, 0, 0, 0], None, None, False),
        ("native-reference", "float32", [1e-5, 1e-5, 1e-5, 0], [0, 0, 0, 0], [1e-5, 1e-5, 0, 0], None, True),
        ("adamw-threshold", "float32", [1e-5, 1e-5, 0, 0], [0, 0, 0, 0], None,
         {"float32": .005, "float16": .01, "bfloat16": .01}, True),
        ("nan-mask-mismatch", "float32", [float("nan"), 1], [0, 1], None, None, False),
    ]
    results = []
    for name, dtype, actual, golden, native, custom, expected in cases:
        root = output / name
        root.mkdir()
        shutil.copytree(sources, root / "bundle")
        bundle = root / "bundle"
        for filename, values in (("actual.bin", actual), ("golden.bin", golden), ("native.bin", native)):
            if values is not None:
                tensor = torch.tensor(values, dtype=getattr(torch, dtype))
                (bundle / filename).write_bytes(tensor.view(torch.uint8).numpy().tobytes())
        (bundle / "parameters.json").write_text(json.dumps({"dtype": dtype, "native": native is not None, "custom": custom}))
        def ref(path):
            return {"path": str(path.relative_to(root)), "sha256": file_hash(path)}
        spec = {"mode": MODE, "entrypoint": "oracle.py", "argv": [],
                "files": {str(p.relative_to(bundle)): ref(p) for p in bundle.rglob("*") if p.is_file() and p.name != "actual.bin"},
                "outputs": {"actual.bin": {"actual": "outputs/actual.bin", "dtype": dtype}},
                "result": {"path": "result.json", "passed_field": "passed"},
                "environment": environment, "timeout_seconds": 60}
        (root / "outputs").mkdir()
        shutil.move(bundle / "actual.bin", root / "outputs/actual.bin")
        output_ref = ref(root / "outputs/actual.bin")
        (root / "output.json").write_text(json.dumps({"files": [output_ref]}))
        receipt = {"status": "passed", "fixture_only": True, "output_sha256": file_hash(root / "output.json"),
                   "oracle_source": spec["files"]["oracle.py"], "replay": spec,
                   "checks": [{"actual": output_ref, "dtype": dtype, "oracle_path": "actual.bin"}]}
        limits = {"mode": MODE, "contract_sha256": contract(spec)}
        (root / "receipt.json").write_text(json.dumps(receipt, indent=2))
        (root / "limits.json").write_text(json.dumps(limits, indent=2))
        failure = None
        try:
            replay_oracle(root, receipt, ref(root / "output.json"), limits, logs=root / "logs")
            passed = True
        except OracleFailure as exc:
            if exc.reason != "numerical_mismatch":
                raise
            failure = str(exc)
            passed = False
        result = {"case": name, "dtype": dtype, "expected": expected, "replayed": passed, "matches": passed == expected, "failure": failure}
        results.append(result)
        (root / "result.json").write_text(json.dumps(result, indent=2))
        assert passed == expected, result
        print(json.dumps(result), flush=True)
    report = {"scope": "CPU original comparator regression; no NPU or performance evidence", "results": results,
              "elapsed_seconds": time.monotonic() - started, "passed": all(r["matches"] for r in results)}
    (output / "results.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skill-lib", type=Path, default=REPO / "skill-libs/graph-base/1.1.0")
    args = parser.parse_args()
    run(args.upstream.resolve(), args.output.resolve(), args.skill_lib.resolve())
