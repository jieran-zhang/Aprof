"""The Task profiler process has a fixed environment and a replayable receipt."""

import json
from pathlib import Path
import sys

import pytest
from aprof_runtime import __version__

if __version__ != "0.2.2":
    pytest.skip("select graph-base/0.5.1", allow_module_level=True)

from aprof_runtime.store import EpisodeStore

SCRIPTS = Path(__file__).resolve().parents[2] / "skill-libs/graph-base/0.5.1/skills/ascendc-aprof-profiling/scripts"
sys.path.insert(0, str(SCRIPTS))
from profile_capture import run


def test_task_process_environment_is_explicit_and_default_receipt_is_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv("APROF_INHERITED_SECRET", "unfrozen")
    command = [sys.executable, "-c", "import json,os; print(json.dumps({k:v for k,v in os.environ.items() if k.startswith('APROF_')},sort_keys=True))"]
    with EpisodeStore(tmp_path / "objects.db") as store:
        result = run(command, tmp_path, tmp_path / "task", 5, store,
                     environment={"APROF_SHARED_REPEAT": "100"})
        assert json.loads(result["text"].strip()) == {"APROF_SHARED_REPEAT": "100"}
        assert result["environment"] == {"APROF_SHARED_REPEAT": "100"}
        assert result["timeout_seconds"] == 5
        assert type(result["pid"]) is int and result["pid"] > 0
        original = json.loads(store.verify_artifact(result["log_hash"]).read_text())
        assert original == {key: value for key, value in result.items()
                            if key not in {"log_hash", "text"}}
        default = run(command, tmp_path, tmp_path / "default", 5, store)
        assert json.loads(default["text"].strip())["APROF_INHERITED_SECRET"] == "unfrozen"
        assert not {"environment", "timeout_seconds", "pid"} & set(default)
