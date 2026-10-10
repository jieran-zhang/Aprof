"""Campaign release selection is explicit, immutable and independent of catalog defaults."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
import aprof_layout as layout
from aprof_layout import skill_lib


def test_no_implicit_latest(monkeypatch):
    monkeypatch.delenv('APROF_SKILL_LIB', raising=False)
    monkeypatch.setattr(sys, 'argv', ['collector'])
    with pytest.raises(ValueError, match='no implicit latest'):
        layout.skill_lib()


def test_new_run_binds_release_and_rejects_changes(tmp_path, monkeypatch):
    run = tmp_path / 'run'
    binding = layout.bind_run(run)
    expected = json.loads((skill_lib() / 'release.json').read_text())['release_id']
    assert binding['release_id'] == expected
    assert layout.verify_run(run) == binding
    monkeypatch.setattr(sys, 'argv', ['collector', '--run', str(run)])
    monkeypatch.setenv('APROF_SKILL_LIB', str(tmp_path / 'different'))
    with pytest.raises(ValueError, match='differs from frozen'):
        layout.skill_lib()


def test_existing_historical_run_is_not_rebound(tmp_path):
    run = tmp_path / 'historical'; run.mkdir()
    marker = run / 'events.jsonl'; marker.write_bytes(b'original bytes\n')
    with pytest.raises(ValueError, match='historical run'):
        layout.bind_run(run)
    assert marker.read_bytes() == b'original bytes\n' and not (run / 'skill-lib.json').exists()


def test_unbound_historical_execution_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='historical run'):
        layout.verify_run(tmp_path)


def test_collector_freezes_copied_release_and_rejects_tampering(tmp_path):
    package = tmp_path / 'standalone'
    shutil.copytree(skill_lib(), package, ignore=shutil.ignore_patterns('__pycache__', '.runtime-env', '*.egg-info', 'build'))
    run = tmp_path / 'campaign'
    env = {k: v for k, v in os.environ.items() if k not in ('APROF_SKILL_LIB', 'PYTHONPATH')}
    env['PYTHONPATH'] = str(layout.SCRIPTS)
    subprocess.run([sys.executable, '-c', 'from aprof_layout import bind_run; import sys; bind_run(sys.argv[1])',
                    str(run), '--skill-lib', str(package)], env=env, check=True, capture_output=True)
    command = [sys.executable, str(layout.SCRIPTS / 'level2_campaign.py'), 'freeze-engineering', '--run', str(run)]
    result = subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    frozen = json.loads(Path(json.loads(result.stdout)['path']).read_text())
    assert frozen['skill_library']['path'] == str(package)
    assert str(package / 'release.json') in frozen['skill_files']
    assert str(layout.SCRIPTS / 'level2_campaign.py') in frozen['collector_files']
    assert not set(frozen['skill_files']) & set(frozen['collector_files'])
    assert all(Path(row['snapshot']).is_file() for row in frozen['files'])
    source = package / 'skills/ascendc-aprof-workflow/SKILL.md'
    source.write_bytes(source.read_bytes() + b'\ntampered\n')
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    assert result.returncode != 0 and 'release bytes differ' in result.stderr
    assert len(list((run / 'bootstrap').glob('frozen-engineering-*.json'))) == 1
