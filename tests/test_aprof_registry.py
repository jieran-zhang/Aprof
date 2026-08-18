from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/sync_aprof_registry.py"
SPEC = importlib.util.spec_from_file_location("sync_aprof_registry", SCRIPT)
assert SPEC and SPEC.loader
registry_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(registry_tool)


class AProfRegistryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = registry_tool.load_registry(REPO_ROOT)

    def test_registry_matches_skill_frontmatter(self) -> None:
        self.assertEqual([], registry_tool.validate_registry(REPO_ROOT, self.registry))

    def test_generated_install_artifacts_are_current(self) -> None:
        self.assertEqual([], registry_tool.check_artifacts(REPO_ROOT, self.registry))

    def test_roles_keep_training_and_benchmark_boundaries_explicit(self) -> None:
        capabilities = self.registry["capabilities"]
        core_names = {item["name"] for item in capabilities["core"]}
        optional_names = {
            item["name"] for item in capabilities["optional_adapters"]
        }
        benchmark_names = {item["name"] for item in capabilities["benchmark_only"]}

        self.assertIn("ascendc-aprof-workflow", core_names)
        self.assertIn("ascendc-aprof-diagnosis", core_names)
        self.assertIn("ascendc-aprof-profiling", core_names)
        self.assertIn("ascendc-aprof-optimization", core_names)
        self.assertIn("ascendc-kernel-direct-invoke", core_names)
        self.assertEqual({"ascendc-remote-kernel-deploy"}, optional_names)
        self.assertEqual({"ascendc-aprof-inject-problems"}, benchmark_names)
        self.assertTrue(core_names.isdisjoint(optional_names | benchmark_names))

        legacy_names = {
            legacy_name
            for item in capabilities["core"]
            for legacy_name in item.get("legacy_names", [])
        }
        self.assertEqual(
            {
                "aprof-ascendc-diagnosis",
                "aprof-ascendc-profiling",
                "aprof-ascendc-optimization",
                "aprof-ascendc-kernel-direct-invoke",
            },
            legacy_names,
        )

    def test_marketplace_and_plugin_dependencies_come_from_registry(self) -> None:
        marketplace = registry_tool.json.loads(
            registry_tool.render_marketplace(self.registry)
        )
        manifest = registry_tool.json.loads(
            registry_tool.render_plugin_manifest(self.registry)
        )
        workflow_entry = next(
            item
            for item in marketplace["plugins"]
            if item["name"] == "aprof-performance-workflow"
        )
        expected = self.registry["workflow_plugin"]["dependencies"]
        self.assertEqual(expected, workflow_entry["dependencies"])
        self.assertEqual(expected, manifest["dependencies"])
        benchmark_package = self.registry["benchmark_package"]["name"]
        self.assertNotIn(benchmark_package, expected)

        core_package = next(
            item
            for item in marketplace["plugins"]
            if item["name"] == self.registry["library"]["name"]
        )
        benchmark_entry = next(
            item
            for item in marketplace["plugins"]
            if item["name"] == benchmark_package
        )
        injection_path = "./benchmark/ascendc-aprof-inject-problems"
        self.assertNotIn(injection_path, core_package["skills"])
        self.assertEqual([injection_path], benchmark_entry["skills"])

    def test_codex_marketplace_has_one_installable_self_contained_plugin(self) -> None:
        marketplace = registry_tool.json.loads(
            registry_tool.render_codex_marketplace(self.registry)
        )
        workflow = self.registry["workflow_plugin"]

        self.assertEqual("aprof", marketplace["name"])
        self.assertTrue(marketplace["interface"]["displayName"])
        self.assertEqual(1, len(marketplace["plugins"]))

        entry = marketplace["plugins"][0]
        self.assertEqual(workflow["name"], entry["name"])
        self.assertEqual(
            {
                "source": "local",
                "path": f"./plugins/{workflow['name']}",
            },
            entry["source"],
        )
        self.assertEqual(
            {
                "installation": "AVAILABLE",
                "authentication": "ON_INSTALL",
            },
            entry["policy"],
        )
        self.assertIsInstance(entry["category"], str)
        self.assertTrue(entry["category"].strip())

        # Codex ingests a self-contained plugin archive. Claude package
        # dependencies and the independent benchmark package must not leak into
        # this marketplace entry.
        self.assertNotIn("dependencies", entry)
        self.assertNotIn("skills", entry)
        self.assertNotIn(self.registry["library"]["name"], {entry["name"]})
        self.assertNotIn(self.registry["benchmark_package"]["name"], {entry["name"]})

    def test_codex_plugin_manifest_matches_ingestion_contract(self) -> None:
        workflow = self.registry["workflow_plugin"]
        manifest = registry_tool.json.loads(
            registry_tool.render_codex_plugin_manifest(self.registry)
        )

        self.assertEqual(workflow["name"], manifest["name"])
        self.assertEqual(workflow["version"], manifest["version"])
        self.assertEqual(workflow["description"], manifest["description"])
        self.assertEqual({"name": "AProf"}, manifest["author"])
        self.assertEqual("./skills/", manifest["skills"])

        # These are valid in the existing Claude manifest, but rejected by the
        # Codex plugin validator. Codex skills are physically bundled instead.
        for unsupported in ("dependencies", "agents", "hooks"):
            self.assertNotIn(unsupported, manifest)

        interface = manifest["interface"]
        for field in (
            "displayName",
            "shortDescription",
            "longDescription",
            "developerName",
            "category",
        ):
            self.assertIsInstance(interface[field], str)
            self.assertTrue(interface[field].strip(), field)
        self.assertIsInstance(interface["capabilities"], list)
        self.assertTrue(
            all(isinstance(item, str) and item.strip() for item in interface["capabilities"])
        )
        prompt = interface["defaultPrompt"]
        self.assertTrue(
            (isinstance(prompt, str) and prompt.strip())
            or (
                isinstance(prompt, list)
                and prompt
                and all(isinstance(item, str) and item.strip() for item in prompt)
            )
        )

        overridden = registry_tool.json.loads(
            registry_tool.render_codex_plugin_manifest(
                self.registry, version="0.2.0+codex.test"
            )
        )
        self.assertEqual("0.2.0+codex.test", overridden["version"])
        self.assertEqual(workflow["version"], self.registry["workflow_plugin"]["version"])

    def test_codex_skill_bundle_is_complete_and_excludes_non_core_roles(self) -> None:
        skills_root = (
            REPO_ROOT / "plugins/aprof-performance-workflow/skills"
        )
        self.assertTrue(skills_root.is_dir())

        core = self.registry["capabilities"]["core"]
        support = self.registry["support_skills"]
        expected_items = {item["name"]: item for item in [*core, *support]}
        actual_names = {
            path.name
            for path in skills_root.iterdir()
            if path.is_dir() and not path.name.startswith(".")
        }
        self.assertEqual(set(expected_items), actual_names)

        excluded_names = {
            item["name"]
            for role in ("optional_adapters", "benchmark_only")
            for item in self.registry["capabilities"][role]
        }
        legacy_names = {
            legacy
            for item in core
            for legacy in item.get("legacy_names", [])
        }
        self.assertTrue(actual_names.isdisjoint(excluded_names))
        self.assertTrue(actual_names.isdisjoint(legacy_names))

        def file_map(root: Path) -> dict[str, bytes]:
            result: dict[str, bytes] = {}
            for path in sorted(root.rglob("*")):
                relative = path.relative_to(root)
                if "__pycache__" in relative.parts or path.suffix == ".pyc":
                    continue
                if path.is_file():
                    result[relative.as_posix()] = path.read_bytes()
            return result

        symlinks = [path for path in skills_root.rglob("*") if path.is_symlink()]
        self.assertEqual([], symlinks, "Codex plugin bundles must not depend on repo symlinks")
        self.assertEqual([], list(skills_root.rglob("__pycache__")))
        self.assertEqual([], list(skills_root.rglob("*.pyc")))

        for name, item in expected_items.items():
            with self.subTest(skill=name):
                source = REPO_ROOT / item["source"]
                bundled = skills_root / name
                self.assertEqual(file_map(source), file_map(bundled))

    def test_codex_renderers_are_deterministic(self) -> None:
        self.assertEqual(
            registry_tool.render_codex_marketplace(self.registry),
            registry_tool.render_codex_marketplace(copy.deepcopy(self.registry)),
        )
        self.assertEqual(
            registry_tool.render_codex_plugin_manifest(self.registry),
            registry_tool.render_codex_plugin_manifest(copy.deepcopy(self.registry)),
        )

    def test_codex_bundle_names_cannot_collide(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["support_skills"][0]["name"] = registry["capabilities"]["core"][0][
            "name"
        ]
        errors = registry_tool.validate_registry(REPO_ROOT, registry)
        self.assertTrue(any("duplicate" in error and "name" in error for error in errors), errors)

    def test_unselected_optional_cleanup_only_removes_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            managed = root / "managed"
            managed.symlink_to(target, target_is_directory=True)
            registry_tool._remove_unselected_managed_symlink(managed)
            self.assertFalse(managed.is_symlink())

            user_managed = root / "user-managed"
            user_managed.mkdir()
            registry_tool._remove_unselected_managed_symlink(user_managed)
            self.assertTrue(user_managed.is_dir())

    def test_install_names_are_single_safe_path_components(self) -> None:
        for field, malicious in (("name", "../escape"), ("name", "nested/escape")):
            registry = copy.deepcopy(self.registry)
            registry["capabilities"]["core"][0][field] = malicious
            errors = registry_tool.validate_registry(REPO_ROOT, registry)
            self.assertTrue(
                any("one safe path component" in error for error in errors), errors
            )

        registry = copy.deepcopy(self.registry)
        registry["capabilities"]["core"][1]["legacy_names"] = ["../legacy"]
        errors = registry_tool.validate_registry(REPO_ROOT, registry)
        self.assertTrue(any("one safe path component" in error for error in errors), errors)

        registry = copy.deepcopy(self.registry)
        registry["cursor_agents"][0]["name"] = "../../agent.md"
        errors = registry_tool.validate_registry(REPO_ROOT, registry)
        self.assertTrue(any("one safe path component" in error for error in errors), errors)

    def test_registry_sources_cannot_escape_repository(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["capabilities"]["core"][0]["source"] = "../outside"
        errors = registry_tool.validate_registry(REPO_ROOT, registry)
        self.assertTrue(any("normalized repository-relative" in error for error in errors), errors)

        registry = copy.deepcopy(self.registry)
        registry["workflow_plugin"]["agents"][0] = "/tmp/outside-agent.md"
        errors = registry_tool.validate_registry(REPO_ROOT, registry)
        self.assertTrue(any("workflow plugin agent" in error for error in errors), errors)

    def test_resolved_symlinks_cannot_escape_repository_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            (root / ".cursor").symlink_to(Path(outside), target_is_directory=True)
            with self.assertRaisesRegex(registry_tool.RegistryError, "outside repository root"):
                registry_tool._repo_path(root, ".cursor/skills", "Cursor skills target")


if __name__ == "__main__":
    unittest.main()
