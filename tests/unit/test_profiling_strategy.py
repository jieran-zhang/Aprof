from __future__ import annotations

import unittest
from pathlib import Path

from aprof.agents.profiling.strategy import ProfilingStrategyAgent
from aprof.core.paths import benchmarks_dir


class ProfilingStrategyTests(unittest.TestCase):
    def test_plan_for_tilelen_small(self) -> None:
        case = benchmarks_dir() / "aprof_injected_ops" / "swi_glu" / "inject_tilelen_small"
        if not case.exists():
            self.skipTest("injected benchmark case not present")
        plan = ProfilingStrategyAgent().plan(case)
        self.assertIn("run.sh", plan.command[1])
        self.assertIn("--tile-length", plan.command)
        self.assertIn("16", plan.command)


if __name__ == "__main__":
    unittest.main()
