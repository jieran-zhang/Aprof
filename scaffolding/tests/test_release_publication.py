"""A stable manifest cannot bypass the Teacher and equal-budget release gates."""
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest

import release_skill_lib as release
import verify_teacher_wiki as teacher


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def candidate(tmp_path):
    destination = tmp_path / 'graph-base/1.0.0'
    shutil.copytree(ROOT / 'skill-libs/graph-base/1.0.0', destination,
                    ignore=shutil.ignore_patterns('release.json', '__pycache__', '.runtime-env', '*.pyc'))
    return destination


def test_seal_cannot_omit_equal_budget_acceptance(candidate):
    with pytest.raises(ValueError, match='requires --validation-run'):
        release.seal(candidate, 'test-source', '0.5.0')
    assert not (candidate / 'release.json').exists()


def test_seal_cannot_bypass_independent_promotion(candidate, tmp_path, monkeypatch):
    monkeypatch.setattr(teacher, 'verify', lambda *args: {'promoted_skills': 0})
    with pytest.raises(ValueError, match='no independently validated skill'):
        release.seal(candidate, 'test-source', '0.5.0', tmp_path / 'claimed-results')
    assert not (candidate / 'release.json').exists()


def test_seal_rejects_evaluation_that_does_not_admit_publication(candidate, tmp_path, monkeypatch):
    monkeypatch.setattr(teacher, 'verify', lambda *args: {'promoted_skills': 1})
    calls = []

    def rejected(output, *, release):
        calls.append((output, release))
        return {'accepted': False}

    monkeypatch.setitem(sys.modules, 'evaluate_skill_release', SimpleNamespace(verify_publication=rejected))
    output = tmp_path / 'results'
    with pytest.raises(ValueError, match='do not support stable publication'):
        release.seal(candidate, 'test-source', '0.5.0', output)
    assert calls == [(output.resolve(), candidate.resolve())]
    assert not (candidate / 'release.json').exists()


def test_existing_release_families_keep_their_original_gate():
    assert release.publication_evidence(ROOT / 'skill-libs/graph-base/0.5.0', None) is None


def test_seal_rejects_skill_changes_after_qualification(candidate, tmp_path, monkeypatch):
    monkeypatch.setattr(teacher, 'verify', lambda *args: {'promoted_skills': 1})
    monkeypatch.setitem(sys.modules, 'evaluate_skill_release',
                        SimpleNamespace(verify_publication=lambda *args, **kwargs: {'accepted': True}))

    def changed_during_graph_check(*args, **kwargs):
        (candidate / 'skills/ascendc-aprof-workflow/SKILL.md').write_text('changed after qualification')

    monkeypatch.setattr(release.subprocess, 'run', changed_during_graph_check)
    with pytest.raises(ValueError, match='candidate changed while verifying'):
        release.seal(candidate, 'test-source', '0.5.0', tmp_path / 'results')
    assert not (candidate / 'release.json').exists()
