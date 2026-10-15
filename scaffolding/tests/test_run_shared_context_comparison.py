"""Small real ledgers/tars with mocked native execution: never builds or devices."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
import run_shared_context_comparison as wrapper
import shared_context_campaign as campaign

H = 'sha256:' + 'a' * 64


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)
    return path


def source(directory, archive, label):
    from prepare_trace_pilot import create_source_snapshot
    write(directory / 'op_host/main.cpp', 'host ' + label)
    write(directory / 'op_kernel/kernel.cpp', 'kernel ' + label)
    write(directory / 'CMakeLists.txt', 'cmake fixture')
    archive.parent.mkdir(parents=True, exist_ok=True)
    create_source_snapshot(directory, archive, root_label='small-real-snapshot-fixture')
    return wrapper.sha(archive)


def build(path, first, second):
    roles = {}
    for role, directory in (('A', first), ('B', second)):
        binary = write(path.parent / (role + '.so'), 'tiny fake binary ' + role + str(path))
        adapter = write(path.parent / role / 'op_host/exp.asc', 'tiny audited adapter ' + role + str(path))
        write(path.parent / role / 'op_kernel/exp.h', 'tiny audited header ' + role)
        roles[role] = {'source_dir': str(directory), 'source_sha256': wrapper.build_tools.source_hash(directory),
                      'cmake_sha256': wrapper.sha(directory / 'CMakeLists.txt')[7:], 'binary': str(binary),
                      'binary_sha256': wrapper.sha(binary)[7:], 'kernel_symbols': 'exp_' + role,
                      'adapter_sha256': wrapper.sha(adapter)[7:]}
    wrapper.save(path, {'operator': 'exp', 'roles': roles})


def memories(run, labels):
    from shared_context_memory_plan import plan
    task = run / 'tasks/exp'
    audit = {'version': 'shared_context_resource_audit_v1', 'harness': [], 'adapters': []}
    sizeof = {'entries': []}
    for index, path in enumerate(dict.fromkeys(labels.values())):
        value = wrapper.load(path)
        for role in 'AB':
            adapter = path.parent / role / 'op_host/exp.asc'
            kernel = path.parent / role / 'op_kernel/exp.h'
            entry = {'role': role, 'operator': 'exp', 'type': 'ExpTilingData',
                'adapter_path': str(adapter), 'adapter_sha256': wrapper.sha(adapter)[7:],
                'header_path': str(kernel), 'header_sha256': wrapper.sha(kernel)[7:],
                'kernel_path': str(kernel), 'kernel_sha256': wrapper.sha(kernel)[7:],
                'source_sha256': value['roles'][role]['source_sha256']}
            audit['adapters'].append(entry)
            proof = {key: entry[key] for key in ('adapter_sha256', 'header_sha256', 'kernel_sha256', 'source_sha256', 'type')}
            proof.update(bytes=40, alignof=8, size_t_bytes=8)
            target = run / 'bootstrap' / f'sizeof-{index}-{role}.json'
            wrapper.save(target, proof, replace=target.exists())
            sizeof['entries'].append({**proof, 'compiler_command': ['synthetic-asc'], 'compiler_sha256': 'a' * 64,
                'compiler_version': 'CPU test fixture', 'cmake_parameters': ['fixture'],
                'evidence_path': str(target), 'evidence_sha256': wrapper.sha(target)[7:]})
    for name, value in (('resource-preflight-audit.json', audit), ('sizeof-metadata.json', sizeof)):
        target = run / 'bootstrap' / name
        wrapper.save(target, value, replace=target.exists())
    attributes = [{'case_id': case, 'dtype': 'float32', 'numel': 1} for case in range(1, 21)]
    path = task / 'input-bindings.json'
    wrapper.save(path, {'cases': [{'case_id': row['case_id'], 'attributes': row} for row in attributes]}, replace=path.exists())
    for label, path in labels.items():
        rows = []
        for case in attributes:
            request = {'case': case, 'cores': 48, 'buffer_configs': ['normal', 'swapped'],
                       'roles': {role: str(path.parent / role / 'op_host/exp.asc') for role in 'AB'}}
            rows.append({'case_id': case['case_id'], 'request': request, 'plan': plan(audit, sizeof, request)})
        target = task / (label + '-memory-plan.json')
        wrapper.save(target, {'label': label, 'prospective': True,
            'provenance': {'audit': wrapper.sha(run / 'bootstrap/resource-preflight-audit.json'), 'sizeof': wrapper.sha(run / 'bootstrap/sizeof-metadata.json')},
            'cases': rows}, replace=target.exists())


@pytest.fixture
def setup(tmp_path, monkeypatch):
    run = tmp_path / 'run'
    task = run / 'tasks/exp'
    base = source(task / 'baseline', task / 'baseline-source.tar', 'baseline')
    directory = task / 'candidates/exp001'
    changed = source(directory / 'source', directory / 'source.tar', 'candidate')
    inherited = {'candidate_id': 'exp001', 'source_hash': changed, 'patch_hash': H,
                 'source_parent': {'candidate_id': None, 'source_hash': base}, 'origin': {'run_id': 'old', 'manifest_ref': H},
                 'probes': [{'case_id': 3, 'reason': 'BF16 transfer probe'}]}
    cfg = campaign.make_config('run', {name: base if name == 'exp' else H for name in campaign.WORKLOADS}, inherited, H)
    ledger = campaign.prepare_ledger(run / 'ledger', cfg)
    ledger.resume(event_id='resume', reason='fixture authorization')
    build(task / 'aa-build/build_manifest.json', task / 'baseline', task / 'baseline')
    build(directory / 'ab-build/build_manifest.json', task / 'baseline', directory / 'source')
    wrapper.save(task / 'qualification/report.json', {'fixture': 'qualified'})
    memories(run, {'baseline': task / 'aa-build/build_manifest.json', 'exp001': directory / 'ab-build/build_manifest.json'})

    def prepare(args):
        assert Path(args.opdir) == task / 'baseline'
        cases = args.cases.split(',')
        manifest = {'run_id': args.run_id, 'task_id': 'exp', 'attempt_id': args.attempt_id,
            'comparison_id': args.comparison_id, 'comparison_kind': args.comparison_kind,
            'cases': [{'case_id': case} for case in cases], 'stages': args.phases.split(','),
            'qualification_scope': {'status': 'externally_qualified'},
            'session_plan': [{'session_id': f'{phase}-{r}', 'phase': phase, 'case_order': cases}
                             for phase in args.phases.split(',') for r in range(6)]}
        wrapper.save(Path(args.output) / 'manifest.json', manifest)
        wrapper.save(Path(args.output) / 'execution-plan.json', {'build': args.build, 'control_build': args.control_build})
        return manifest

    monkeypatch.setattr(wrapper.native, 'prepare', prepare)
    monkeypatch.setattr(wrapper.native, 'attest_files', lambda *args: None)
    monkeypatch.setattr(wrapper.native, 'verify_directory', lambda *args: {'valid': True})
    calls = []

    def execute(argv, cwd, out, **kwargs):
        calls.append(str(out))
        current = campaign.Ledger(run / 'ledger')
        assert current.state['tasks']['exp']['used']['timing_groups'] > 0
        assert any(stage['kind'] == 'timing' and stage['attempts'][-1]['outcome'] is None
                   for stage in current.state['tasks']['exp']['stages'].values())
        directory = Path(argv[-1])
        manifest = wrapper.load(directory / 'manifest.json')
        for session in manifest['session_plan']:
            rows = [{'type': 'sample'} for _ in range(len(session['case_order']) * 60)]
            rows.append({'type': 'session_end', 'exit_code': 0})
            write(directory / session['session_id'] / 'journal.jsonl', '\n'.join(json.dumps(row) for row in rows))
        wrapper.save(out / 'execution.json', {'status': 'passed'})
        wrapper.save(directory / 'report.json', {'measurement_quality': {'observed_checks_pass': True, 'failures': []},
            'phases': {'ab': {'suite': {'speedup': 1.1}, 'cases': {c['case_id']: {'speedup': 1.1} for c in manifest['cases']}}},
            'case_attributes': {c['case_id']: {} for c in manifest['cases']}})

    monkeypatch.setattr(wrapper, 'run_process', execute)
    return run, ledger, calls, execute


def ready(ledger, cid='exp001'):
    for kind in ('build', 'correctness'):
        sid = cid + '-' + kind
        ledger.start_stage(event_id=sid, workload='exp', candidate_id=cid, stage_id=sid, kind=kind,
                           plan={'case_ids': list(range(1, 21))} if kind == 'correctness' else {'argv': ['fixture-build']})
        ledger.finish_stage(event_id=sid + '-finish', workload='exp', stage_id=sid, outcome='success', evidence={'fixture_ref': H})


def test_search_counts_ab_only_and_preserves_quality_failure_without_retry(setup, monkeypatch):
    run, ledger, calls, execute = setup
    ready(ledger)

    def failed_quality(argv, cwd, out, **kwargs):
        execute(argv, cwd, out, **kwargs)
        path = Path(argv[-1]) / 'report.json'
        report = wrapper.load(path)
        report['measurement_quality'] = {'observed_checks_pass': False, 'failures': ['CV rejected']}
        wrapper.save(path, report, replace=True)

    monkeypatch.setattr(wrapper, 'run_process', failed_quality)
    result = wrapper.run(run, 'exp', 'exp001')
    assert result['status'] == 'quality_failed'
    assert result['formal_samples'] == 5 * 6 * 30 * 2
    assert result['actual_costs']['aa_event_samples'] == 3 * result['formal_samples']
    assert len(calls) == 1
    stage = campaign.Ledger(run / 'ledger').state['tasks']['exp']['stages']['exp001-timing-search']
    assert stage['attempts'][0]['outcome'] == 'quality_failed'
    assert not campaign.Ledger(run / 'ledger').state['tasks']['exp']['candidates']['exp001']['feedback_closed']
    assert stage['plan']['case_ids'] == [1, 8, 14, 20, 3]
    with pytest.raises(ValueError, match='retried'):
        wrapper.collect_group(run / 'tasks/exp/candidates/exp001/comparisons/search')
    assert len(calls) == 1


def test_missing_correctness_never_executes_or_charges(setup):
    run, ledger, calls, _ = setup
    prepared = wrapper.prepare_group(run, 'exp', 'exp001', 'search')
    with pytest.raises(ValueError, match='successful current build'):
        wrapper.collect_group(prepared['group'])
    assert calls == []
    assert campaign.Ledger(run / 'ledger').state['tasks']['exp']['used']['timing_groups'] == 0


def test_final_requires_exact_freeze_and_all_cases(setup):
    run, ledger, calls, _ = setup
    ready(ledger)
    with pytest.raises(ValueError, match='explicit ledger freeze'):
        wrapper.run(run, 'exp', 'exp001', 'final')
    prepared = wrapper.prepare_group(run, 'exp', 'exp001', 'final')
    with pytest.raises(ValueError, match='exact frozen plan'):
        wrapper.collect_group(prepared['group'])
    assert not calls
    ledger.observation(event_id='obs', workload='exp', observation_id='obs', candidate_id='exp001',
        stage_ids=['exp001-build', 'exp001-correctness'], feedback={'result': 'ready to freeze fixture'}, close_feedback=True,
        quality={k: False for k in ('correctness', 'runtime', 'stable', 'protocol_qualified')}, evidence_ref=H)
    ledger.freeze(event_id='freeze', workload='exp', candidate_ids=['exp001'], final_plans={'exp001': prepared['ledger_plan']}, reason='fixture selection closed')
    result = wrapper.collect_group(prepared['group'])
    assert result['status'] == 'passed' and result['formal_samples'] == 20 * 360
    assert len(result['evaluations'][0]['cases']) == 20


def test_search_plan_cannot_reveal_undeclared_case(setup):
    run, ledger, calls, _ = setup
    ready(ledger)
    prepared = wrapper.prepare_group(run, 'exp', 'exp001', 'search')
    path = Path(prepared['group']) / 'ledger-plan.json'
    plan = wrapper.load(path)
    plan['case_ids'].append(19)
    wrapper.save(path, plan, replace=True)
    with pytest.raises(ValueError, match='ledger plan differs'):
        wrapper.collect_group(prepared['group'])
    assert not calls


def test_execution_failure_retains_partial_samples_and_charge(setup, monkeypatch):
    run, ledger, calls, _ = setup
    ready(ledger)

    def crash(argv, cwd, out, **kwargs):
        directory = Path(argv[-1])
        write(directory / 'ab-0/journal.jsonl', '{"type":"sample"}\n{"type":')
        wrapper.save(out / 'execution.json', {'status': 'failed'})
        raise RuntimeError('fixture native crash')

    monkeypatch.setattr(wrapper, 'run_process', crash)
    result = wrapper.run(run, 'exp', 'exp001')
    assert result['status'] == 'execution_failed'
    assert result['formal_samples'] == 1 and result['actual_costs']['journal_parse_errors'] == 1
    current = campaign.Ledger(run / 'ledger')
    assert current.state['tasks']['exp']['used']['timing_groups'] == 1
    assert current.state['tasks']['exp']['stages']['exp001-timing-search']['attempts'][0]['outcome'] == 'failed'


def test_archive_and_native_source_scopes_are_verified_separately(setup):
    run, ledger, calls, _ = setup
    task = run / 'tasks/exp'
    bound = wrapper.source_binding(task / 'baseline-source.tar', task / 'baseline', ledger.config['tasks']['exp']['baseline_source_hash'], wrapper.load(task / 'aa-build/build_manifest.json'), 'A')
    assert bound['archive']['sha256'] != bound['native_source_hash']
    path = task / 'candidates/exp001/ab-build/build_manifest.json'
    data = wrapper.load(path)
    data['roles']['B']['source_sha256'] = ledger.state['tasks']['exp']['candidates']['exp001']['source_hash'][7:]
    wrapper.save(path, data, replace=True)
    with pytest.raises(ValueError, match='build native source hash mismatch'):
        wrapper.prepare_group(run, 'exp', 'exp001', 'search')
    assert not calls


def test_source_tree_change_is_rejected_before_stage(setup):
    run, ledger, calls, _ = setup
    ready(ledger)
    prepared = wrapper.prepare_group(run, 'exp', 'exp001', 'search')
    write(run / 'tasks/exp/candidates/exp001/source/op_kernel/kernel.cpp', 'changed after freeze')
    with pytest.raises(ValueError, match='native source differs from archive'):
        wrapper.collect_group(prepared['group'])
    assert not calls


def test_distinct_parent_needs_two_true_builds_and_never_composes_ratios(setup):
    run, ledger, calls, _ = setup
    ready(ledger)
    plan = campaign.timing_plan(ledger.state['tasks']['exp']['candidates']['exp001'], ledger.config['tasks']['exp']['baseline_source_hash'],
                                purpose='search', manifest_ref=H)
    ledger.start_stage(event_id='prior-timing', workload='exp', candidate_id='exp001', stage_id='prior-timing', kind='timing', plan=plan)
    ledger.finish_stage(event_id='prior-timing-finish', workload='exp', stage_id='prior-timing', outcome='success', formal_samples=5 * 360,
                        evidence={'fixture_ref': H})
    ledger.observation(event_id='obs', workload='exp', observation_id='obs', candidate_id='exp001',
        stage_ids=['exp001-build', 'exp001-correctness', 'prior-timing'], feedback={'result': 'next fixture'}, close_feedback=True,
        quality={k: True for k in ('correctness', 'runtime', 'stable', 'protocol_qualified')}, evidence_ref=H)
    directory = run / 'tasks/exp/candidates/exp002'
    changed = source(directory / 'source', directory / 'source.tar', 'second candidate')
    ledger.register(event_id='register-two', workload='exp', candidate_id='exp002', source_hash=changed, patch_hash=H,
        source_parent={'candidate_id': 'exp001', 'source_hash': ledger.state['tasks']['exp']['candidates']['exp001']['source_hash']},
        decision_basis=['obs'], probes=[])
    with pytest.raises(ValueError, match='distinct direct parent'):
        wrapper.prepare_group(run, 'exp', 'exp002', 'search')
    base = run / 'tasks/exp/baseline'
    parent = directory.parent / 'exp001/source'
    build(directory / 'wrong-build/build_manifest.json', base, directory / 'source')
    build(directory / 'parent-aa/build_manifest.json', parent, parent)
    inputs = {'comparisons': [
        {'control': 'parent', 'build': str(directory / 'wrong-build/build_manifest.json'),
         'control_build': str(directory / 'parent-aa/build_manifest.json'), 'qualification_report': str(run / 'tasks/exp/qualification/report.json')},
        {'control': 'original', 'build': str(directory / 'wrong-build/build_manifest.json'),
         'control_build': str(run / 'tasks/exp/aa-build/build_manifest.json'), 'qualification_report': str(run / 'tasks/exp/qualification/report.json')}]}
    path = run / 'comparison-inputs.json'
    wrapper.save(path, inputs)
    with pytest.raises(ValueError, match='wrong source directory'):
        wrapper.prepare_group(run, 'exp', 'exp002', 'search', path)
    build(directory / 'parent-ab/build_manifest.json', parent, directory / 'source')
    inputs['comparisons'][0]['build'] = str(directory / 'parent-ab/build_manifest.json')
    inputs['comparisons'][0].update(memory_label='exp002-parent', control_memory_label='exp001-aa')
    inputs['comparisons'][1]['memory_label'] = 'exp002-original'
    memories(run, {'baseline': run / 'tasks/exp/aa-build/build_manifest.json',
        'exp002-parent': directory / 'parent-ab/build_manifest.json', 'exp001-aa': directory / 'parent-aa/build_manifest.json',
        'exp002-original': directory / 'wrong-build/build_manifest.json'})
    wrapper.save(path, inputs, replace=True)
    prepared = wrapper.prepare_group(run, 'exp', 'exp002', 'search', path)
    assert len(prepared['ledger_plan']['comparisons']) == 2
    assert [row['control_source_hash'] for row in prepared['ledger_plan']['comparisons']] == [
        ledger.state['tasks']['exp']['candidates']['exp001']['source_hash'], ledger.config['tasks']['exp']['baseline_source_hash']]
    assert not calls
    ready(ledger, cid='exp002')
    result = wrapper.collect_group(prepared['group'])
    assert result['status'] == 'passed' and result['formal_samples'] == 4 * 2 * 360
    assert [row['control'] for row in result['evaluations']] == ['parent', 'original']
    assert len(calls) == 2


def test_real_snapshot_and_both_build_memory_plans_are_frozen_before_collection(setup):
    run, ledger, calls, _ = setup
    prepared = wrapper.prepare_group(run, 'exp', 'exp001', 'search')
    group = Path(prepared['group'])
    bindings = wrapper.load(group / 'source-native-bindings.json')
    assert all(row['snapshot_kind'] == 'aprof_source_snapshot_v1' and row['snapshot_file_count'] == 3 for row in bindings.values())
    memory = wrapper.load(group / 'memory-plan-bindings.json')['original']
    assert memory['ab']['label'] == 'exp001' and memory['aa']['label'] == 'baseline'
    assert memory['ab']['prospective'] is True
    assert (group / 'producers/shared_context_wrapper_evidence.py').is_file()
    assert not calls


def test_memory_plan_requires_swap_controls_and_rejects_stale_sizeof_before_charge(setup):
    run, ledger, calls, _ = setup
    ready(ledger)
    path = run / 'tasks/exp/baseline-memory-plan.json'
    value = wrapper.load(path)
    value['cases'][0]['request']['buffer_configs'] = ['normal']
    wrapper.save(path, value, replace=True)
    with pytest.raises(ValueError, match='both buffer configurations'):
        wrapper.prepare_group(run, 'exp', 'exp001', 'search')
    assert not calls and ledger.state['tasks']['exp']['used']['timing_groups'] == 0
    memories(run, {'baseline': run / 'tasks/exp/aa-build/build_manifest.json',
                   'exp001': run / 'tasks/exp/candidates/exp001/ab-build/build_manifest.json'})
    prepared = wrapper.prepare_group(run, 'exp', 'exp001', 'search')
    proof = run / 'bootstrap/sizeof-0-A.json'
    proof.write_bytes(proof.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='sizeof evidence hash mismatch'):
        wrapper.collect_group(prepared['group'])
    assert not calls and campaign.Ledger(run / 'ledger').state['tasks']['exp']['used']['timing_groups'] == 0
