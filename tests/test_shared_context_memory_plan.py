"""CPU arithmetic/contract tests; sizeof values below are synthetic fixtures."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location(
    "memory_plan", Path(__file__).resolve().parents[1] / "scripts/shared_context_memory_plan.py")
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)
collector_spec = importlib.util.spec_from_file_location(
    "collect_sizeof", Path(__file__).resolve().parents[1] / "scripts/shared_context_collect_sizeof.py")
collector = importlib.util.module_from_spec(collector_spec)
collector_spec.loader.exec_module(collector)


class MemoryPlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        entries, metadata = [], []
        for role in "AB":
            paths = {}
            for kind in ("adapter", "header", "kernel"):
                p = root / (role + kind)
                p.write_text(role + kind)
                paths[kind + "_path"] = str(p)
                paths[kind + "_sha256"] = planner.digest(p)
            entry = {**paths, "source_sha256": "a" * 64, "type": "FixtureType",
                     "operator": "exp", "role": role}
            evidence = root / (role + "evidence")
            evidence.write_text(json.dumps({**entry, "bytes": 40, "alignof": 8,
                                            "size_t_bytes": 8}))
            meta = {**entry, "bytes": 40, "alignof": 8, "size_t_bytes": 8,
                    "compiler_command": ["synthetic-test-only"],
                    "compiler_sha256": "b" * 64, "compiler_version": "test",
                    "cmake_parameters": ["synthetic-test-only"],
                    "evidence_path": str(evidence), "evidence_sha256": planner.digest(evidence)}
            entries.append(entry)
            metadata.append(meta)
        self.audit = {"version": "shared_context_resource_audit_v1", "adapters": entries, "harness": []}
        self.metadata = {"entries": metadata}
        self.request = {"roles": {e["role"]: e["adapter_path"] for e in entries},
                        "case": {"numel": 10, "dtype": "float32"}, "cores": 48}

    def run_plan(self):
        return planner.plan(self.audit, self.metadata, self.request)

    def test_normal_and_pool_reprepare_peak(self):
        self.assertEqual(self.run_plan()["peak_requested_device_bytes"], 240)
        self.request["buffer_configs"] = ["normal", "swapped"]
        result = self.run_plan()
        self.assertEqual(result["peak_requested_device_bytes"], 480)
        self.assertEqual(result["pointer_swap_extra_device_bytes"], 0)
        self.assertEqual(result["retained_pool_bytes_during_reprepare"], 240)

    def test_norm_allocated_output_differs_from_export(self):
        for e in self.audit["adapters"]:
            e["operator"] = "foreach_norm"
        self.request["case"] = {"lengths": [10, 20], "dtype": "float16"}
        role = self.run_plan()["roles"]["A"]
        self.assertEqual(role["requested_bytes_by_kind"],
                         {"input": 60, "output": 64, "tiling": 80, "workspace": 1536})
        self.assertEqual(role["export_bytes"], 4)

    def test_chunks_accumulate_and_tail_is_separate(self):
        for e in self.audit["adapters"]:
            e.update(operator="foreach_addcdiv_scalar", chunk_elements=8)
        self.request["case"] = {"lengths": [17, 3], "dtype": "float32"}
        role = self.run_plan()["roles"]["A"]
        self.assertEqual(role["requested_bytes_by_kind"],
                         {"input": 240, "output": 80, "tiling": 160, "workspace": 0})

    def test_metadata_missing_or_source_changed_refuses(self):
        saved = copy.deepcopy(self.metadata)
        self.metadata = {"entries": []}
        with self.assertRaisesRegex(ValueError, "sizeof evidence"):
            self.run_plan()
        self.metadata = saved
        Path(self.audit["adapters"][0]["header_path"]).write_text("changed")
        with self.assertRaisesRegex(ValueError, "source changed"):
            self.run_plan()

    def test_unknown_formula_and_overflow_refuse(self):
        self.audit["adapters"][0]["operator"] = "unknown"
        with self.assertRaisesRegex(ValueError, "unknown audited"):
            self.run_plan()
        self.audit["adapters"][0]["operator"] = "exp"
        self.request["case"]["numel"] = 1 << 63
        with self.assertRaisesRegex(ValueError, "allocation bytes"):
            self.run_plan()

    def test_swap_rejects_different_chunk_layout(self):
        for e, chunk in zip(self.audit["adapters"], (8, 4)):
            e.update(operator="foreach_addcdiv_scalar", chunk_elements=chunk)
        self.request["case"] = {"lengths": [12], "dtype": "float32"}
        self.request["buffer_configs"] = ["swapped"]
        with self.assertRaisesRegex(ValueError, "incompatible mutable"):
            self.run_plan()

    def test_sizeof_evidence_must_match_claimed_size(self):
        self.metadata["entries"][0]["bytes"] = 48
        with self.assertRaisesRegex(ValueError, "contents mismatch"):
            self.run_plan()

    def test_collector_preserves_probe_and_compiler_evidence(self):
        root = Path(self.tmp.name)
        compiler = root / "synthetic-compiler"
        compiler.write_text("not executable; subprocess mocked")
        source = root / "probe.asc"
        source.write_text("synthetic fixture")
        observed = {k: self.metadata["entries"][0][k] for k in
                    ("adapter_sha256", "header_sha256", "kernel_sha256", "source_sha256",
                     "type", "bytes", "alignof", "size_t_bytes")}
        target = {**observed, "source": str(source), "target": "probe"}
        (root / "probe_manifest.json").write_text(json.dumps({"targets": [target]}))
        (root / "compile_commands.json").write_text(json.dumps([
            {"file": str(source), "arguments": [str(compiler), "--npu-arch=dav-2201", "-std=c++17"]}]))
        output = root / "collected.json"
        argv = ["collect", "--probe-dir", str(root), "--build-dir", str(root),
                "--compiler", str(compiler), "--compiler-sha256", "c" * 64,
                "--cmake-parameters-json", '["-S", "synthetic"]', "--output", str(output)]
        with patch("sys.argv", argv), patch.object(collector.subprocess, "run", side_effect=[
                SimpleNamespace(stdout="synthetic compiler version"),
                SimpleNamespace(stdout=json.dumps(observed) + "\n")]), patch("builtins.print"):
            collector.main()
        entry = json.loads(output.read_text())["entries"][0]
        self.assertEqual(entry["bytes"], 40)
        self.assertEqual(entry["compiler_version"], "synthetic compiler version")
        self.assertEqual(planner.digest(entry["evidence_path"]), entry["evidence_sha256"])

    def test_make_recipe_is_derived_and_does_not_invent_std(self):
        root = Path(self.tmp.name)
        source = root / "probe.asc"
        target = {"target": "probe", "source": str(source)}
        directory = root / "CMakeFiles/probe.dir"
        directory.mkdir(parents=True)
        (directory / "flags.make").write_text(
            "ASC_DEFINES =\nASC_INCLUDES = -I/include\nASC_FLAGS = --npu-arch=dav-2201\n")
        (directory / "build.make").write_text(
            "\t/compiler/bisheng $(ASC_DEFINES) $(ASC_INCLUDES) -fPIC $(ASC_FLAGS) -o probe.o -c --asc-aicore-lang " + str(source) + "\n")
        command, provenance = collector.compile_command(root, target)
        self.assertEqual(command[0], "/compiler/bisheng")
        self.assertIn("--npu-arch=dav-2201", command)
        self.assertFalse(any(x.startswith("-std=") for x in command))
        self.assertEqual(provenance["kind"], "derived_from_cmake_makefiles")
        self.assertEqual(len(provenance["evidence"]), 2)
        (directory / "flags.make").write_text(
            "ASC_DEFINES = $(UNKNOWN)\nASC_INCLUDES =\nASC_FLAGS = --npu-arch=dav-2201\n")
        with self.assertRaisesRegex(ValueError, "unsupported Make variable"):
            collector.compile_command(root, target)


if __name__ == "__main__":
    unittest.main()
