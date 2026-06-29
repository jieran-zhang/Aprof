from __future__ import annotations

import unittest

from aprof.benchmarks.cannbench_adapter import CannBenchAdapter
from aprof.benchmarks.registry import list_manifests, load_injected_ops_manifest, load_reference_ops


class BenchmarkRegistryTests(unittest.TestCase):
    def test_injected_ops_manifest(self) -> None:
        manifest = load_injected_ops_manifest()
        self.assertEqual(manifest.name, "aprof_injected_ops")
        self.assertGreaterEqual(len(manifest.cases), 21)

    def test_reference_ops_manifest(self) -> None:
        manifest = load_reference_ops()
        self.assertEqual(manifest.name, "reference_ops")
        self.assertTrue(any(case.name == "reduce_sum" for case in manifest.cases))

    def test_list_manifests(self) -> None:
        manifests = list_manifests()
        names = {manifest.name for manifest in manifests}
        self.assertIn("aprof_injected_ops", names)
        self.assertIn("reference_ops", names)

    def test_cannbench_adapter_seed(self) -> None:
        adapter = CannBenchAdapter()
        manifest = adapter.to_manifest()
        self.assertEqual(manifest.name, "cannbench")
        self.assertGreaterEqual(len(manifest.cases), 1)


if __name__ == "__main__":
    unittest.main()
