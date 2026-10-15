from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


REPO = Path(__file__).resolve().parents[2]
TRACES = REPO.parent / "optimization-traces"
RELEASE = REPO / "skill-libs/graph-base/1.0.0"
AUDIT = REPO / "scaffolding/curation/graph-base-1.0.0.json"
SPEC = importlib.util.spec_from_file_location("verify_teacher_wiki", REPO / "scaffolding/tools/verify_teacher_wiki.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.mark.skipif(not (TRACES / "index.json").exists(), reason="external trace archive absent")
def test_teacher_wiki_respects_current_split():
    inventory = MODULE.inventory(REPO, TRACES)
    assert len(inventory) == 66
    assert inventory["l2:softmax001"]["split"] == "test"
    assert inventory["l2:arg_max001"]["split"] == "train"
    assert MODULE.verify(REPO, TRACES, RELEASE, AUDIT)["wiki_pages"] == 10


@pytest.mark.skipif(not (TRACES / "index.json").exists(), reason="external trace archive absent")
def test_teacher_wiki_rejects_leaked_test_record(tmp_path):
    audit = json.loads(AUDIT.read_text())
    row = audit["records"]["l2:softmax001"]
    row["decision"] = "include"
    row["wiki_ids"] = ["parent-baseline"]
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(audit))
    with pytest.raises(ValueError, match="validation/test source entered Wiki"):
        MODULE.verify(REPO, TRACES, RELEASE, path)


def test_frozen_split_validates_without_upstream_catalog():
    result = subprocess.run([sys.executable, str(REPO / "scaffolding/benchmarks/cannbench/validate_splits.py")],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "validation=5, test=15" in result.stdout


@pytest.mark.parametrize("fault", ["changed_gate", "new_module", "missing_schema"])
def test_teacher_rejects_changed_frozen_machine_inventory_before_runtime_import(tmp_path, fault):
    release = tmp_path / "candidate"
    for prefix in ("runtime", "skillgraph/versions", "schemas"):
        shutil.copytree(RELEASE / prefix, release / prefix, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    assert MODULE.verify_frozen_machine_rules(REPO, release)["protected_files"] > 0
    if fault == "changed_gate":
        path = release / "runtime/src/aprof_runtime/gates.py"
        path.write_text(path.read_text() + "\nraise RuntimeError('must never import this changed gate')\n")
    elif fault == "new_module":
        (release / "runtime/src/aprof_runtime/new_gate.py").write_text("raise RuntimeError('must not import')\n")
    else:
        (release / "schemas/gate-request.schema.json").unlink()
    with pytest.raises(ValueError, match="frozen machine-rule inventory differs"):
        # Missing trace/audit paths prove that the guard runs before the rest
        # of verification or any candidate runtime import.
        MODULE.verify(REPO, tmp_path / "absent-traces", release, tmp_path / "absent-audit")


@pytest.mark.skipif(not (TRACES / "index.json").exists(), reason="external trace archive absent")
def test_rejected_proposal_evidence_must_match_hash(tmp_path):
    release = tmp_path / "candidate"
    shutil.copytree(RELEASE, release, ignore=shutil.ignore_patterns("__pycache__"))
    evidence = MODULE.source(AUDIT, REPO.parent)
    evidence["sha256"] = "sha256:" + "0" * 64
    event = {"decision": "rejected", "proposal_id": "tampered-rejection",
             "wiki_id": "tile-amortization", "reason": "failed independent control",
             "evidence_refs": [evidence]}
    with (release / "wiki/evolution.jsonl").open("a") as stream:
        stream.write(json.dumps(event) + "\n")
    with pytest.raises(ValueError, match="hash differs"):
        MODULE.verify(REPO, TRACES, release, AUDIT)


def promotion_fixture(tmp_path):
    """A text edit fixture only; no claim of real hardware acceptance."""
    repo = tmp_path / "repo"
    release = repo / "skill-libs/graph-base/1.0.0"
    skill = "skills/example/SKILL.md"
    (release / skill).parent.mkdir(parents=True)
    (release / skill).write_text("new conditional instruction\n")
    for version in ("0.5.0", "1.0.0"):
        destination = repo / "skill-libs/graph-base" / version
        original = REPO / "skill-libs/graph-base" / version
        for prefix in ("runtime", "skillgraph/versions", "schemas"):
            shutil.copytree(original / prefix, destination / prefix, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(REPO / "skill-libs/graph-base/0.5.0/release.json", repo / "skill-libs/graph-base/0.5.0/release.json")
    for split, operators in (("train", ["exp"]), ("validation", []), ("test", [])):
        root = repo / "scaffolding/benchmarks/cannbench" / split
        root.mkdir(parents=True)
        (root / "operators.txt").write_text("".join(name + "\n" for name in operators))
        (root / "manifest.json").write_text(json.dumps({"active_operators": operators}))
    before = tmp_path / "before.md"
    before.write_text("prior instruction\n")
    event = {"proposal_id": "test-proposal", "wiki_id": "tile", "target_skill": skill}
    entry = {"source_keys": ["history"], "skill_refs": [skill]}
    records = {"history": {"operator": "exp", "sources": [{"path": "history/old-run/trace.json"}]}}
    receipt = {"schema_version": 1, **event, "source_keys": entry["source_keys"],
               "skill_before": MODULE.source(before, tmp_path),
               "skill_after": MODULE.source(release / skill, tmp_path), "validations": []}
    return repo, release, event, entry, records, receipt


def test_promotion_rejects_absent_or_forged_receipt(tmp_path):
    repo, release, event, entry, records, receipt = promotion_fixture(tmp_path)
    with pytest.raises(ValueError, match="receipt requires"):
        MODULE.verify_promotion(event, entry, records, repo, release)
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt))
    event["validation_receipt"] = MODULE.source(path, tmp_path)
    path.write_text(json.dumps({**receipt, "verdict": "production_safe_gain"}))
    with pytest.raises(ValueError, match="hash differs"):
        MODULE.verify_promotion(event, entry, records, repo, release)


def test_promotion_rejects_bare_acceptance_and_multiple_skills(tmp_path):
    repo, release, event, entry, records, receipt = promotion_fixture(tmp_path)
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt))
    event["validation_receipt"] = MODULE.source(path, tmp_path)
    with pytest.raises(ValueError, match="independent formal validation"):
        MODULE.verify_promotion(event, entry, records, repo, release)
    entry["skill_refs"].append("skills/another/SKILL.md")
    with pytest.raises(ValueError, match="exactly one canonical skill"):
        MODULE.verify_promotion(event, entry, records, repo, release)


