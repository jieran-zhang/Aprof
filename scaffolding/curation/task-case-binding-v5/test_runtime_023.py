"""Narrow runtime identity checks after applying the authorized 1.0-only change."""
import os
from pathlib import Path
import tomllib
from types import SimpleNamespace

import pytest

from aprof_runtime import __version__
from aprof_runtime.errors import StoreError
from aprof_runtime.gates import CandidateGate
from aprof_runtime.store import _verify_profile_admission


def test_runtime_and_distribution_metadata_agree():
    root = Path(os.environ['APROF_CASE_BINDING_TEST_RELEASE'])
    metadata = tomllib.loads((root / 'runtime/pyproject.toml').read_text())
    assert __version__ == metadata['project']['version'] == '0.2.3'


@pytest.mark.parametrize('build', ['aprof-runtime/0.2.3', 'aprof-runtime/0.2.4'])
def test_episode_replay_uses_current_full_gate_or_rejects_unknown_build(monkeypatch, build):
    outcome = SimpleNamespace(candidate_id='candidate')
    episode = SimpleNamespace(runtime_build=build, gate_request=object(),
                              draft=SimpleNamespace(candidate_id='candidate'), outcome=outcome)
    calls, store = [], object()
    def evaluate(self, request, *, store):
        calls.append((request, store))
        return [outcome]
    monkeypatch.setattr(CandidateGate, 'evaluate', evaluate)
    if build.endswith('0.2.4'):
        with pytest.raises(StoreError, match='unsupported runtime identity'):
            _verify_profile_admission(episode, store)
        assert calls == []
    else:
        _verify_profile_admission(episode, store)
        assert calls == [(episode.gate_request, store)]
