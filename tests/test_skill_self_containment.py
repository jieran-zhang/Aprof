from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("self_contained_registry", ROOT / "scripts/sync_aprof_registry.py")
assert SPEC and SPEC.loader
registry_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(registry_tool)


class SkillSelfContainmentTest(unittest.TestCase):
    def test_checkout_without_third_party_rebuilds_and_installs_all_skills(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("skills", "plugins"):
                shutil.copytree(ROOT / name, root / name,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            (root / "skillgraph").mkdir()
            shutil.copy2(ROOT / "skillgraph/registry.json", root / "skillgraph/registry.json")
            self.assertFalse((root / "third_party").exists())
            shutil.rmtree(root / registry_tool.CODEX_SKILLS_PATH)
            registry = registry_tool.load_registry(root)
            registry_tool.write_artifacts(root, registry)
            self.assertEqual([], registry_tool.check_artifacts(root, registry))
            with contextlib.redirect_stdout(io.StringIO()):
                registry_tool.install_cursor(root, registry, with_remote=True, with_benchmark_tools=False)
            expected = {entry["name"] for entry in registry["support_skills"]}
            expected.update(entry["name"] for role, entry in registry_tool.capabilities(registry)
                            if role != "benchmark_only")
            for name in expected:
                self.assertTrue((root / ".cursor/skills" / name / "SKILL.md").is_file(), name)
            # Exercise the packaged tools without hardware or the source tree.
            bundle = root / registry_tool.CODEX_SKILLS_PATH
            commands = [
                ["bash", str(bundle / "ops-profiling/scripts/msprof_profile_run.sh"), "--help"],
                [sys.executable, str(bundle / "ops-profiling/scripts/msprof_perf_summary.py"), "--help"],
                [sys.executable, str(bundle / "ops-profiling/scripts/perf_summary.py"), "--help"],
                [sys.executable, str(bundle / "ops-simulator/scripts/trace_bubble_analyzer.py"), "--help"],
            ]
            for command in commands:
                result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=30)
                self.assertEqual(0, result.returncode, (command, result.stderr))

    def test_every_portable_markdown_link_resolves_within_bundle(self):
        bundle = (ROOT / registry_tool.CODEX_SKILLS_PATH).resolve()
        for path in bundle.rglob("*.md"):
            for target in re.findall(r"\]\(([^\s)]+)\)", path.read_text()):
                if "://" in target or target.startswith(("#", "<")):
                    continue
                relative = target.split("#", 1)[0]
                if not relative:
                    continue
                resolved = (path.parent / relative).resolve()
                self.assertTrue(resolved.is_relative_to(bundle), (path, target))
                self.assertTrue(resolved.is_file(), (path, target))

    def test_registry_rejects_external_or_missing_support_sources(self):
        registry = registry_tool.load_registry(ROOT)
        external = copy.deepcopy(registry)
        external["support_skills"][0]["source"] = "third_party/unavailable-skill"
        errors = registry_tool.validate_registry(ROOT, external)
        self.assertTrue(any("owned by AProf" in error for error in errors), errors)
        missing = copy.deepcopy(registry)
        missing["support_skills"][0]["source"] = "skills/aprof/support/missing-required-source"
        errors = registry_tool.validate_registry(ROOT, missing)
        self.assertTrue(any("missing required local support skill" in error for error in errors), errors)

    def test_source_and_bundle_have_no_runtime_external_skill_paths(self):
        roots = [ROOT / "skills/aprof", ROOT / "plugins/aprof-performance-workflow"]
        for root in roots:
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix not in {".md", ".py", ".sh", ".json"}:
                    continue
                if path.name == "NOTICE.md":
                    continue  # An upstream attribution is not an execution dependency.
                content = path.read_text()
                self.assertNotIn("third_party/cannbot-skills", content, path)
                self.assertNotRegex(content, r"(?:skill:|`/)(?:ops-precision-standard|ascendc-direct-invoke-template|ascendc-regbase-best-practice)\b", path)

    def test_declared_agent_skills_are_present_and_collectors_retain_licenses(self):
        registry = registry_tool.load_registry(ROOT)
        names = {entry["name"] for _, entry in registry_tool.capabilities(registry)}
        names.update(entry["name"] for entry in registry["support_skills"])
        for entry in registry["cursor_agents"]:
            text = (ROOT / entry["source"]).read_text()
            match = re.search(r"^skills:\n((?:  - [^\n]+\n)+)", text, re.MULTILINE)
            if match:
                requested = {line.strip()[2:] for line in match.group(1).splitlines()}
                self.assertTrue(requested <= names, (entry["name"], requested - names))
        for name in ("ops-profiling", "ops-simulator"):
            directory = ROOT / "skills/aprof/support" / name
            self.assertTrue((directory / "LICENSE").is_file())
            self.assertTrue((directory / "NOTICE.md").is_file())
        self.assertIn("Apache License", (ROOT / "skills/aprof/support/ops-simulator/LICENSE.Apache-2.0").read_text())


if __name__ == "__main__":
    unittest.main()