@pytest.mark.parametrize("fault", ["none", "forged_outcome", "missing_boundary", "wrong_source", "historical_run",
                                  "missing_control", "failed_control", "missing_campaign", "mixed_operator_scope"])
def test_promotion_replays_current_exploration_gate_without_policy_episode(tmp_path, fault):
    # A subprocess selects the frozen 1.0.0 runtime even when the surrounding
    # regression suite deliberately tests an older release.
    program = r'''
import json, sys
from pathlib import Path
from test_teacher_wiki import promotion_fixture, MODULE
root, fault = Path(sys.argv[1]), sys.argv[2]
repo, release, event, entry, records, receipt = promotion_fixture(root)
sys.path.insert(0, str(release / 'runtime/src'))
from test_traces_exploration import request_fixture
from test_profile_evidence_v11 import seal_capture
from aprof_runtime.store import EpisodeStore
from aprof_runtime.profile_evidence import normalize_profile
from aprof_runtime.exploration import ExplorationGate
from aprof_runtime.traces import register_json_artifact, make_optimization_trace
import timing_admission

# This test isolates machine-gate/Teacher wiring. The admission module's own
# tests independently replay complete synthetic raw/log/control evidence.
def replay_control(store, reference, *, expected):
    assert store.verify_artifact(reference)
    assert expected['purpose'] == 'promotion'
    if fault == 'failed_control':
        raise ValueError('A/A session drift exceeds frozen threshold')
    return {'passed': True, 'protocol_ref': reference, 'stage_windows': {'boundary': [1, 2], 'profile': [3, 4]}}
timing_admission.verify_timing_admission = replay_control
timing_admission.verify_boundary_report = lambda *args, **kwargs: {'passed': True}
timing_admission.verify_profile_window = lambda *args, **kwargs: {'passed': True}
MODULE.verify_campaign = lambda store, ref, **kwargs: {'verified': bool(store.verify_artifact(ref))}

with EpisodeStore(root / 'evidence.sqlite') as store:
    request = request_fixture(root, store)
    candidate, evidence = request['candidates'][0], request['evidence'][0]
    hardware_ref = register_json_artifact(store, {'soc': 'Ascend910C', 'device': 0,
        'cann_version': {'version': 'synthetic test, never hardware evidence'}})
    mechanism = json.loads(store.verify_artifact(evidence['artifacts']['mechanism_report']).read_text())
    for metric in mechanism['metrics']:
        for role in ('baseline', 'candidate'):
            profile = json.loads(store.verify_artifact(metric[role + '_profile_hash']).read_text())
            capture = json.loads(store.verify_artifact(profile['capture_manifest_hash']).read_text())
            capture['hardware_hash'] = hardware_ref
            for row in capture['captures']:
                seal_capture(store, capture, row)
            spec = {name: {key: value[key] for key in ('unit', 'aggregation', 'sources')}
                    for name, value in profile['metrics'].items()}
            metric[role + '_profile_hash'] = register_json_artifact(store,
                normalize_profile(store, register_json_artifact(store, capture), spec))
    evidence['artifacts']['mechanism_report'] = register_json_artifact(store, mechanism)
    sources = candidate['source_hashes']
    log = register_json_artifact(store, {'test_fixture_only': True, 'exit_status': 0})
    refs = {}
    for name, cases, role in [('correctness', list(range(1, 21)), 'accuracy_report'),
                              ('boundary', [21, 22], 'boundary_report')]:
        report = {'run_id': 'run', 'candidate_id': 'c1', 'source_hashes': sources,
                  'status': 'passed', 'case_ids': cases, 'passed_case_ids': cases,
                  'execution': {'exit_status': 0, 'log_ref': log}}
        if fault == 'wrong_source' and name == 'boundary':
            report['source_hashes'] = {'baseline': sources['baseline'], 'candidate': sources['baseline']}
        refs[name + '_report_ref'] = register_json_artifact(store, report)
        if not (fault == 'missing_boundary' and name == 'boundary'):
            evidence['artifacts'][role] = refs[name + '_report_ref']
    evidence['artifacts']['hardware_report'] = hardware_ref
    control_ref = register_json_artifact(store, {'test_fixture_only': True, 'controls': 'isolated wiring fixture'})
    registration_ref = register_json_artifact(store, {'test_fixture_only': True, 'registration': 'isolated wiring fixture'})
    if fault != 'missing_control':
        evidence['artifacts']['control_report'] = control_ref
    evidence['artifacts']['qualification_registration'] = registration_ref
    campaign_ref = register_json_artifact(store, {'test_fixture_only': True, 'campaign': 'isolated wiring fixture'})
    if fault != 'missing_campaign':
        evidence['artifacts']['qualification_campaign'] = campaign_ref
    if fault == 'forged_outcome':
        evidence['scope'] = 'failed'
    outcome, = ExplorationGate().evaluate(request, store=store)
    if fault == 'forged_outcome':
        assert outcome['verdict'] == 'benchmark_specialized_gain'
        outcome['verdict'] = 'production_safe_gain'
    else:
        assert outcome['verdict'] == 'production_safe_gain'
    outcome_ref = register_json_artifact(store, outcome)
    stages = {name: {'status': 'passed', 'reason': 'synthetic fixture', 'artifact_refs': []}
              for name in ('static_review', 'build', 'correctness', 'runtime', 'timing', 'profile')}
    trace = make_optimization_trace({'run_id': 'run', 'task_id': 'task', 'session_id': 'session',
        'attempt_id': 'a1', 'candidate_id': 'c1', 'operator': 'exp', 'split': 'train',
        'source_parent_hash': sources['baseline']},
        provenance={'baseline_source_hash': sources['baseline'], 'candidate_source_hash': sources['candidate'],
                    'patch_hash': candidate['patch_artifact_hash']},
        intervention={'handler': {'id': candidate['handler_id'], 'version': candidate['handler_version'],
                                  'producer_hash': None}, 'parameters': candidate['parameters']},
        workload={'case_ids': list(range(1, 21)), 'hardware_fingerprint': hardware_ref},
        validation={**stages, 'case_count': 20, 'passed_count': 20, 'timing_case_ids': list(range(1,21))},
        result={'verdict': 'production_safe_gain', 'exploration_outcome_ref': outcome_ref})
    path = root / 'trace.json'
    path.write_text(json.dumps(trace))
    validation = {'run_id': 'run', 'trace': MODULE.source(path, root),
                  'original_baseline_hash': sources['baseline'], 'direct_parent_hash': sources['baseline'],
                  'hardware_report_ref': hardware_ref, 'control_report_ref': control_ref,
                  'registration_ref': registration_ref, 'campaign_report_ref': campaign_ref, **refs}
validation['store'] = MODULE.source(root / 'evidence.sqlite', root)
receipt['validations'] = [validation]
path = root / 'receipt.json'
path.write_text(json.dumps(receipt))
event['validation_receipt'] = MODULE.source(path, root)
if fault == 'historical_run':
    records['history']['sources'][0]['path'] = 'history/run/trace.json'
if fault == 'mixed_operator_scope':
    records['mish-history'] = {'operator': 'mish', 'sources': [{'path': 'history/mish/trace.json'}]}
    entry['source_keys'].append('mish-history')
    receipt['source_keys'] = entry['source_keys']
    path.write_text(json.dumps(receipt))
    event['validation_receipt'] = MODULE.source(path, root)
try:
    MODULE.verify_promotion(event, entry, records, repo, release)
except Exception as exc:
    if fault == 'none':
        raise
    messages = {'forged_outcome': 'does not replay', 'missing_boundary': 'gate-bound boundary',
                'wrong_source': 'source identity differs', 'historical_run': 'independent run identity',
                'missing_control': 'gate-bound control', 'failed_control': 'session drift',
                'missing_campaign': 'complete qualification campaign',
                'mixed_operator_scope': 'every source operator'}
    assert messages[fault] in str(exc), str(exc)
else:
    assert fault == 'none', 'forged or incomplete promotion was admitted'
assert MODULE.source(root / 'evidence.sqlite', root) == validation['store'], 'verification mutated store'
'''
    environment = dict(os.environ, APROF_SKILL_LIB=str(RELEASE), PYTHONPATH=os.pathsep.join(map(str, (
        RELEASE / "runtime/src", REPO / "scaffolding/collection/scripts", REPO / "scaffolding/tests"))))
    result = subprocess.run([sys.executable, "-c", program, str(tmp_path), fault],
                            env=environment, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
