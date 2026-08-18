#!/usr/bin/env python3
"""Generate, validate, and install AProf capability metadata from one registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Iterable


REGISTRY_PATH = Path("skillgraph/registry.json")
MARKETPLACE_PATH = Path(".claude-plugin/marketplace.json")
PLUGIN_MANIFEST_PATH = Path(
    "plugins/aprof-performance-workflow/.claude-plugin/plugin.json"
)
CODEX_MARKETPLACE_PATH = Path(".agents/plugins/marketplace.json")
CODEX_PLUGIN_MANIFEST_PATH = Path(
    "plugins/aprof-performance-workflow/.codex-plugin/plugin.json"
)
CODEX_SKILLS_PATH = Path("plugins/aprof-performance-workflow/skills")
INIT_PATH = Path("plugins/aprof-performance-workflow/init.sh")
ROLE_ORDER = ("core", "optional_adapters", "benchmark_only")
FRONTMATTER_NAME = re.compile(r"^name:\s*([^#\n]+?)\s*$", re.MULTILINE)
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
CODEX_CACHEBUSTER = re.compile(r"^[0-9A-Za-z.-]+$")
BUNDLE_IGNORED_DIRS = {"__pycache__"}


class RegistryError(ValueError):
    """Raised when registry content is incomplete or inconsistent."""


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def _safe_component(value: Any, label: str) -> str:
    """Return a registry name that cannot escape a single destination component."""
    if not isinstance(value, str) or SAFE_COMPONENT.fullmatch(value) is None:
        raise RegistryError(
            f"{label} must be one safe path component containing only "
            "letters, digits, '.', '_' or '-': {value!r}"
        )
    if value in {".", ".."}:
        raise RegistryError(f"{label} must not be '.' or '..'")
    return value


def _repo_path(repo_root: Path, relative: Any, label: str) -> Path:
    """Resolve an untrusted registry path while keeping it inside the repository."""
    if not isinstance(relative, str) or not relative:
        raise RegistryError(f"{label} must be a non-empty repository-relative path")
    path = Path(relative)
    if path.is_absolute() or "\\" in relative or any(part in {"", ".", ".."} for part in path.parts):
        raise RegistryError(f"{label} must be a normalized repository-relative path: {relative!r}")
    root = repo_root.resolve()
    try:
        resolved = (root / path).resolve()
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise RegistryError(f"{label} resolves outside repository root: {relative!r}") from exc
    return resolved


def load_registry(repo_root: Path) -> dict[str, Any]:
    path = _repo_path(repo_root, REGISTRY_PATH.as_posix(), "registry path")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RegistryError(f"registry not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RegistryError(f"invalid JSON in {path}: {exc}") from exc
    if data.get("schema_version") != 1:
        raise RegistryError("registry schema_version must be 1")
    return data


def capabilities(registry: dict[str, Any], roles: Iterable[str] = ROLE_ORDER):
    for role in roles:
        for item in registry.get("capabilities", {}).get(role, []):
            yield role, item


def read_frontmatter_name(skill_file: Path) -> str:
    text = skill_file.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise RegistryError(f"missing YAML frontmatter: {skill_file}")
    end = text.find("\n---", 4)
    if end < 0:
        raise RegistryError(f"unterminated YAML frontmatter: {skill_file}")
    match = FRONTMATTER_NAME.search(text[4:end])
    if not match:
        raise RegistryError(f"frontmatter name missing: {skill_file}")
    return match.group(1).strip().strip('"\'')


def validate_registry(repo_root: Path, registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    seen_names: dict[str, str] = {}
    seen_sources: set[str] = set()
    seen_legacy_names: set[str] = set()
    seen_support_names: set[str] = set()

    for role, item in capabilities(registry):
        name = item.get("name")
        source = item.get("source")
        if not name or not source:
            errors.append(f"{role} capability requires name and source: {item!r}")
            continue
        try:
            name = _safe_component(name, f"{role} capability name")
            source_path = _repo_path(repo_root, source, f"{role} capability source")
        except RegistryError as exc:
            errors.append(str(exc))
            continue
        if name in seen_names:
            errors.append(f"duplicate capability name {name!r} in {role} and {seen_names[name]}")
        if name in seen_legacy_names:
            errors.append(f"canonical capability name collides with a legacy name: {name}")
        if source in seen_sources:
            errors.append(f"duplicate capability source {source!r}")
        seen_names[name] = role
        seen_sources.add(source)
        for legacy_name in item.get("legacy_names", []):
            try:
                legacy_name = _safe_component(legacy_name, f"legacy name for {name}")
            except RegistryError as exc:
                errors.append(str(exc))
                continue
            if legacy_name == name:
                errors.append(f"legacy name repeats canonical name for {source}: {name}")
            if legacy_name in seen_names:
                errors.append(f"legacy name collides with a canonical capability: {legacy_name}")
            if legacy_name in seen_legacy_names:
                errors.append(f"duplicate legacy capability name: {legacy_name}")
            seen_legacy_names.add(legacy_name)
        skill_file = source_path / "SKILL.md"
        if not skill_file.is_file():
            errors.append(f"missing SKILL.md for {name}: {skill_file}")
            continue
        try:
            actual_name = read_frontmatter_name(skill_file)
        except (OSError, RegistryError) as exc:
            errors.append(str(exc))
            continue
        if actual_name != name:
            errors.append(
                f"registry/frontmatter name mismatch for {source}: "
                f"registry={name!r}, frontmatter={actual_name!r}"
            )

    for item in registry.get("support_skills", []):
        name = item.get("name")
        source = item.get("source")
        if not name or not source:
            errors.append(f"support skill requires name and source: {item!r}")
            continue
        try:
            name = _safe_component(name, "support skill name")
            source_path = _repo_path(repo_root, source, f"support skill {name} source")
        except RegistryError as exc:
            errors.append(str(exc))
            continue
        if name in seen_names:
            errors.append(
                f"duplicate bundled skill name collides with a capability: {name}"
            )
        if name in seen_support_names:
            errors.append(f"duplicate support skill name: {name}")
        seen_support_names.add(name)
        skill_file = source_path / "SKILL.md"
        if not skill_file.is_file():
            # A missing optional submodule is an install-time warning, not registry drift.
            continue
        try:
            actual_name = read_frontmatter_name(skill_file)
        except (OSError, RegistryError) as exc:
            errors.append(str(exc))
            continue
        if actual_name != name:
            errors.append(
                f"registry/frontmatter name mismatch for {source}: "
                f"registry={name!r}, frontmatter={actual_name!r}"
            )

    for agent in registry.get("cursor_agents", []):
        name = agent.get("name")
        source = agent.get("source")
        if not name or not source:
            errors.append(f"cursor agent requires name and source: {agent!r}")
            continue
        try:
            _safe_component(name, "cursor agent name")
            source_path = _repo_path(repo_root, source, f"cursor agent {name} source")
        except RegistryError as exc:
            errors.append(str(exc))
            continue
        if not source_path.is_file():
            errors.append(f"missing cursor agent source: {source}")

    plugin = registry.get("workflow_plugin", {})
    library = registry.get("library", {})
    benchmark_package = registry.get("benchmark_package", {})
    dependencies = plugin.get("dependencies", [])
    for label, value in (
        ("library.name", library.get("name")),
        ("benchmark_package.name", benchmark_package.get("name")),
        ("workflow_plugin.name", plugin.get("name")),
    ):
        try:
            _safe_component(value, label)
        except RegistryError as exc:
            errors.append(str(exc))
    if not isinstance(dependencies, list):
        errors.append("workflow_plugin.dependencies must be a list")
        dependencies = []
    for index, dependency in enumerate(dependencies):
        try:
            _safe_component(dependency, f"workflow_plugin.dependencies[{index}]")
        except RegistryError as exc:
            errors.append(str(exc))
    plugin_root = _repo_path(
        repo_root, "plugins/aprof-performance-workflow", "workflow plugin root"
    )
    for source in plugin.get("agents", []):
        try:
            source_path = _repo_path(repo_root, source, "workflow plugin agent source")
            source_path.relative_to(plugin_root)
        except (RegistryError, ValueError) as exc:
            errors.append(f"workflow plugin agent must resolve inside plugin root: {source!r}: {exc}")
            continue
        if not source_path.is_file():
            errors.append(f"missing workflow plugin agent: {source}")
    if library.get("name") not in dependencies:
        errors.append("workflow_plugin.dependencies must include library.name")
    if not benchmark_package.get("name"):
        errors.append("benchmark_package.name is required")
    elif benchmark_package["name"] in dependencies:
        errors.append("workflow_plugin must not depend on benchmark_package")
    if seen_names.get("ascendc-aprof-workflow") != "core":
        errors.append("ascendc-aprof-workflow must be a core capability")
    if seen_names.get("ascendc-aprof-inject-problems") != "benchmark_only":
        errors.append("ascendc-aprof-inject-problems must remain benchmark_only")
    if plugin.get("name") != Path("plugins/aprof-performance-workflow").name:
        errors.append("workflow_plugin.name must match its plugin directory")

    codex = plugin.get("codex", {})
    required_codex_strings = (
        "marketplace_name",
        "marketplace_display_name",
        "display_name",
        "short_description",
        "long_description",
        "developer_name",
        "category",
    )
    for key in required_codex_strings:
        if not isinstance(codex.get(key), str) or not codex[key].strip():
            errors.append(f"workflow_plugin.codex.{key} must be a non-empty string")
    try:
        _safe_component(codex.get("marketplace_name"), "Codex marketplace name")
    except RegistryError as exc:
        errors.append(str(exc))
    for key in ("capabilities", "default_prompt"):
        values = codex.get(key)
        if not isinstance(values, list) or not values or not all(
            isinstance(value, str) and value.strip() for value in values
        ):
            errors.append(
                f"workflow_plugin.codex.{key} must be a non-empty string list"
            )
    prompts = codex.get("default_prompt", [])
    if isinstance(prompts, list):
        if len(prompts) > 3:
            errors.append("workflow_plugin.codex.default_prompt supports at most 3 prompts")
        for index, prompt in enumerate(prompts):
            if isinstance(prompt, str) and len(prompt) > 128:
                errors.append(
                    f"workflow_plugin.codex.default_prompt[{index}] exceeds 128 characters"
                )
    return errors


def _marketplace_skill_path(source: str) -> str:
    prefix = "skills/aprof/"
    if not source.startswith(prefix):
        raise RegistryError(f"marketplace skill must live under {prefix}: {source}")
    return "./" + source[len(prefix) :]


def render_marketplace(registry: dict[str, Any]) -> str:
    library = registry["library"]
    benchmark_package = registry["benchmark_package"]
    workflow = registry["workflow_plugin"]
    skill_paths = [
        _marketplace_skill_path(item["source"])
        for _, item in capabilities(registry, ("core", "optional_adapters"))
    ]
    benchmark_skill_paths = [
        _marketplace_skill_path(item["source"])
        for _, item in capabilities(registry, ("benchmark_only",))
    ]
    data = {
        "name": "aprof",
        "owner": {"name": "AProf", "url": "https://gitcode.com/cann/Aprof"},
        "plugins": [
            {
                "name": library["name"],
                "description": library["description"],
                "source": "./skills/aprof",
                "strict": False,
                "version": library["version"],
                "author": {"name": "AProf"},
                "keywords": [
                    "aprof",
                    "ascendc",
                    "skillgraph",
                    "profiling",
                    "optimization",
                ],
                "category": "skills",
                "skills": skill_paths,
            },
            {
                "name": benchmark_package["name"],
                "description": benchmark_package["description"],
                "source": "./skills/aprof",
                "strict": False,
                "version": benchmark_package["version"],
                "author": {"name": "AProf"},
                "keywords": ["aprof", "ascendc", "benchmark", "injection"],
                "category": "skills",
                "skills": benchmark_skill_paths,
            },
            {
                "name": workflow["name"],
                "source": "./plugins/aprof-performance-workflow",
                "description": workflow["description"],
                "version": workflow["version"],
                "author": {"name": "AProf"},
                "keywords": [
                    "aprof",
                    "ascendc",
                    "skillgraph",
                    "workflow",
                    "agent",
                ],
                "category": "development",
                "dependencies": workflow["dependencies"],
            },
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def render_plugin_manifest(registry: dict[str, Any]) -> str:
    workflow = registry["workflow_plugin"]
    plugin_root = Path("plugins/aprof-performance-workflow")
    agent_paths = [
        "./" + Path(path).relative_to(plugin_root).as_posix()
        for path in workflow["agents"]
    ]
    data = {
        "name": workflow["name"],
        "description": workflow["description"],
        "version": workflow["version"],
        "author": {"name": "AProf"},
        "homepage": "https://gitcode.com/cann/Aprof",
        "repository": "https://gitcode.com/cann/Aprof",
        "license": "CANN-2.0",
        "dependencies": workflow["dependencies"],
        "agents": agent_paths,
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def render_codex_marketplace(registry: dict[str, Any]) -> str:
    """Render the repo-local Codex marketplace entry for the workflow plugin."""
    workflow = registry["workflow_plugin"]
    codex = workflow["codex"]
    data = {
        "name": codex["marketplace_name"],
        "interface": {"displayName": codex["marketplace_display_name"]},
        "plugins": [
            {
                "name": workflow["name"],
                "source": {
                    "source": "local",
                    "path": f"./plugins/{workflow['name']}",
                },
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": codex["category"],
            }
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def render_codex_plugin_manifest(
    registry: dict[str, Any], version: str | None = None
) -> str:
    """Render a Codex-native manifest without Claude-only dependency fields."""
    workflow = registry["workflow_plugin"]
    codex = workflow["codex"]
    data = {
        "name": workflow["name"],
        "version": version or workflow["version"],
        "description": workflow["description"],
        "author": {"name": "AProf"},
        "homepage": "https://gitcode.com/cann/Aprof",
        "repository": "https://gitcode.com/cann/Aprof",
        "license": "CANN-2.0",
        "keywords": [
            "aprof",
            "ascendc",
            "skillgraph",
            "profiling",
            "optimization",
        ],
        "skills": "./skills/",
        "interface": {
            "displayName": codex["display_name"],
            "shortDescription": codex["short_description"],
            "longDescription": codex["long_description"],
            "developerName": codex["developer_name"],
            "category": codex["category"],
            "capabilities": codex["capabilities"],
            "websiteURL": "https://gitcode.com/cann/Aprof",
            "defaultPrompt": codex["default_prompt"],
        },
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def codex_bundle_entries(
    repo_root: Path, registry: dict[str, Any]
) -> list[tuple[str, Path]]:
    """Return available canonical sources bundled into the Codex plugin.

    The production bundle intentionally contains only core AProf capabilities
    and registry-listed support knowledge. Optional execution adapters and
    benchmark-generation skills remain separate systems.
    """
    entries: list[tuple[str, Path]] = []
    for _, item in capabilities(registry, ("core",)):
        entries.append(
            (
                item["name"],
                _repo_path(repo_root, item["source"], f"core skill {item['name']}"),
            )
        )
    for item in registry.get("support_skills", []):
        source = _repo_path(
            repo_root, item["source"], f"support skill {item['name']} source"
        )
        if (source / "SKILL.md").is_file():
            entries.append((item["name"], source))
    return entries


def _bundle_source_files(source: Path) -> dict[Path, Path]:
    """Map portable relative bundle paths to source files."""
    files: dict[Path, Path] = {}
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part in BUNDLE_IGNORED_DIRS for part in relative.parts):
            continue
        if path.name.endswith((".pyc", ".pyo")):
            continue
        if path.is_symlink():
            raise RegistryError(f"Codex skill bundle does not allow symlinks: {path}")
        if path.is_file():
            files[relative] = path
    return files


def _configured_codex_bundle_names(registry: dict[str, Any]) -> set[str]:
    return {
        item["name"]
        for _, item in capabilities(registry, ("core",))
    } | {item["name"] for item in registry.get("support_skills", [])}


def check_codex_skill_bundle(
    repo_root: Path, registry: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    bundle_root = _repo_path(
        repo_root, CODEX_SKILLS_PATH.as_posix(), "Codex bundled skills root"
    )
    configured_names = _configured_codex_bundle_names(registry)
    if not bundle_root.is_dir():
        return [f"generated Codex skill bundle missing: {CODEX_SKILLS_PATH}"]

    actual_names = {
        path.name for path in bundle_root.iterdir() if path.is_dir() and not path.is_symlink()
    }
    unexpected = actual_names - configured_names
    missing = configured_names - actual_names
    if unexpected:
        errors.append(f"unexpected Codex bundled skills: {sorted(unexpected)}")
    if missing:
        errors.append(f"missing Codex bundled skills: {sorted(missing)}")
    for path in bundle_root.iterdir():
        if path.is_symlink():
            errors.append(f"Codex skill bundle contains symlink: {path}")
        elif not path.is_dir():
            errors.append(f"Codex skills root contains non-skill entry: {path}")

    available = dict(codex_bundle_entries(repo_root, registry))
    for name in sorted(configured_names):
        destination = bundle_root / name
        if not (destination / "SKILL.md").is_file():
            errors.append(f"bundled skill is missing SKILL.md: {destination}")
            continue
        source = available.get(name)
        if source is None:
            # Support submodules may be absent in a consumer checkout. The
            # already materialized bundle remains usable and self-contained.
            continue
        expected_files = _bundle_source_files(source)
        actual_files: dict[Path, Path] = {}
        for path in sorted(destination.rglob("*")):
            relative = path.relative_to(destination)
            if path.is_symlink():
                errors.append(f"Codex skill bundle contains symlink: {path}")
            elif path.is_file():
                actual_files[relative] = path
        if set(actual_files) != set(expected_files):
            errors.append(f"bundled skill file set is stale: {name}")
            continue
        for relative, source_file in expected_files.items():
            try:
                if actual_files[relative].read_bytes() != source_file.read_bytes():
                    errors.append(f"bundled skill file is stale: {name}/{relative}")
            except OSError as exc:
                errors.append(f"cannot compare bundled skill {name}/{relative}: {exc}")
    return errors


def write_codex_skill_bundle(repo_root: Path, registry: dict[str, Any]) -> None:
    bundle_root = _repo_path(
        repo_root, CODEX_SKILLS_PATH.as_posix(), "Codex bundled skills root"
    )
    bundle_root.mkdir(parents=True, exist_ok=True)
    configured_names = _configured_codex_bundle_names(registry)
    available = dict(codex_bundle_entries(repo_root, registry))

    for name in sorted(configured_names):
        destination = bundle_root / name
        source = available.get(name)
        if source is None:
            if not (destination / "SKILL.md").is_file():
                raise RegistryError(
                    f"support skill source and materialized bundle are both missing: {name}"
                )
            continue
        # Validate before removing the old generated copy, so a source symlink
        # cannot escape into the archived plugin.
        _bundle_source_files(source)
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_dir():
                destination.unlink()
            else:
                shutil.rmtree(destination)
        shutil.copytree(
            source,
            destination,
            symlinks=False,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )

    for path in bundle_root.iterdir():
        if path.name in configured_names:
            continue
        if path.is_symlink() or path.is_file():
            path.unlink()
        else:
            shutil.rmtree(path)


def render_init_script() -> str:
    return '''#!/usr/bin/env bash
# Install registry-selected AProf capabilities into Cursor project config.
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PLUGIN_ROOT/../.." && pwd)"

exec python3 "$REPO_ROOT/scripts/sync_aprof_registry.py" \\
  --repo-root "$REPO_ROOT" install "$@"
'''


def rendered_artifacts(
    registry: dict[str, Any], *, codex_version: str | None = None
) -> dict[Path, str]:
    return {
        MARKETPLACE_PATH: render_marketplace(registry),
        PLUGIN_MANIFEST_PATH: render_plugin_manifest(registry),
        CODEX_MARKETPLACE_PATH: render_codex_marketplace(registry),
        CODEX_PLUGIN_MANIFEST_PATH: render_codex_plugin_manifest(
            registry, codex_version
        ),
        INIT_PATH: render_init_script(),
    }


def _valid_codex_manifest_version(actual: Any, base: str) -> bool:
    if actual == base:
        return True
    prefix = base + "+codex."
    return (
        isinstance(actual, str)
        and actual.startswith(prefix)
        and CODEX_CACHEBUSTER.fullmatch(actual[len(prefix) :]) is not None
    )


def check_artifacts(repo_root: Path, registry: dict[str, Any]) -> list[str]:
    errors = validate_registry(repo_root, registry)
    for relative_path, expected in rendered_artifacts(registry).items():
        path = _repo_path(repo_root, relative_path.as_posix(), "generated artifact")
        try:
            actual = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            errors.append(f"generated artifact missing: {relative_path}")
            continue
        if relative_path == CODEX_PLUGIN_MANIFEST_PATH:
            try:
                actual_data = json.loads(actual)
                expected_data = json.loads(expected)
            except json.JSONDecodeError as exc:
                errors.append(f"invalid generated Codex manifest: {exc}")
                continue
            base_version = registry["workflow_plugin"]["version"]
            if not _valid_codex_manifest_version(
                actual_data.get("version"), base_version
            ):
                errors.append(
                    "generated Codex manifest has an invalid version; expected "
                    f"{base_version!r} or one +codex.<cachebuster> suffix"
                )
                continue
            actual_data["version"] = base_version
            if actual_data != expected_data:
                errors.append(
                    f"generated artifact is stale: {relative_path} "
                    "(run scripts/sync_aprof_registry.py write)"
                )
            continue
        if actual != expected:
            errors.append(
                f"generated artifact is stale: {relative_path} "
                "(run scripts/sync_aprof_registry.py write)"
            )
    errors.extend(check_codex_skill_bundle(repo_root, registry))
    return errors


def write_artifacts(repo_root: Path, registry: dict[str, Any]) -> None:
    errors = validate_registry(repo_root, registry)
    if errors:
        raise RegistryError("\n".join(errors))
    codex_version = registry["workflow_plugin"]["version"]
    codex_manifest = _repo_path(
        repo_root,
        CODEX_PLUGIN_MANIFEST_PATH.as_posix(),
        "generated Codex manifest",
    )
    try:
        existing_version = json.loads(codex_manifest.read_text(encoding="utf-8")).get(
            "version"
        )
        if _valid_codex_manifest_version(existing_version, codex_version):
            codex_version = existing_version
    except (FileNotFoundError, json.JSONDecodeError, AttributeError):
        pass

    artifacts = rendered_artifacts(registry, codex_version=codex_version)
    # Materialize the portable archive content before marketplace registration.
    # A restricted checkout may intentionally make `.agents/` read-only while
    # still allowing the plugin itself to be regenerated and validated.
    write_codex_skill_bundle(repo_root, registry)
    ordered_paths = [
        path for path in artifacts if path != CODEX_MARKETPLACE_PATH
    ] + [CODEX_MARKETPLACE_PATH]
    for relative_path in ordered_paths:
        content = artifacts[relative_path]
        path = _repo_path(repo_root, relative_path.as_posix(), "generated artifact")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _repo_path(repo_root, INIT_PATH.as_posix(), "installer artifact").chmod(0o755)


def _replace_symlink(source: Path, destination: Path) -> None:
    if destination.is_symlink() or destination.exists():
        if destination.is_dir() and not destination.is_symlink():
            raise RegistryError(f"refusing to replace directory: {destination}")
        destination.unlink()
    destination.symlink_to(source.resolve(), target_is_directory=source.is_dir())


def _remove_unselected_managed_symlink(destination: Path) -> None:
    """Remove a previously managed optional link without touching user directories."""
    if destination.is_symlink():
        destination.unlink()
        print(f"unlinked unselected optional capability {destination}")
    elif destination.exists():
        print(f"warn: unselected capability path is user-managed; leaving it: {destination}")


def install_cursor(
    repo_root: Path,
    registry: dict[str, Any],
    *,
    with_remote: bool,
    with_benchmark_tools: bool,
) -> None:
    errors = validate_registry(repo_root, registry)
    if errors:
        raise RegistryError("\n".join(errors))

    cursor_dir = _repo_path(repo_root, ".cursor", "Cursor install root")
    skills_dir = _repo_path(repo_root, ".cursor/skills", "Cursor skills target")
    agents_dir = _repo_path(repo_root, ".cursor/agents", "Cursor agents target")
    skills_dir.mkdir(parents=True, exist_ok=True)
    agents_dir.mkdir(parents=True, exist_ok=True)

    roles = ["core"]
    if with_remote:
        roles.append("optional_adapters")
    if with_benchmark_tools:
        roles.append("benchmark_only")

    selected_names = {item["name"] for _, item in capabilities(registry, roles)}
    for _, item in capabilities(registry):
        for legacy_name in item.get("legacy_names", []):
            _remove_unselected_managed_symlink(skills_dir / legacy_name)
    for _, item in capabilities(registry, ("optional_adapters", "benchmark_only")):
        if item["name"] not in selected_names:
            _remove_unselected_managed_symlink(skills_dir / item["name"])

    installed_skills: list[str] = []
    for _, item in capabilities(registry, roles):
        source = _repo_path(repo_root, item["source"], f"capability {item['name']} source")
        _replace_symlink(source, skills_dir / item["name"])
        installed_skills.append(item["name"])
        print(f"linked {skills_dir / item['name']} -> {source}")

    for item in registry.get("support_skills", []):
        source = _repo_path(repo_root, item["source"], f"support skill {item['name']} source")
        if not (source / "SKILL.md").is_file():
            print(f"warn: support skill missing (submodule not initialized): {source}")
            continue
        _replace_symlink(source, skills_dir / item["name"])
        installed_skills.append(item["name"])
        print(f"linked {skills_dir / item['name']} -> {source}")

    installed_agents: list[str] = []
    for item in registry.get("cursor_agents", []):
        source = _repo_path(repo_root, item["source"], f"cursor agent {item['name']} source")
        _replace_symlink(source, agents_dir / item["name"])
        installed_agents.append(item["name"])
        print(f"linked {agents_dir / item['name']} -> {source}")

    manifest = {
        "plugin": registry["workflow_plugin"]["name"],
        "registry_schema_version": registry["schema_version"],
        "registry": REGISTRY_PATH.as_posix(),
        "options": {
            "with_remote": with_remote,
            "with_benchmark_tools": with_benchmark_tools,
        },
        "skills": installed_skills,
        "agents": installed_agents,
    }
    manifest_path = cursor_dir / "aprof-performance-workflow-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Done. Invoke /ascendc-aprof-workflow in Cursor.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", type=Path, default=repo_root_from_script(), help=argparse.SUPPRESS
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="validate registry and generated artifacts")
    subparsers.add_parser("write", help="regenerate manifests and installer wrapper")
    install = subparsers.add_parser("install", help="install registry-selected Cursor links")
    install.add_argument(
        "--with-remote", action="store_true", help="install the optional remote adapter"
    )
    install.add_argument(
        "--with-benchmark-tools",
        action="store_true",
        help="install benchmark-only problem injection tools",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    try:
        registry = load_registry(repo_root)
        if args.command == "check":
            errors = check_artifacts(repo_root, registry)
            if errors:
                print("\n".join(f"error: {error}" for error in errors), file=sys.stderr)
                return 1
            print("AProf registry and generated artifacts are consistent.")
        elif args.command == "write":
            write_artifacts(repo_root, registry)
            print(
                "Regenerated AProf marketplaces, plugin manifests, Codex skill "
                "bundle, and installer."
            )
        else:
            install_cursor(
                repo_root,
                registry,
                with_remote=args.with_remote,
                with_benchmark_tools=args.with_benchmark_tools,
            )
    except (OSError, RegistryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
