"""CPU integration checks for the new executor; all device commands are replaced."""
import io
import json
from pathlib import Path
import sys
import tarfile
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import msprof_exploration_execute as execute


@pytest.mark.parametrize('existing', [False, True])
def test_recorded_shared_read_rejects_wrong_task_without_writes(tmp_path, monkeypatch, existing):
    monkeypatch.setattr(execute, 'ROOT', tmp_path)
    knowledge = tmp_path / 'docs/skill.md'
    knowledge.parent.mkdir(); knowledge.write_text('knowledge')
    task = tmp_path / 'wrong-task'
    if existing:
        task.mkdir(); (task / 'keep').write_text('original')
    before = {str(p): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    with pytest.raises(ValueError, match='existing campaign task manifest'):
        execute.read_recorded(task, knowledge, 'diagnosis')
    assert task.exists() == existing
    assert before == {str(p): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


@pytest.mark.parametrize('change', [{'version': 'old_protocol'}, {'task_dir': '/wrong/task'}, {'task_dir': None}])
def test_recorded_read_rejects_misbound_manifest(tmp_path, monkeypatch, change):
    monkeypatch.setattr(execute, 'ROOT', tmp_path)
    task = tmp_path / 'task'; task.mkdir()
    execute.save(task / 'manifest.json', {'version': execute.PROTOCOL, 'task_dir': str(task), **change})
    with pytest.raises(ValueError, match='manifest identity differs'):
        execute.read_recorded(task, tmp_path / 'docs/not-even-read.md', 'diagnosis')
    assert sorted(p.name for p in task.iterdir()) == ['manifest.json']


def test_recorded_reads_keep_task_and_split_boundaries(tmp_path, monkeypatch):
    monkeypatch.setattr(execute, 'ROOT', tmp_path)
    task = tmp_path / 'validation/tasks/gelu'; task.mkdir(parents=True)
    execute.save(task / 'manifest.json', {'version': execute.PROTOCOL, 'task_dir': str(task)})
    for name in ['agent/metadata.json', 'baseline/kernel.h']:
        path = task / name; path.parent.mkdir(exist_ok=True); path.write_text(name)
        assert execute.read_recorded(task, path, 'inspect declared source') == name
    knowledge = tmp_path / 'docs/skill.md'; knowledge.parent.mkdir(); knowledge.write_text('shared')
    assert execute.read_recorded(task, knowledge, 'load workflow') == 'shared'
    records = list((task / 'knowledge-reads').glob('*.json'))
    assert len(records) == 3
    for denied in [task / 'calibration/card.json', tmp_path / 'train/tasks/exp/feedback/report.json',
                   tmp_path / 'validation/tasks/other/baseline/kernel.h']:
        with pytest.raises(ValueError, match='coordinator-only|outside this task'):
            execute.read_recorded(task, denied, 'not authorized')
    assert len(list((task / 'knowledge-reads').glob('*.json'))) == 3
    assert len((task / 'events.jsonl').read_text().splitlines()) == 3


def test_extract_rejects_traversal_and_symlinks(tmp_path):
    for name, kind in [('source/../../outside', tarfile.REGTYPE), ('source/link', tarfile.SYMTYPE)]:
        archive = tmp_path / ('bad-' + str(kind) + '.tar')
        with tarfile.open(archive, 'w') as tar:
            info = tarfile.TarInfo(name); info.type = kind
            info.linkname = '/etc/passwd'
            tar.addfile(info)
        with pytest.raises(ValueError, match='unsafe'):
            execute.extract_source(archive, tmp_path / ('out-' + str(kind)))
    assert not (tmp_path / 'outside').exists()


def test_recorder_preserves_order_and_no_overwrite(tmp_path):
    a = execute.event(tmp_path, 'read', {'path': 'skill', 'classification': 'knowledge_read'})
    b = execute.event(tmp_path, 'decision', {'basis': 'actual observation'})
    assert a['previous_hash'] is None and b['previous_hash'] == a['hash']
    assert b['sequence'] == 1
    assert json.loads((tmp_path / 'events.jsonl').read_text().splitlines()[0]) == a
    execute.save(tmp_path / 'frozen.json', {'x': 1})
    with pytest.raises(FileExistsError): execute.save(tmp_path / 'frozen.json', {'x': 2})


def test_combined_roles_preserve_actual_parent_and_candidate(tmp_path):
    a = {'operator': 'exp', 'harness': {}, 'roles': {'A': {'source_sha256': 'parent'}, 'B': {'source_sha256': 'parent'}}}
    b = {'operator': 'exp', 'harness': {}, 'roles': {'A': {'source_sha256': 'child'}, 'B': {'source_sha256': 'child'}}}
    execute.save(tmp_path / 'a.json', a); execute.save(tmp_path / 'b.json', b)
    c = execute.comparison_manifest(tmp_path / 'a.json', tmp_path / 'b.json', tmp_path / 'ab.json')
    assert c['roles'] == {'A': a['roles']['A'], 'B': b['roles']['B']}
    assert len(c['component_builds']) == 2


def test_cohort_never_starts_second_process_after_evidence_failure(tmp_path, monkeypatch):
    calls = []
    def collect(request, out):
        calls.append(str(out))
        out.mkdir()
    def invalid(*args, **kwargs): raise ValueError('missing case/config')
    fake = SimpleNamespace(validate_plan=lambda p: p, verify_observation=invalid,
                           analyze_task_cohort=lambda *args, **kwargs: pytest.fail('invalid evidence summarized'))
    monkeypatch.setitem(sys.modules, 'msprof_exploration_report', fake)
    monkeypatch.setattr(execute, 'execution_modules', lambda: (SimpleNamespace(collect=collect), None, None))
    monkeypatch.setattr(execute, 'preflight_cohort', lambda plan: {'producer_bindings': []})
    plan = {'protocol': execute.PROTOCOL, 'schedule': [{'name': f'p{i}', 'request': {}} for i in range(6)]}
    with pytest.raises(ValueError, match='missing'):
        execute.collect_cohort(plan, tmp_path / 'cohort')
    assert len(calls) == 1
    completion = execute.load(tmp_path / 'cohort/group-completion.json')
    assert completion['status'] == 'failed' and completion['completed_sessions'] == []


def test_cohort_matrix_and_declared_cases(tmp_path):
    task = tmp_path / 'task'; task.mkdir()
    rows = [{'case_id': c, 'metadata': {'path': f'/inputs/{c}.json'}, 'verifier': {'path': '/oracle.py'}} for c in [1, 8, 14, 20]]
    execute.save(task / 'input-bindings.json', {'cases': rows})
    execute.save(tmp_path / 'runner.json', {'runner_hash': 'sha256:' + '1' * 64})
    execute.save(tmp_path / 'roles.json', {})
    plan = execute.cohort_plan(task, tmp_path / 'roles.json', tmp_path / 'runner.json', [1, 8, 14, 20], 'ab', 'search')
    for key in ['load_order', 'first_order']:
        assert [r['request'][key] for r in plan['schedule']].count('AB') == 3
    assert [r['request']['buffer_configs'] for r in plan['schedule']].count('normal,swapped') == 3
    assert all(r['request']['profiler_mode'] == 'task_time_l1_ai_core_off' for r in plan['schedule'])
    assert plan['case_ids'] == [1, 8, 14, 20]


def preflight_fixture(tmp_path, *, composed=False):
    from test_msprof_exploration_report import setup_inputs
    task = tmp_path / 'repo/.aprof/runs/level1-msprof-feedback-20260911T000000Z/train/tasks/exp'
    request, build = setup_inputs(task, ids=(1, 8))
    verifier = task / 'baseline/scripts/verify_result.py'
    verifier.parent.mkdir(parents=True)
    verifier.write_text("raise AssertionError('preflight must never execute the oracle')\n")
    rows = []
    for spec in request['cases']:
        spec['verifier'] = str(verifier)
        meta = execute.load(spec['metadata'])
        rows.append({'case_id': spec['case_id'], 'metadata': execute.pointer(spec['metadata']),
                     'verifier': execute.pointer(verifier), 'inputs': {'input': execute.pointer(meta['input'])},
                     'oracle_file': execute.pointer(meta['golden'])})
    execute.save(task / 'input-bindings.json', {'cases': rows})
    roles = Path(request['role_build'])
    if composed:
        combined = task / 'plans/combined.json'
        execute.comparison_manifest(roles, roles, combined)
        roles = combined
    plan = execute.cohort_plan(task, roles, request['runner_build'], [1, 8], 'ab' if composed else 'aa', 'preflight')
    return task, plan, build


def rewrite(path, change):
    value = execute.load(path)
    change(value)
    Path(path).write_bytes(execute.canonical(value))


def test_preflight_is_read_only_and_never_loads_oracle_or_native(tmp_path, monkeypatch):
    import cannbench_msprof_timing as timing
    task, plan, _ = preflight_fixture(tmp_path)
    monkeypatch.setattr(timing, 'ReusedVerifier', lambda *args: pytest.fail('oracle imported'))
    monkeypatch.setattr(timing, 'collect', lambda *args: pytest.fail('native started'))
    before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.rglob('*') if p.is_file()}
    original_flag = sys.dont_write_bytecode
    result = execute.preflight_cohort(plan)
    assert result['read_only'] and result['checked_case_ids'] == [1, 8]
    assert result['identity_binding_mode'] == 'frozen_manifest_pointers'
    assert sys.dont_write_bytecode == original_flag
    assert before == {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.rglob('*') if p.is_file()}


@pytest.mark.parametrize('target', ['input', 'oracle', 'metadata', 'role_binary', 'source', 'adapter', 'role_patch', 'runner_binary', 'runner_patch', 'component_manifest'])
def test_preflight_rejects_changed_dependencies_before_collection(tmp_path, monkeypatch, target):
    task, plan, build = preflight_fixture(tmp_path, composed=True)
    spec = plan['schedule'][0]['request']['cases'][0]
    meta = execute.load(spec['metadata'])
    runner = execute.load(plan['schedule'][0]['request']['runner_build'])
    files = {'input': meta['input'], 'oracle': spec['verifier'], 'metadata': spec['metadata'],
             'role_binary': build['roles']['B']['binary'], 'source': task / 'baseline/op_kernel/kernel.h',
             'adapter': task / 'roles/A/op_host/exp.asc', 'role_patch': task / 'roles/B.harness.patch',
             'runner_binary': runner['runner'], 'runner_patch': task / 'runner/harness.patch',
             'component_manifest': task / 'roles/build_manifest.json'}
    path = Path(files[target]); path.write_bytes(path.read_bytes() + b'changed')
    monkeypatch.setattr(execute, 'execution_modules', lambda: pytest.fail('native modules reached after invalid identity'))
    out = task / 'rejected'
    with pytest.raises(ValueError):
        execute.collect_cohort(plan, out)
    assert not out.exists()


@pytest.mark.parametrize('target', ['role_build', 'runner_build'])
def test_new_plan_binds_manifest_bytes_even_when_manifest_internally_valid(tmp_path, target):
    _, plan, _ = preflight_fixture(tmp_path)
    path = Path(plan['identity_bindings'][target]['path'])
    path.write_bytes(path.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='hash differs'):
        execute.preflight_cohort(plan)


def test_preflight_legacy_plan_preserves_original_scope_checks(tmp_path):
    _, plan, _ = preflight_fixture(tmp_path, composed=True)
    del plan['identity_bindings']
    assert execute.preflight_cohort(plan)['identity_binding_mode'] == 'legacy_frozen_scope_and_components'
    plan['calibration_scope']['inputs'] = 'sha256:' + '0' * 64
    with pytest.raises(ValueError, match='input bindings hash differs'):
        execute.preflight_cohort(plan)


def test_preflight_rejects_requested_oracle_substitution_and_unbound_input(tmp_path):
    task, plan, _ = preflight_fixture(tmp_path)
    for row in plan['schedule']:
        row['request']['cases'][0]['verifier'] = str(task / 'other-oracle.py')
    with pytest.raises(ValueError, match='verifier differs'):
        execute.preflight_cohort(plan)
    for row in plan['schedule']:
        row['request']['cases'][0]['verifier'] = str(task / 'baseline/scripts/verify_result.py')
    metadata = Path(plan['schedule'][0]['request']['cases'][0]['metadata'])
    unbound = task / 'unbound.bin'; unbound.write_bytes(b'new input')
    rewrite(metadata, lambda value: value.update(input=str(unbound)))
    binding = task / 'input-bindings.json'
    rewrite(binding, lambda value: value['cases'][0].update(metadata=execute.pointer(metadata)))
    plan['identity_bindings']['input_bindings'] = execute.pointer(binding)
    plan['calibration_scope']['inputs'] = execute.sha(binding)
    with pytest.raises(ValueError, match='unbound input/oracle'):
        execute.preflight_cohort(plan)


def add_frozen_generator(tmp_path, plan, monkeypatch):
    import msprof_exploration_provenance as provenance
    repo = tmp_path / 'repo'
    scripts = repo / 'scripts'; scripts.mkdir()
    generator = scripts / 'msprof_exploration_execute.py'
    generator.write_bytes(b'old engineering source')
    origin = execute.pointer(generator)
    role_path = Path(plan['identity_bindings']['role_build']['path'])
    component_path = Path(execute.load(role_path)['component_builds'][0]['path'])
    rewrite(component_path, lambda value: value.update(campaign_build={'generator': origin}))
    rewrite(role_path, lambda value: value.update(component_builds=[execute.pointer(component_path)] * 2))
    plan['identity_bindings']['role_build'] = execute.pointer(role_path)
    run = repo / '.aprof/runs/level1-msprof-feedback-20260911T000000Z'
    snapshot = run / 'bootstrap/source-cas' / origin['sha256'][7:]
    snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes(generator.read_bytes())
    manifest = run / 'bootstrap/frozen-engineering-01.json'
    execute.save(manifest, {'files': [{**origin, 'snapshot': str(snapshot)}]})
    generator.write_bytes(b'new engineering source')
    monkeypatch.setattr(provenance, 'ENGINEERING_SCRIPTS', scripts)
    monkeypatch.setattr(provenance, 'CAMPAIGN_RUNS', repo / '.aprof/runs')
    return snapshot, manifest


def test_preflight_resolves_frozen_generator_without_accepting_tampered_cas(tmp_path, monkeypatch):
    _, plan, _ = preflight_fixture(tmp_path, composed=True)
    snapshot, manifest = add_frozen_generator(tmp_path, plan, monkeypatch)
    result = execute.preflight_cohort(plan)
    assert result['producer_bindings'] == [{'origin': {'path': str(tmp_path / 'repo/scripts/msprof_exploration_execute.py'),
                                                       'sha256': execute.sha(snapshot)},
                                            'snapshot': execute.pointer(snapshot), 'frozen_manifest': execute.pointer(manifest),
                                            'binding_mode': 'frozen_engineering_snapshot'}]
    snapshot.write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='snapshot hash differs'):
        execute.preflight_cohort(plan)


