"""Run the portable static checks and standard-library refresh in the guide."""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "plugins/aprof-performance-workflow/quickstart.md"


def test_quickstart_static_checks_use_reproducible_current_graph():
    section = GUIDE.read_text().split("## Verify the static library\n", 1)[1].split("## Invoke", 1)[0]
    commands = re.search(r"```bash\n(.*?)\n```", section, re.S).group(1).splitlines()
    assert any("compile_graph_v2.py --check" in command for command in commands)
    assert not any("compile_seed_graph.py" in command for command in commands)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
    for command in commands:
        argv = shlex.split(command)
        argv[:1] = [sys.executable] if argv[0] == "python3" else [sys.executable, "-m", "aprof_runtime.cli"]
        subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, check=True)


def test_documented_cache_refresh_is_portable_and_does_not_stack_versions(tmp_path):
    guide = GUIDE.read_text()
    assert "/root/.codex" not in guide
    assert "plugin-creator/scripts" not in guide
    code = re.search(r"python3 - <<'PY'\n(.*?)\nPY", guide, re.S).group(1)
    registry = tmp_path / "skillgraph/registry.json"
    registry.parent.mkdir()
    registry.write_text(json.dumps({"workflow_plugin": {"version": "0.3.0"}}))
    manifest = tmp_path / "plugins/aprof-performance-workflow/.codex-plugin/plugin.json"
    manifest.parent.mkdir(parents=True)
    original = {"name": "aprof-performance-workflow", "version": "0.3.0+codex.old", "skills": "./skills/"}
    manifest.write_text(json.dumps(original))
    versions = []
    for _ in range(2):
        subprocess.run([sys.executable, "-B", "-c", code], cwd=tmp_path, check=True)
        updated = json.loads(manifest.read_text())
        versions.append(updated["version"])
        assert re.fullmatch(r"0\.3\.0\+codex\.[0-9a-f]{32}", updated["version"])
        assert {**updated, "version": original["version"]} == original
    assert versions[0] != versions[1]
