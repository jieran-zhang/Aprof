"""验证治理后的安装入口和真实 Agent 注册，完全不访问 NPU。"""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

PACKAGE = Path(__file__).resolve().parents[2]


def run_tool(package, tool, *args):
    return subprocess.run([sys.executable, str(package / "tools" / tool), *args],
                          text=True, capture_output=True)


def test_install_exposes_complete_workflow_and_is_idempotent(tmp_path):
    target = tmp_path / "host-skills"
    result = run_tool(PACKAGE, "install.py", "--allow-unsealed", "--skills-dir", str(target))
    assert result.returncode == 0, result.stderr
    registry = json.loads((PACKAGE / "skills/registry.json").read_text())
    skills = registry["capabilities"]["core"] + registry["support_skills"]
    assert {path.name for path in target.iterdir()} == {entry["name"] for entry in skills}
    for entry in skills:
        assert (target / entry["name"]).resolve() == PACKAGE / entry["source"]
    source = (target / "ascendc-aprof-coordinator/SKILL.md").resolve()
    workflow = source.parent / "../../workflows/aprof-performance-workflow.md"
    assert workflow.is_file()
    for agent in registry["workflow_plugin"]["agents"]:
        assert (PACKAGE / agent).is_file()
    again = run_tool(PACKAGE, "install.py", "--allow-unsealed", "--skills-dir", str(target))
    assert again.returncode == 0, again.stderr


def test_removed_remote_option_cannot_install_anything(tmp_path):
    target = tmp_path / "host-skills"
    result = run_tool(PACKAGE, "install.py", "--allow-unsealed", "--with-remote",
                      "--skills-dir", str(target))
    assert result.returncode != 0
    assert not target.exists()


@pytest.mark.parametrize("damage", ["plugin_path", "role_identity", "missing_contract"])
def test_release_rejects_broken_workflow_entry(tmp_path, damage):
    package = tmp_path / "package"
    shutil.copytree(PACKAGE, package,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".runtime-env"))
    if damage == "plugin_path":
        path = package / ".claude-plugin/plugin.json"
        value = json.loads(path.read_text())
        value["agents"][0] = "./agents/removed-wrapper.md"
        path.write_text(json.dumps(value))
        expected = "plugin agents differ"
    elif damage == "role_identity":
        path = package / "workflows/agents/diagnosis.md"
        path.write_text(path.read_text().replace("name: aprof-diagnosis-agent", "name: stale-agent"))
        expected = "agent frontmatter name mismatch"
    else:
        (package / "workflows/contracts/candidate.md").unlink()
        expected = "incomplete package"
    result = run_tool(package, "release.py", "--allow-unsealed")
    assert result.returncode != 0
    assert expected in result.stderr
