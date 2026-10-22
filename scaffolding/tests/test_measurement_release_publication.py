"""Measurement repair publication cannot borrow the Teacher release's evidence.

The temporary verifier stubs test dispatch and failure handling only. They are
not measurement qualification and no real package is sealed by this module.
"""
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest

import release_skill_lib as release


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def candidate(tmp_path):
    source = ROOT / 'skill-libs/graph-base/0.5.0'
    destination = tmp_path / 'graph-base/0.5.1'
    tool = release.release_module(source)
    destination.mkdir(parents=True)
    for name in tool.verify(source)['files']:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)
    path = destination / 'skillgraph/registry.json'
    registry = json.loads(path.read_text())
    registry['library']['version'] = registry['workflow_plugin']['version'] = '0.5.1'
    path.write_text(json.dumps(registry))
    for host in ('.codex-plugin', '.claude-plugin'):
        path = destination / host / 'plugin.json'
        manifest = json.loads(path.read_text())
        manifest['version'] = '0.5.1'
        path.write_text(json.dumps(manifest))
    return destination


def test_measurement_release_requires_its_own_report(candidate, tmp_path):
    with pytest.raises(ValueError, match='requires --measurement-validation'):
        release.seal(candidate, 'synthetic-test', '0.5.0', validation_run=tmp_path / 'teacher-results')
    assert not (candidate / 'release.json').exists()


def test_real_verifier_rejects_a_claimed_summary(candidate, tmp_path):
    report = tmp_path / 'claimed-summary.json'
    report.write_text(json.dumps({'accepted': True, 'stable': True}))
    with pytest.raises(ValueError, match='invalid publication report schema'):
        release.seal(candidate, 'synthetic-test', '0.5.0', measurement_validation=report)
    assert not (candidate / 'release.json').exists()


@pytest.mark.parametrize('claimed', [False, None, 1, 'true'])
def test_measurement_release_requires_explicit_independent_acceptance(candidate, tmp_path, monkeypatch, claimed):
    calls = []
    report = tmp_path / 'unqualified.json'

    def verifier(root, path):
        calls.append((root, path))
        return {'accepted': claimed}

    monkeypatch.setitem(sys.modules, 'verify_task_window_publication',
                        SimpleNamespace(verify_task_window_publication=verifier))
    with pytest.raises(ValueError, match='lacks independent publication acceptance'):
        release.seal(candidate, 'synthetic-test', '0.5.0', measurement_validation=report)
    assert calls == [(candidate.resolve(), report.resolve())]
    assert not (candidate / 'release.json').exists()


def test_measurement_verifier_failure_cannot_create_manifest(candidate, tmp_path, monkeypatch):
    def verifier(*_):
        raise ValueError('raw control evidence is not replayable')

    monkeypatch.setitem(sys.modules, 'verify_task_window_publication',
                        SimpleNamespace(verify_task_window_publication=verifier))
    with pytest.raises(ValueError, match='not replayable'):
        release.seal(candidate, 'synthetic-test', '0.5.0', measurement_validation=tmp_path / 'report')
    assert not (candidate / 'release.json').exists()


def test_measurement_candidate_cannot_change_after_verification(candidate, tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, 'verify_task_window_publication',
                        SimpleNamespace(verify_task_window_publication=lambda *_: {'accepted': True}))

    def mutate(*_, **__):
        (candidate / 'README.md').write_text('changed after qualification')

    monkeypatch.setattr(release.subprocess, 'run', mutate)
    with pytest.raises(ValueError, match='candidate changed while verifying'):
        release.seal(candidate, 'synthetic-test', '0.5.0', measurement_validation=tmp_path / 'report')
    assert not (candidate / 'release.json').exists()


def test_measurement_report_does_not_replace_teacher_gate(tmp_path):
    with pytest.raises(ValueError, match='Teacher and equal-budget'):
        release.publication_evidence(ROOT / 'skill-libs/graph-base/1.0.0', None, tmp_path / 'report')
    with pytest.raises(ValueError, match='uses --measurement-validation'):
        release.publication_evidence(ROOT / 'skill-libs/graph-base/0.5.1', tmp_path / 'teacher', tmp_path / 'method')
    assert release.publication_evidence(ROOT / 'skill-libs/graph-base/0.5.0', None) is None
