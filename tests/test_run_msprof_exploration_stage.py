"""Stage accounting and observed-runtime checks without loading an NPU runtime."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run_msprof_exploration_stage as stage
from msprof_exploration_execute import save


def test_runtime_requires_twenty_successful_teardowns(tmp_path):
    root = tmp_path / 'correctness'
    save(root / 'completion.json', {'status': 'passed', 'completed': [{'case_id': str(c)} for c in range(1, 21)]})
    for c in range(1, 21):
        save(root / f'case_{c:02d}/native.json', {'exit_code': 0, 'stream_destroyed': True, 'context_destroyed': True, 'finalized': True})
    result = stage.runtime_assessment(root, tmp_path / 'runtime.json')
    assert result['new_native_execution'] is False
    assert result['formal_admission'] == 'not_evaluated'
    bad = root / 'case_20/native.json'
    bad.write_text(json.dumps({'exit_code': 0, 'stream_destroyed': True, 'context_destroyed': False, 'finalized': True}))
    with pytest.raises(ValueError, match='safely'):
        stage.runtime_assessment(root, tmp_path / 'invalid.json')
    assert not (tmp_path / 'invalid.json').exists()


def test_partial_costs_do_not_refund_started_process(tmp_path):
    journal = tmp_path / 'session/native/journal.jsonl'; journal.parent.mkdir(parents=True)
    rows = [{'type': 'process_start'}, {'type': 'case_start', 'warmup_per_role': 10},
            {'type': 'sample', 'repeat': 10, 'launches_per_call': 4}]
    journal.write_text(''.join(json.dumps(r) + '\n' for r in rows) + '{broken')
    result = stage.actual_costs(tmp_path)
    assert result['native_processes_started'] == 1 and result['native_processes_completed'] == 0
    assert result['role_samples'] == 1 and result['timed_complete_calls'] == 10
    assert result['formal_target_kernel_launches'] == 40 and result['warmup_complete_calls'] == 0
    assert result['unconfirmed_warmup_blocks'] == 1
    journal.write_text(''.join(json.dumps(r) + '\n' for r in rows[:2] + [{'type': 'warmup_complete', 'calls_per_role': 10}] + rows[2:]))
    result = stage.actual_costs(tmp_path)
    assert result['warmup_complete_calls'] == 20 and result['unconfirmed_warmup_blocks'] == 0


def test_build_start_precedes_execution_and_failure_is_closed(tmp_path, monkeypatch):
    events = []
    class Ledger:
        config = {"policy": {"protocol": stage.PROTOCOL}}
        def __init__(self, *args): pass
        def validate_start(self, **kwargs): pass
        def start(self, **kwargs): events.append(('start', kwargs))
        def finish(self, **kwargs): events.append(('finish', kwargs))
    def build(*args):
        assert events[0][0] == 'start'
        events.append(('execute', {}))
        raise RuntimeError('compiler failed')
    monkeypatch.setattr(stage, 'Campaign', Ledger)
    monkeypatch.setattr(stage, 'build_operator', build)
    monkeypatch.setattr(stage, 'verify_source_snapshot', lambda *args: None)
    task = tmp_path / 'train/tasks/exp'
    task.mkdir(parents=True)
    (task / 'baseline-source.tar').write_bytes(b'frozen')
    result = stage.run_stage(tmp_path, 'exp', 'baseline', 'build', 'build')
    assert [e[0] for e in events] == ['start', 'execute', 'finish']
    assert events[0][1]['event_id'] == 'exp-baseline-build-start'
    assert events[-1][1]['event_id'] == 'exp-baseline-build-finish'
    assert events[-1][1]['outcome'] == 'build_failed'
    assert events[-1][1]['native_started'] is False
    assert result['status'] == 'failed'
    assert (task / 'stages/build/result.json').exists()
    with pytest.raises(FileExistsError): stage.run_stage(tmp_path, 'exp', 'baseline', 'build', 'build')
    assert len(events) == 3


def test_changed_explicit_calibration_blocks_before_new_native(tmp_path, monkeypatch):
    class Ledger:
        config = {"policy": {"protocol": stage.PROTOCOL}}
        def __init__(self, *args): pass
        def validate_start(self, **kwargs): pass
        def start(self, **kwargs): pass
        def finish(self, **kwargs): pass
    monkeypatch.setattr(stage, 'Campaign', Ledger)
    monkeypatch.setattr(stage, 'collect_cohort', lambda *args: pytest.fail('must not start native'))
    calibration = tmp_path / 'calibration.json'
    save(calibration, {'changed': True})
    plan = tmp_path / 'plan.json'
    save(plan, {'calibration_report': {'path': str(calibration), 'sha256': 'sha256:' + '0' * 64}, 'cohorts': []})
    result = stage.run_stage(tmp_path, 'exp', 'exp001', 'timing', 'search', plan_path=plan)
    assert result['status'] == 'failed' and result['native_started'] is False
    assert result['error']['message'] == 'frozen calibration report changed'


def test_source_identity_deduplicates_revert_and_relabel(tmp_path):
    original = tmp_path / 'original'; variant = tmp_path / 'variant'; proposed = tmp_path / 'new-label'
    for root, code in [(original, 'tile=4096'), (variant, 'tile=8192'), (proposed, 'tile=4096')]:
        (root / 'op_kernel').mkdir(parents=True)
        (root / 'op_kernel/kernel.asc').write_text(code)
    with pytest.raises(ValueError, match='same source as baseline'):
        stage.require_distinct_source(proposed, {'parent': variant, 'baseline': original})
    (proposed / 'op_kernel/kernel.asc').write_text('tile=8192')
    with pytest.raises(ValueError, match='same source as earlier'):
        stage.require_distinct_source(proposed, {'baseline': original, 'earlier': variant})
    (proposed / 'op_kernel/kernel.asc').write_text('tile=6144')
    assert stage.require_distinct_source(proposed, {'baseline': original, 'earlier': variant}).startswith('sha256:')


def test_two_comparisons_use_their_frozen_calibration_and_preflight_all(tmp_path, monkeypatch):
    class Ledger:
        config = {"policy": {"protocol": stage.PROTOCOL}}
        def __init__(self, *args): pass
        def validate_start(self, **kwargs): pass
        def start(self, **kwargs): pass
        def finish(self, **kwargs): pass
    monkeypatch.setattr(stage, 'Campaign', Ledger)
    captures = []
    monkeypatch.setattr(stage, 'collect_cohort', lambda plan, out, calibration: captures.append((plan, calibration)))
    base, parent = tmp_path / 'base.json', tmp_path / 'parent.json'
    save(base, {'source': 'original'}); save(parent, {'source': 'actual-parent'})
    cohorts = []
    for relation in ['direct_parent', 'original_baseline']:
        path = tmp_path / (relation + '.json'); save(path, {'relation': relation})
        cohorts.append({'relation': relation, 'plan': stage.pointer(path)})
    cohorts[0]['calibration_report'] = stage.pointer(parent)
    plan = tmp_path / 'plan.json'
    save(plan, {'calibration_report': stage.pointer(base), 'cohorts': cohorts})
    result = stage.run_stage(tmp_path, 'exp', 'exp002', 'timing', 'search', plan_path=plan)
    assert result['status'] == 'passed'
    assert [cal['source'] for _, cal in captures] == ['actual-parent', 'original']
    captures.clear()
    parent.write_text('{}')
    result = stage.run_stage(tmp_path, 'exp', 'exp002', 'timing', 'other', plan_path=plan)
    assert result['status'] == 'failed' and not captures and not result['native_started']


def test_fixed_parent_aa_control_uses_explicit_plan(tmp_path, monkeypatch):
    events = []
    class Ledger:
        config = {"policy": {"protocol": stage.PROTOCOL}}
        def __init__(self, *args): pass
        def validate_start(self, **kwargs): events.append(kwargs)
        def start(self, **kwargs): pass
        def finish(self, **kwargs): pass
    monkeypatch.setattr(stage, 'Campaign', Ledger)
    captures = []
    monkeypatch.setattr(stage, 'collect_cohort', lambda plan, out: captures.append(plan))
    path = tmp_path / 'plan.json'
    save(path, {'source_hash': 'sha256:' + 'e' * 64, 'control_type': 'aa', 'cohort': {'actual_source': 'exp001'}})
    result = stage.run_stage(tmp_path, 'exp', 'baseline', 'control', 'aa-parent', plan_path=path)
    assert result['status'] == 'passed'
    assert events[0]['candidate_id'] is None
    assert captures == [{'actual_source': 'exp001'}]
    assert events[0]['plan']['source_hash'] == 'sha256:' + 'e' * 64


def test_reused_oracles_are_calls_not_new_processes(tmp_path):
    save(tmp_path / 'standalone/completion.json', {'actual_costs': {'verifier_calls': 20, 'verifier_processes_started': 0}})
    save(tmp_path / 'standalone/case_01/verify.execution.json', {'mode': 'in_process_original_verifier_v1', 'verifier_calls': 1, 'verifier_processes_started': 0})
    save(tmp_path / 'evidence/case_01/verify.execution.json', {'mode': 'in_process_original_verifier_v1', 'verifier_calls': 1, 'verifier_processes_started': 0})
    actual = stage.actual_costs(tmp_path)
    assert actual['verifier_calls'] == 21 and actual['verifier_processes_started'] == 0


@pytest.mark.parametrize('purpose', ['search', 'final'])
@pytest.mark.parametrize('epoch', [None, 'masked-scale-input-domain-02'])
def test_prepare_timing_freezes_epoch_for_parent_and_original_cohorts(tmp_path, monkeypatch, purpose, epoch):
    task = tmp_path / 'train/tasks/masked_scale'
    baseline_hash, parent_hash, candidate_hash = ['sha256:' + char * 64 for char in 'abc']
    candidate = {'candidate_id': 'masked002', 'source_hash': candidate_hash,
                 'source_parent': {'candidate_id': 'masked001', 'source_hash': parent_hash},
                 'probes': [{'case_id': 3}, {'case_id': 9}]}
    class Ledger:
        def __init__(self, directory):
            assert directory == tmp_path / 'train/ledger'
            self.state = {'tasks': {'masked_scale': {'candidates': {'masked002': candidate}}}}
            self.config = {'tasks': {'masked_scale': {'baseline_source_hash': baseline_hash}}}
        def timing_plan(self, workload, candidate_id, **kwargs):
            return stage.timing_plan(candidate, baseline_hash, **kwargs)
    monkeypatch.setattr(stage, 'Campaign', Ledger)
    for root, source_hash in [(task, baseline_hash), (task / 'candidates/masked001', parent_hash),
                              (task / 'candidates/masked002', candidate_hash)]:
        save(root / 'build/build_manifest.json', {'operator': 'masked_scale', 'harness': {},
              'roles': {role: {'source_sha256': source_hash} for role in 'AB'}})
    save(task / 'input-bindings.json', {'cases': [
        {'case_id': case, 'metadata': {'path': str(task / f'prepared/{case}/metadata.json')},
         'verifier': {'path': str(task / 'baseline/scripts/verify_result.py')}} for case in range(1, 21)]})
    save(tmp_path / 'tools/timing/build.json', {'runner_hash': 'sha256:' + 'd' * 64})
    kwargs = {} if epoch is None else {'epoch': epoch}
    path = stage.prepare_timing(tmp_path, 'masked_scale', 'masked002', 'timing-' + purpose,
                                purpose=purpose, **kwargs)
    plan = stage.load(path)
    assert [row['relation'] for row in plan['cohorts']] == ['direct_parent', 'original_baseline']
    assert [row['control_candidate_id'] for row in plan['cohorts']] == ['masked001', 'baseline']
    expected_cases = list(range(1, 21)) if purpose == 'final' else [1, 8, 14, 20, 3, 9]
    assert plan['case_ids'] == expected_cases
    for row, control_hash in zip(plan['cohorts'], [parent_hash, baseline_hash]):
        ref = row['plan']
        assert stage.sha(ref['path']) == ref['sha256']
        cohort = stage.load(ref['path'])
        assert cohort['calibration_scope']['epoch'] == (epoch or 'epoch-01')
        assert cohort['case_ids'] == expected_cases and len(cohort['schedule']) == 6
        comparison = stage.load(cohort['schedule'][0]['request']['role_build'])
        assert comparison['roles']['A']['source_sha256'] == control_hash
        assert comparison['roles']['B']['source_sha256'] == candidate_hash


def test_fresh_graph_registration_binds_complete_checked_bundle(tmp_path):
    import shutil
    from aprof_runtime.jsonio import content_hash
    from aprof_runtime.errors import GraphError
    graph = tmp_path / 'graph/v0002'
    shutil.copytree(Path(__file__).resolve().parents[1] / 'skillgraph/versions/v0002', graph)
    ref = stage.pointer(graph / 'graph.json')
    digest = content_hash(stage.load(graph / 'graph.json'))
    refs = stage.fresh_graph_bundle(tmp_path, ref, digest)
    assert {Path(r['path']).name for r in refs} == {'graph.json', 'manifest.json', 'checksums.json', 'lineage.json'}
    assert all(stage.sha(r['path']) == r['sha256'] for r in refs)
    with pytest.raises(ValueError, match='frozen run'):
        stage.fresh_graph_bundle(tmp_path, {**ref, 'path': str(tmp_path / 'other/graph.json')}, digest)
    (graph / 'lineage.json').write_text('{}')
    with pytest.raises(GraphError, match='checksum'):
        stage.fresh_graph_bundle(tmp_path, ref, digest)


def test_fresh_launch_registration_rejects_independent_sidecar_plan(tmp_path):
    from copy import deepcopy
    from shared_context_build import source_hash
    source = tmp_path / 'candidate/op'
    (source / 'op_host').mkdir(parents=True)
    (source / 'op_host/operator.asc').write_text('transpose<<<1,0,s>>>(); selected<<<1,0,s>>>(); fallback<<<1,0,s>>>();')
    dispatch = {'operator': 'x', 'entries': [{'tiling_key': 4, 'kernel_entry': 'selected'}],
                'fallback': {'tiling_key': 0, 'kernel_entry': 'fallback'}}
    launch = {'version': 'level2_dispatch_launch_v1', 'source_sha256': source_hash(source),
              'dispatch_plan': dispatch, 'sequences': {
                  '4': {'kernels': ['transpose', 'selected'], 'auxiliary_tasks': []},
                  '0': {'kernels': ['fallback'], 'auxiliary_tasks': []}}}
    path = source.parent / 'dispatch-launch.json'
    save(path, launch)
    assert stage.fresh_dispatch_launch(source, stage.pointer(path), dispatch) == launch
    for fault in ['plan', 'source', 'missing_key', 'missing_symbol', 'missing_selected', 'malformed_aux']:
        bad = deepcopy(launch)
        if fault == 'plan': bad['dispatch_plan']['operator'] = 'other'
        elif fault == 'source': bad['source_sha256'] = '0' * 64
        elif fault == 'missing_key': del bad['sequences']['0']
        elif fault == 'missing_symbol': bad['sequences']['4']['kernels'].append('absent')
        elif fault == 'missing_selected': bad['sequences']['4']['kernels'] = ['transpose']
        else: bad['sequences']['4']['auxiliary_tasks'] = 'device_memset'
        path.write_text(json.dumps(bad))
        with pytest.raises(ValueError, match='fresh dispatch'):
            stage.fresh_dispatch_launch(source, stage.pointer(path), dispatch)


def test_registration_rechecks_frozen_metadata_before_selection(tmp_path):
    path = tmp_path / 'metadata.json'
    save(path, {'shape': [128], 'dtype': 'float32'})
    row = {'case_id': 1, 'metadata': stage.pointer(path)}
    assert stage.frozen_workload_metadata(row)['shape'] == [128]
    path.write_text(json.dumps({'shape': [256], 'dtype': 'float32'}))
    with pytest.raises(ValueError, match='metadata changed'):
        stage.frozen_workload_metadata(row)


def test_fresh_build_uses_bound_npu_arch_and_requires_new_arch_compiler(tmp_path):
    from copy import deepcopy
    from test_planning import context_example
    profile = context_example()['evidence']['architecture_profile']
    task = tmp_path / 'task'; task.mkdir()
    path = task / 'profile.json'
    def bind(value):
        path.write_text(json.dumps(value))
        (task / 'manifest.json').write_text(json.dumps({'version': 'msprof_task_time_exploration_v2',
                                                      'architecture_profile': stage.pointer(path)}))
    bind(profile)
    assert stage.fresh_build_target(task)['npu_arch'] == 'dav-2201'
    value = deepcopy(profile); value.update(soc_name='Ascend950PR_9599', architecture_id='950', npu_arch=3510)
    value.pop('compiler', None); bind(value)
    with pytest.raises(ValueError, match='verified compiler'):
        stage.fresh_build_target(task)
    value['compiler'] = dict(status='verified', path='/sdk/bisheng', version='clang15', evidence_refs=['sha256:'+'a'*64])
    bind(value)
    assert stage.fresh_build_target(task)['npu_arch'] == 'dav-3510'
    path.write_text('{}')
    with pytest.raises(ValueError, match='absent or changed'):
        stage.fresh_build_target(task)
    value = deepcopy(profile); value.update(soc_name='MysterySoC', architecture_id='unknown', npu_arch=None); bind(value)
    with pytest.raises(ValueError, match='unknown or unsupported'):
        stage.fresh_build_target(task)


def test_fresh_build_passes_profile_target_to_actual_builder(tmp_path, monkeypatch):
    events = []
    class Ledger:
        config = {'schema_version':'msprof_exploration_campaign_v2', 'policy': {'protocol': stage.PROTOCOL}}
        def __init__(self, *args): pass
        def validate_start(self, **kwargs): pass
        def start(self, **kwargs): events.append('start')
        def finish(self, **kwargs): events.append('finish')
    monkeypatch.setattr(stage, 'Campaign', Ledger)
    monkeypatch.setattr(stage, 'verify_source_snapshot', lambda *args: None)
    monkeypatch.setattr(stage, 'fresh_build_target', lambda *args: {'npu_arch':'dav-3510'})
    def build(*args, **kwargs):
        assert events == ['start']
        assert kwargs == {'npu_arch':'dav-3510'}
        events.append('build')
    monkeypatch.setattr(stage, 'build_operator', build)
    task = tmp_path / 'train/tasks/exp'; task.mkdir(parents=True)
    (task / 'baseline-source.tar').write_bytes(b'frozen')
    result = stage.run_stage(tmp_path, 'exp', 'baseline', 'build', 'build')
    assert result['status'] == 'passed' and events == ['start','build','finish']
    assert stage.load(task / 'stages/build/build-target.json')['npu_arch'] == 'dav-3510'