def test_preflight_rejects_changed_generator_without_explicit_freeze(tmp_path, monkeypatch):
    _, plan, _ = preflight_fixture(tmp_path, composed=True)
    _, manifest = add_frozen_generator(tmp_path, plan, monkeypatch)
    manifest.unlink()
    with pytest.raises(ValueError, match='dependency pointer hash differs'):
        execute.preflight_cohort(plan)


def test_cohort_rechecks_identity_before_each_process_and_records_resolution(tmp_path, monkeypatch):
    import msprof_exploration_report as report
    task, plan, _ = preflight_fixture(tmp_path, composed=True)
    add_frozen_generator(tmp_path, plan, monkeypatch)
    calls = []
    def collect(request, out):
        calls.append(out)
        execute.save(out / 'completion.json', {})
        execute.save(out / 'samples.json', {})
        execute.save(out / 'native/journal.jsonl', {})
        (task / 'baseline/op_kernel/kernel.h').write_bytes(b'changed after first native')
    monkeypatch.setattr(execute, 'execution_modules', lambda: (SimpleNamespace(collect=collect), None, None))
    monkeypatch.setattr(report, 'verify_observation', lambda *args, **kwargs: None)
    monkeypatch.setattr(report, 'analyze_task_cohort', lambda *args, **kwargs: pytest.fail('failed cohort analyzed'))
    out = task / 'cohort'
    with pytest.raises(ValueError, match='source hash differs'):
        execute.collect_cohort(plan, out)
    assert len(calls) == 1
    assert execute.load(out / 'group-completion.json')['status'] == 'failed'
    assert execute.load(out / 'identity-resolution.json')['producer_bindings'][0]['binding_mode'] == 'frozen_engineering_snapshot'
