from __future__ import annotations

import unittest

from aprof.core.paths import default_architecture_path
from aprof.metrics.architecture import architecture_to_metric_interface, load_architecture


class ArchitectureLoaderTests(unittest.TestCase):
    def test_load_default_architecture(self) -> None:
        model = load_architecture(default_architecture_path())
        self.assertEqual(model.soc_version, "Ascend910B1")
        self.assertIn("vector", model.components)
        self.assertIn("mte2", model.components)

    def test_metric_interface_contract(self) -> None:
        model = load_architecture(default_architecture_path())
        interface = architecture_to_metric_interface(model)
        self.assertEqual(interface.soc_version, "Ascend910B1")
        self.assertIn("vector", interface.metrics)
        self.assertTrue(interface.metrics["vector"].metric_mapping)


if __name__ == "__main__":
    unittest.main()
