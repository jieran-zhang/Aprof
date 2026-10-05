"""Synthetic CPU-only regression for frozen producer identity resolution."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import msprof_exploration_provenance as provenance
import msprof_exploration_report as report
from test_msprof_exploration_report import data, put, setup_inputs, make_session, make_cohort


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    scripts = tmp_path / 'repo/scripts'
    runs = tmp_path / 'repo/.aprof/runs'
    monkeypatch.setattr(provenance, 'ENGINEERING_SCRIPTS', scripts)
    monkeypatch.setattr(provenance, 'CAMPAIGN_RUNS', runs)
    run = runs / 'level1-msprof-feedback-20260911T101952Z'
    task = run / 'train/tasks/exp'
    task.mkdir(parents=True)
    live = Path(data(scripts / 'msprof_exploration_execute.py', b'# original producer\n'))
    expected = report.sha(live)
    snapshot = Path(data(run / 'bootstrap/source-cas' / expected[7:], live.read_bytes()))
    manifest = Path(put(run / 'bootstrap/frozen-engineering.json', {'files': [
        {'path': str(live), 'sha256': expected, 'snapshot': str(snapshot)}]}))
    return dict(run=run, task=task, live=live, expected=expected, snapshot=snapshot, manifest=manifest,
                document={'campaign_build': {'generator': {'path': str(live), 'sha256': expected}}})


def test_changed_producer_keeps_exact_old_report_and_emits_separate_provenance(frozen):
    request, build = setup_inputs(frozen['task'])
    build.update(frozen['document'])
    put(request['role_build'], build)
    directory = make_session(frozen['task'], request, build)
    original = report.verify_observation(directory)
    frozen['live'].write_text('# changed engineering implementation\n')
    before = {p: (p.stat().st_mtime_ns, report.sha(p)) for p in frozen['run'].rglob('*') if p.is_file()}
    side = []
    replay = report.verify_observation(directory, provenance_out=side)
    preflight = []
    report._build_identity(request, report.load(directory / 'bindings.json'), provenance_out=preflight)
    assert preflight == side
    assert replay == original
    binding = side[0]
    assert binding['origin'] == {'path': str(frozen['live']), 'sha256': frozen['expected']}
    assert binding['snapshot']['path'] == str(frozen['snapshot'])
    assert binding['snapshot']['sha256'] == frozen['expected']
    assert str(frozen['snapshot']) not in replay['artifacts']
    assert before == {p: (p.stat().st_mtime_ns, report.sha(p)) for p in frozen['run'].rglob('*') if p.is_file()}


@pytest.mark.parametrize('field', ['input', 'source', 'dependency'])
def test_nonproducer_semantic_pointer_cannot_use_frozen_script(frozen, field):
    frozen['live'].write_text('# changed\n')
    pointer = frozen['document']['campaign_build']['generator']
    with pytest.raises(ValueError, match='dependency pointer hash differs'):
        provenance.verify_pointer_tree({field: pointer}, evidence_path=frozen['task'] / 'build.json')


def test_input_python_file_cannot_use_producer_fallback(frozen):
    live = Path(data(frozen['task'] / 'input.py', b'original input'))
    expected = report.sha(live)
    snapshot = data(frozen['run'] / 'bootstrap/source-cas' / expected[7:], live.read_bytes())
    put(frozen['manifest'], {'files': [{'path': str(live), 'sha256': expected, 'snapshot': snapshot}]})
    live.write_text('changed input')
    with pytest.raises(ValueError, match='dependency pointer hash differs'):
        provenance.verify_pointer_tree({'producer': {'path': str(live), 'sha256': expected}},
                                       evidence_path=frozen['task'] / 'build.json')


def test_snapshot_corruption_is_rejected(frozen):
    frozen['live'].write_text('# changed\n')
    frozen['snapshot'].write_text('corrupt')
    with pytest.raises(ValueError, match='snapshot hash differs'):
        provenance.verify_pointer_tree(frozen['document'], evidence_path=frozen['task'] / 'build.json')


def test_unknown_campaign_cannot_select_freeze_directory(frozen):
    frozen['live'].write_text('# changed\n')
    with pytest.raises(ValueError, match='dependency pointer hash differs'):
        provenance.verify_pointer_tree(frozen['document'], evidence_path=frozen['run'].parent / 'unknown/train/tasks/exp/build.json')


def test_unfrozen_producer_cannot_resolve_old_hash(frozen):
    frozen['live'].write_text('# changed\n')
    frozen['manifest'].unlink()
    with pytest.raises(ValueError, match='dependency pointer hash differs'):
        provenance.verify_pointer_tree(frozen['document'], evidence_path=frozen['task'] / 'build.json')


def test_legacy_collector_cannot_use_engineering_fallback(frozen):
    legacy = Path(data(frozen['live'].parent / 'cannbench_msprof_timing.py', b'old legacy'))
    expected = report.sha(legacy)
    snapshot = data(frozen['run'] / 'bootstrap/source-cas' / expected[7:], legacy.read_bytes())
    put(frozen['manifest'], {'files': [{'path': str(legacy), 'sha256': expected, 'snapshot': snapshot}]})
    legacy.write_text('changed legacy')
    with pytest.raises(ValueError, match='dependency pointer hash differs'):
        provenance.verify_pointer_tree({'producer': {'path': str(legacy), 'sha256': expected}},
                                       evidence_path=frozen['task'] / 'build.json')


def test_snapshot_outside_campaign_cas_is_rejected(frozen):
    frozen['live'].write_text('# changed\n')
    elsewhere = data(frozen['task'] / 'snapshot.py', frozen['snapshot'].read_bytes())
    value = provenance.load(frozen['manifest'])
    value['files'][0]['snapshot'] = elsewhere
    put(frozen['manifest'], value)
    with pytest.raises(ValueError, match='snapshot location differs'):
        provenance.verify_pointer_tree(frozen['document'], evidence_path=frozen['task'] / 'build.json')


def test_new_plan_identity_bindings_are_verified(tmp_path):
    dirs, plan = make_cohort(tmp_path)
    request = plan['schedule'][0]['request']
    inputs = Path(put(tmp_path / 'inputs.json', {'fixture': True}))
    ptr = lambda path: {'path': str(path), 'sha256': report.sha(path)}
    plan['calibration_scope']['inputs'] = report.sha(inputs)
    plan['identity_bindings'] = {key: ptr(request[key]) for key in ('role_build', 'runner_build')}
    plan['identity_bindings'].update(input_bindings=ptr(inputs), producer=ptr(report._legacy()[0].__file__))
    assert report.validate_plan(plan)['identity_bindings'] == plan['identity_bindings']
    bad = deepcopy(plan)
    bad['identity_bindings']['role_build']['path'] = request['runner_build']
    with pytest.raises(ValueError, match='manifest path differs'):
        report.validate_plan(bad)
    inputs.write_text('changed')
    with pytest.raises(ValueError, match='dependency pointer hash differs'):
        report.validate_plan(plan)


def fresh_producer_fixture(frozen, monkeypatch, *, bind=True):
    run=frozen['run'].parent/'level2-skill-graph-base-20261005-experiment'
    task=run/'train/tasks/maximum';task.mkdir(parents=True)
    manifest=Path(put(task/'manifest.json',dict(version='msprof_task_time_exploration_v2',run_id=run.name,
        operator='maximum',split='train',source_split='test',task_dir=str(task))))
    live=Path(data(frozen['live'].parent/'level2_adapters.py',b'# old level2 producer\n'))
    expected=report.sha(live);snapshot=Path(data(run/'bootstrap/source-cas'/expected[7:],live.read_bytes()))
    freeze=Path(put(run/'bootstrap/frozen-engineering-01.json',{'files':[{'path':str(live),'sha256':expected,'snapshot':str(snapshot)}],
        'task_manifests':[{'path':str(manifest),'sha256':report.sha(manifest)}] if bind else []}))
    live.write_text('# new level2 producer\n')
    return dict(run=run,task=task,manifest=manifest,freeze=freeze,live=live,expected=expected,
                pointer={'producer':{'path':str(live),'sha256':expected}})


def test_manifest_attested_fresh_run_can_resolve_new_producer(frozen,monkeypatch):
    value=fresh_producer_fixture(frozen,monkeypatch)
    bindings=[]
    assert provenance.campaign_root(value['task']/'result.json')==value['run']
    provenance.verify_pointer_tree(value['pointer'],evidence_path=value['task']/'result.json',producer_bindings=bindings)
    assert len(bindings)==1 and bindings[0]['origin']['sha256']==value['expected']


def test_fresh_producer_requires_frozen_task_manifest_identity(frozen,monkeypatch):
    value=fresh_producer_fixture(frozen,monkeypatch,bind=False)
    with pytest.raises(ValueError,match='task manifest binding'):
        provenance.verify_pointer_tree(value['pointer'],evidence_path=value['task']/'result.json')


def test_fresh_run_wrong_task_identity_cannot_select_snapshots(frozen,monkeypatch):
    value=fresh_producer_fixture(frozen,monkeypatch)
    document=provenance.load(value['manifest']);document['operator']='scatter';put(value['manifest'],document)
    assert provenance.campaign_root(value['task']/'result.json') is None
    with pytest.raises(ValueError,match='dependency pointer hash differs'):
        provenance.verify_pointer_tree(value['pointer'],evidence_path=value['task']/'result.json')


def test_saved_report_allows_only_attested_analyzer_identity_update(frozen, monkeypatch):
    analyzer = Path(data(frozen['live'].parent / 'msprof_exploration_report.py', b'# historical analyzer\n'))
    expected = report.sha(analyzer)
    snapshot = data(frozen['run'] / 'bootstrap/source-cas' / expected[7:], analyzer.read_bytes())
    put(frozen['manifest'], {'files': [{'path': str(analyzer), 'sha256': expected, 'snapshot': snapshot}]})
    analyzer.write_text('# current analyzer\n')
    monkeypatch.setattr(report, '__file__', str(analyzer))
    saved = {'results': [{'speedup': 1.0}], 'sessions': [{'pid': 7}], 'calibration_report_hash': 'original',
             'analysis_producer_hash': expected}
    actual = {**saved, 'analysis_producer_hash': report.sha(analyzer)}
    before = deepcopy(saved)
    side = []
    result = report.compare_saved_report(saved, actual, evidence_path=frozen['task'] / 'report.json', provenance_out=side)
    assert result['matched'] and result['comparison'] != 'exact'
    assert saved == before and side[0]['snapshot']['sha256'] == expected
    for key, value in [('results', [{'speedup': 1.1}]), ('sessions', [{'pid': 8}]), ('calibration_report_hash', 'other')]:
        with pytest.raises(ValueError, match='saved report differs'):
            report.compare_saved_report(saved, {**actual, key: value}, evidence_path=frozen['task'] / 'report.json')
    frozen['manifest'].unlink()
    with pytest.raises(ValueError, match='dependency pointer hash differs'):
        report.compare_saved_report(saved, actual, evidence_path=frozen['task'] / 'report.json')


@pytest.mark.parametrize('name',['level2_iteration.py','level2_boundaries.py','level2_finalize.py',
    'level2_storage.py','level2_failure_classification.py','level2_raw_method.py','msprof_raw_storage.py'])
def test_fresh_iteration_producers_keep_task_attestation_constraints(frozen,monkeypatch,name):
    value=fresh_producer_fixture(frozen,monkeypatch)
    old=value['live']; new=old.with_name(name); old.rename(new)
    document=provenance.load(value['freeze']);document['files'][0]['path']=str(new);put(value['freeze'],document)
    pointer={'producer':{'path':str(new),'sha256':value['expected']}}
    provenance.verify_pointer_tree(pointer,evidence_path=value['task']/'result.json')
    with pytest.raises(ValueError,match='dependency pointer hash differs'):
        provenance.verify_pointer_tree({'script':pointer['producer']},evidence_path=value['task']/'result.json')


def test_boundary_guard_is_exact_task_source_not_trusted_producer(frozen,monkeypatch):
    value=fresh_producer_fixture(frozen,monkeypatch)
    script=Path(data(value['task']/'agent/boundary_guard.py',b'# task guard\n'))
    ref={'path':str(script),'sha256':report.sha(script)}
    provenance.verify_pointer_tree({'script':ref},evidence_path=value['task']/'boundary/request.json')
    script.write_text('# changed guard\n')
    with pytest.raises(ValueError,match='dependency pointer hash differs'):
        provenance.verify_pointer_tree({'script':ref},evidence_path=value['task']/'boundary/request.json')
