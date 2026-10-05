"""CPU-only tests of serial continuation admission, lineage and CAS isolation."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from aprof_runtime.errors import StoreError
from aprof_runtime.jsonio import file_hash
from test_finalize_level1_campaign import dump, finalize, fixture_run

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('finalize_level1_serial', ROOT / 'scripts/finalize_level1_serial.py')
serial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serial)


def healthy_operator(run, op):
    for phase in ('before', 'after'):
        dump(run / 'tasks' / op / ('health-' + phase + '.json'), dict(
            argv=['/usr/local/sbin/npu-smi', 'info'], cwd=str(ROOT), host='test-host',
            started_at='2026-09-08T01:00:00Z', finished_at='2026-09-08T01:00:01Z',
            exit_status=0, stdout='No running processes found in NPU\n' * 8,
            stderr='', no_device_processes=True))


def continuation(tmp_path, accepted=True, state='gain'):
    parent = fixture_run(tmp_path / 'parent', (state,))
    parent_finalizer = finalize.Finalizer(parent)
    parent_finalizer.finalize_operator('exp')
    parent_finalizer.export()
    old = finalize.rows(parent / 'train/optimization_traces.jsonl')[0]
    run = tmp_path / 'serial'
    (run / 'setup').mkdir(parents=True)
    producer = run / 'setup/cannbench_device_timing.py'
    producer.write_text('frozen test timing producer\n')
    baseline, candidate = parent / 'tasks/exp/baseline', parent / 'tasks/exp/candidates/001/op'
    for tree in (baseline, candidate):
        (tree / 'build').mkdir(parents=True, exist_ok=True)
        (tree / 'build/exp').write_text(str(tree))
    entry = dict(identifier='001', candidate_id='exp-001',
        source_hashes={k: old['provenance'][k + '_source_hash'] for k in ('baseline', 'candidate')},
        baseline=str(baseline), candidate=str(candidate), prepared_root=str(run / 'prepared'),
        baseline_executable_sha256=file_hash(baseline / 'build/exp'),
        candidate_executable_sha256=file_hash(candidate / 'build/exp'))
    dump(run / 'run-manifest.json', dict(run_id=run.name, parent_run=str(parent), operators=['exp'],
        validation_operators=[], candidates={'exp': [entry]}, created_at='2026-09-08T01:00:00Z'))
    control_paths = []
    for index in range(3):
        control = deepcopy(finalize.read(parent / 'tasks/exp/timing/final/001/raw_measurements.json'))
        control.update(operator='exp', baseline_executable_sha256=entry['baseline_executable_sha256'][7:],
            candidate_executable_sha256=entry['baseline_executable_sha256'][7:])
        control['case_ids'] = [1, 8, 14, 20]
        control['records'] = [x for x in control['records'] if x['case_id'] in control['case_ids']]
        for row in control['records']:
            row['candidate'] = deepcopy(row['baseline'])
        location = run / 'tasks/exp/calibration' / str(index)
        dump(location / 'raw_measurements.json', control)
        dump(location / 'measurement_report.json', serial.summarize_multicase(control, control['case_ids']))
        dump(location / 'execution.json', {'exit_status': 0})
        control_paths.append(str(location / 'measurement_report.json'))
    dump(run / 'tasks/exp/calibration-decision.json', dict(accepted=accepted,
        reason='A/A controls passed' if accepted else 'Post-batch role bias exceeds 2%', artifact_paths=control_paths))
    healthy_operator(run, 'exp')
    directory = run / 'tasks/exp/measurements/001'
    raw = deepcopy(finalize.read(parent / 'tasks/exp/timing/final/001/raw_measurements.json'))
    raw.update(operator='exp', host='test-host', producer_sha256=file_hash(producer)[7:],
        baseline_executable_sha256=entry['baseline_executable_sha256'][7:],
        candidate_executable_sha256=entry['candidate_executable_sha256'][7:], case_executions=[])
    for case in range(1, 21):
        metadata = run / 'prepared' / str(case) / 'metadata.json'
        dump(metadata, {'case_id': case})
        raw['case_executions'].append(dict(case_id=case, metadata_path=str(metadata),
            metadata_sha256=file_hash(metadata)[7:], input_hashes={}, exit_status=0))
        for label in ('baseline', 'candidate'):
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f'case-{case:02d}-{label}-verify.log').write_text('output verification passed\n')
    dump(directory / 'raw_measurements.json', raw)
    dump(directory / 'measurement_report.json', serial.summarize_multicase(raw))
    dump(directory / 'execution.json', dict(source_binding=entry, exit_status=0,
        timing_producer_sha256=file_hash(producer)))
    return run, parent


def test_calibration_rejection_preserves_raw_unknown_gain_and_full_lineage(tmp_path):
    run, parent = continuation(tmp_path, accepted=False)
    before = {p: p.read_bytes() for p in parent.rglob('*') if p.is_file()}
    result = serial.SerialFinalizer(run).run_export()
    record = finalize.rows(run / 'train/optimization_traces.jsonl')[0]
    assert record['identity']['run_id'] == run.name
    assert record['identity']['attempt_id'] == record['identity']['parent_attempt_id'] == 'exp-001'
    assert record['result']['verdict'] == 'measurement_unstable'
    assert record['result']['speedup'] is record['result']['speedup_lcb'] is None
    request = finalize.read(run / 'tasks/exp/exploration_request.json')
    assert request['evidence'][0]['baseline_samples_ns'] == []
    report = result['operators'][0]['attempts'][0]
    assert report['per_case'][0]['pair_count'] == 30
    assert report['per_case'][0]['baseline_samples_ns'] == [100.] * 30
    assert report['validation']['correctness']['status'] == 'passed'
    assert result['operators'][0]['best_source']['candidate_id'] is None
    assert (run / 'tasks/exp/best_source/op_kernel/kernel.asc').read_text() == 'baseline'
    assert (run / 'episodes.jsonl').read_bytes() == b''
    assert before == {p: p.read_bytes() for p in parent.rglob('*') if p.is_file()}
    assert serial.SerialFinalizer(run).verify()['valid']


def test_machine_gate_qualified_selection_retry_and_cas_tampering(tmp_path):
    run, parent = continuation(tmp_path)
    finalizer = serial.SerialFinalizer(run)
    result = finalizer.run_export()
    assert result['operators'][0]['best_source']['candidate_id'] == 'exp-001'
    record = finalize.rows(run / 'optimization_traces.jsonl')[0]
    assert record['result']['verdict'] == 'production_safe_gain'
    assert record['result']['speedup'] == pytest.approx(1.25)
    assert record['result']['graph_policy_eligible'] is False
    assert record['result']['episode_ref'] is None
    before = (run / 'trace_events.jsonl').read_bytes()
    assert finalizer.run_export() == result
    assert (run / 'trace_events.jsonl').read_bytes() == before
    digest = record['provenance']['candidate_source_hash']
    with serial.ExportStore(run / 'train/episodes.sqlite') as store:
        path = store.verify_artifact(digest)
        parent_path = parent / 'train/episodes.sqlite.objects/sha256' / digest[7:9] / digest[9:]
        old_parent = parent_path.read_bytes()
        path.write_bytes(b'tampered')
        with pytest.raises(StoreError, match='content does not match'):
            store.verify_artifact(digest)
        assert parent_path.read_bytes() == old_parent
    with pytest.raises(StoreError):
        serial.SerialFinalizer(run).verify()


def test_forged_report_and_missing_candidate_rejected(tmp_path):
    run, _ = continuation(tmp_path)
    p = run / 'tasks/exp/measurements/001/measurement_report.json'
    report = finalize.read(p)
    report['gate_projection']['candidate_samples_ns'][0] = 1
    dump(p, report)
    with pytest.raises(StoreError, match='does not reproduce'):
        serial.SerialFinalizer(run).run_export()
    manifest = finalize.read(run / 'run-manifest.json')
    manifest['candidates']['exp'] = []
    dump(run / 'run-manifest.json', manifest)
    with pytest.raises(StoreError, match='entire parent candidate roster'):
        serial.SerialFinalizer(run)


def test_new_incomplete_correctness_does_not_inherit_parent_pass(tmp_path):
    run, _ = continuation(tmp_path)
    p = run / 'tasks/exp/measurements/001/raw_measurements.json'
    raw = finalize.read(p)
    raw['case_executions'][19]['exit_status'] = 1
    dump(p, raw)
    result = serial.SerialFinalizer(run).run_export()
    item = result['operators'][0]['attempts'][0]
    assert item['result']['verdict'] == 'accuracy_failed'
    assert item['validation']['passed_count'] == 19
    assert item['result']['speedup'] is None
    assert item['measurement_admitted'] is False


def test_performance_source_is_separate_from_unknown_attribution(tmp_path):
    run, _ = continuation(tmp_path, state='unattributed')
    result = serial.SerialFinalizer(run).run_export()
    op = result['operators'][0]
    assert op['attempts'][0]['result']['verdict'] == 'attribution_uncertain'
    assert op['best_source']['candidate_id'] is None
    assert op['measured_best_source']['candidate_id'] == 'exp-001'
    assert op['measured_best_source']['production_safe'] is False
    assert (run / 'tasks/exp/measured_best_source/op_kernel/kernel.asc').read_text() == 'exp-001'
    path = run / 'tasks/exp/measurements/001/raw_measurements.json'
    raw = finalize.read(path)
    for row in raw['records']:
        row['candidate']['elapsed_ns'] = 70.0
    dump(path, raw)
    dump(path.parent / 'measurement_report.json', serial.summarize_multicase(raw))
    with pytest.raises(StoreError, match='differs from sealed'):
        serial.SerialFinalizer(run).verify()


def test_accepted_control_cannot_hide_an_unstable_raw_control(tmp_path):
    run, _ = continuation(tmp_path)
    path = run / 'tasks/exp/calibration/0/raw_measurements.json'
    raw = finalize.read(path)
    raw['complete'] = False
    dump(path, raw)
    dump(path.parent / 'measurement_report.json', serial.summarize_multicase(raw, raw['case_ids']))
    with pytest.raises(StoreError, match='accepted calibration does not replay'):
        serial.SerialFinalizer(run).run_export()


def test_timing_interruption_does_not_invent_failed_output_verification(tmp_path):
    run, _ = continuation(tmp_path)
    directory = run / 'tasks/exp/measurements/001'
    raw = finalize.read(directory / 'raw_measurements.json')
    raw['case_executions'] = []
    raw['complete'] = False
    raw['error'] = {'type': 'TimeoutError', 'message': 'Timing child stopped responding'}
    dump(directory / 'raw_measurements.json', raw)
    dump(directory / 'measurement_report.json', serial.summarize_multicase(raw))
    execution = finalize.read(directory / 'execution.json')
    execution['exit_status'] = 1
    dump(directory / 'execution.json', execution)
    item = serial.SerialFinalizer(run).run_export()['operators'][0]['attempts'][0]
    assert item['validation']['correctness']['status'] == 'interrupted'
    assert item['validation']['passed_count'] == 0
    assert item['validation']['runtime']['status'] == 'failed'
    assert item['result']['speedup'] is None


def harness_entry(tmp_path, store):
    """Small self-describing snapshots exercise the real source boundary."""
    import difflib
    import shutil
    from prepare_trace_pilot import create_source_snapshot
    entry = dict(candidate_id='exp-001', source_hashes={}, measurement_source_binding=dict(
        kind='harness_only_measurement_continuation', allowed_changed_paths=[serial.TIMER_HEADER]))
    for label in ('baseline', 'candidate'):
        original = tmp_path / ('original-' + label)
        tree = tmp_path / ('measurement-' + label)
        for relative, payload in {'op_kernel/exp.asc': 'kernel ' + label + '\n',
                serial.TIMER_HEADER: '#define DIRECT_TIMING 1\n',
                'scripts/verify_result.py': '# protected original precision oracle\n',
                'CMakeLists.txt': 'project(exp)\n'}.items():
            path = original / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload)
        source = tmp_path / (label + '-old.tar')
        create_source_snapshot(original, source, root_label='exp/source')
        entry['source_hashes'][label] = store.install(source)
        shutil.copytree(original, tree)
        header = tree / serial.TIMER_HEADER
        before = header.read_text()
        after = before + '#define CAPTURE_REPLAY_AVAILABLE 1\n'
        header.write_text(after)
        (tree / 'build').mkdir()
        (tree / 'build/exp').write_bytes(b'test executable')
        snapshot = tmp_path / (label + '-measurement.tar')
        create_source_snapshot(tree, snapshot, root_label='exp/source')
        patch = tmp_path / (label + '-harness.patch')
        patch.write_text(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
            fromfile='a/' + serial.TIMER_HEADER, tofile='b/' + serial.TIMER_HEADER)))
        entry[label] = str(tree)
        entry[label + '_executable_sha256'] = file_hash(tree / 'build/exp')
        entry['measurement_source_binding'][label] = dict(source_snapshot_path=str(snapshot),
            source_snapshot_sha256=file_hash(snapshot), harness_patch_path=str(patch), harness_patch_sha256=file_hash(patch))
    return entry


def test_harness_only_source_snapshots_and_exact_header_patch(tmp_path):
    with serial.ExportStore(tmp_path / 'episodes.sqlite') as store:
        entry = harness_entry(tmp_path, store)
        original_hashes = deepcopy(entry['source_hashes'])
        artifacts = serial.verify_measurement_sources(entry, store)
        assert entry['source_hashes'] == original_hashes
        assert artifacts['measurement_baseline_source_snapshot'] != original_hashes['baseline']
        verification = json.loads(store.verify_artifact(artifacts['measurement_source_verification']).read_text())
        assert verification['new_optimization_attempt'] is False
        assert verification['comparisons']['candidate']['changed_source_paths'] == [serial.TIMER_HEADER]
        assert verification['comparisons']['candidate']['precision_verifier_unchanged'] is True
        assert serial.verify_measurement_sources(entry, store) == artifacts


@pytest.mark.parametrize('mutation', ['oracle', 'kernel', 'mode', 'extra', 'deleted', 'patch', 'excludes', 'symlink'])
def test_harness_binding_cannot_hide_other_source_changes(tmp_path, mutation):
    from prepare_trace_pilot import create_source_snapshot, DEFAULT_EXCLUDES
    with serial.ExportStore(tmp_path / 'episodes.sqlite') as store:
        entry = harness_entry(tmp_path, store)
        tree = Path(entry['candidate'])
        declared = entry['measurement_source_binding']['candidate']
        if mutation == 'oracle':
            (tree / 'scripts/verify_result.py').write_text('# weakened checker\n')
        elif mutation == 'kernel':
            (tree / 'op_kernel/exp.asc').write_text('changed optimization source\n')
        elif mutation == 'mode':
            (tree / 'op_kernel/exp.asc').chmod(0o755)
        elif mutation == 'extra':
            (tree / 'op_kernel/extra.asc').write_text('unexpected source\n')
        elif mutation == 'deleted':
            (tree / 'CMakeLists.txt').unlink()
        elif mutation == 'patch':
            path = Path(declared['harness_patch_path'])
            path.write_text('wrong patch\n')
            declared['harness_patch_sha256'] = file_hash(path)
        elif mutation == 'symlink':
            path = tree / 'op_kernel/exp.asc'
            path.unlink()
            path.symlink_to(tmp_path / 'original-candidate/op_kernel/exp.asc')
        if mutation not in ('patch', 'symlink'):
            # Even an internally consistent forged new snapshot must not be
            # allowed to alter the immutable optimization-source boundary.
            snapshot = tmp_path / 'changed-measurement.tar'
            create_source_snapshot(tree, snapshot, root_label='exp/source',
                excludes=DEFAULT_EXCLUDES + (('scripts/*',) if mutation == 'excludes' else ()))
            declared['source_snapshot_path'] = str(snapshot)
            declared['source_snapshot_sha256'] = file_hash(snapshot)
        with pytest.raises(StoreError):
            serial.verify_measurement_sources(entry, store)


def test_method_parent_chain_is_context_and_never_an_extra_candidate(tmp_path):
    run, _ = continuation(tmp_path)
    first = tmp_path / 'legacy-method'
    second = tmp_path / 'capture-method'
    dump(first / 'run-manifest.json', {'kind': 'serial_method_study'})
    dump(first / 'calibration/selection.json', {'accepted': False, 'reason': 'Unstable A/A role bias'})
    dump(second / 'run-manifest.json', {'kind': 'measurement_method_AA_probe', 'method_parent_run': str(first)})
    dump(second / 'selection.json', {'accepted': True, 'reason': 'Synthetic method control passed'})
    manifest = finalize.read(run / 'run-manifest.json')
    manifest['method_parent_run'] = str(second)
    dump(run / 'run-manifest.json', manifest)
    result = serial.SerialFinalizer(run).run_export()
    assert result['attempt_count'] == 1
    assert result['new_source_attempt_count'] == 0
    events = finalize.rows(run / 'trace_events.jsonl')
    method_events = [x for x in events if x['payload'].get('action') == 'record_measurement_method_history']
    assert len(method_events) == 1
    assert method_events[0]['attempt_id'] is None
    assert method_events[0]['candidate_id'] is None
    assert serial.SerialFinalizer(run).verify()['valid']
    changed = finalize.read(first / 'calibration/selection.json')
    changed['accepted'] = True
    dump(first / 'calibration/selection.json', changed)
    with pytest.raises(StoreError, match='method exploration history differs'):
        serial.SerialFinalizer(run).verify()


def test_capture_binding_rejects_legacy_samples_without_losing_observations(tmp_path):
    run, _ = continuation(tmp_path / 'run')
    with serial.ExportStore(tmp_path / 'store/episodes.sqlite') as store:
        directory = tmp_path / 'harness'
        directory.mkdir()
        entry = harness_entry(directory, store)
        entry['identifier'] = '001'
        execution_path = run / 'tasks/exp/measurements/001/execution.json'
        execution = finalize.read(execution_path)
        execution['source_binding'] = entry
        dump(execution_path, execution)
        raw_path = execution_path.parent / 'raw_measurements.json'
        raw = finalize.read(raw_path)
        for label in ('baseline', 'candidate'):
            raw[label + '_executable_sha256'] = entry[label + '_executable_sha256'][7:]
        dump(raw_path, raw)
        dump(raw_path.parent / 'measurement_report.json', serial.summarize_multicase(raw))
        finalizer = serial.SerialFinalizer(run)
        finalizer.manifest['capture_replay'] = True
        measurement = finalizer.measurement('exp', entry, store, {'accepted': True, 'reason': 'CPU synthetic control',
            'operator_health': finalizer.operator_health('exp', store)[0]})
        assert measurement['observed']['per_case'][0]['pair_count'] == 30
        assert measurement['admitted']['stable'] is False
        assert measurement['admitted']['speedup'] is None
        assert measurement['admitted']['gate_projection']['baseline_samples_ns'] == []
        assert any('mode differs' in reason for reason in measurement['admitted']['reasons'])


def test_capture_and_reused_verifier_binding_admits_only_declared_samples(tmp_path):
    run, _ = continuation(tmp_path / 'run')
    with serial.ExportStore(tmp_path / 'store/episodes.sqlite') as store:
        directory = tmp_path / 'harness'
        directory.mkdir()
        entry = harness_entry(directory, store)
        entry['identifier'] = '001'
        location = run / 'tasks/exp/measurements/001'
        execution = finalize.read(location / 'execution.json')
        execution['source_binding'] = entry
        dump(location / 'execution.json', execution)
        raw = finalize.read(location / 'raw_measurements.json')
        raw.update(capture_replay=True, execution_mode='acl_graph_replay', repeat=100,
            captured_operator_calls=100, timing_scope='complete_operator_device_graph_event_interval',
            verification_protocol='in_process_reuse_v1',
            verifier_source_hash=file_hash(Path(entry['baseline']) / 'scripts/verify_result.py'))
        for label in ('baseline', 'candidate'):
            raw[label + '_executable_sha256'] = entry[label + '_executable_sha256'][7:]
        for row in raw['records']:
            for label in ('baseline', 'candidate'):
                row[label].update(repeat=100, execution_mode='acl_graph_replay', captured_operator_calls=100)
        for case in raw['case_executions']:
            case['verifications'] = {label: {'exit_status': 0} for label in ('baseline', 'candidate')}
        dump(location / 'raw_measurements.json', raw)
        dump(location / 'measurement_report.json', serial.summarize_multicase(raw))
        finalizer = serial.SerialFinalizer(run)
        finalizer.manifest.update(capture_replay=True, reuse_verifier=True)
        calibration = {'accepted': True, 'reason': 'CPU synthetic control',
            'operator_health': finalizer.operator_health('exp', store)[0]}
        current = finalizer.measurement('exp', entry, store, calibration)
        assert current['admitted']['stable']
        assert current['correctness']['passed_count'] == 20
        assert current['correctness']['verifier_protocol'] == 'in_process_reuse_v1'
        raw['records'][0]['candidate']['captured_operator_calls'] = 99
        dump(location / 'raw_measurements.json', raw)
        dump(location / 'measurement_report.json', serial.summarize_multicase(raw))
        current = finalizer.measurement('exp', entry, store, calibration)
        assert not current['admitted']['stable']
        assert current['admitted']['speedup'] is None
        assert current['observed']['per_case'][0]['baseline_samples_ns']
        raw['records'][0]['candidate']['captured_operator_calls'] = 100
        raw['case_executions'][0]['verifications'].pop('candidate')
        dump(location / 'raw_measurements.json', raw)
        dump(location / 'measurement_report.json', serial.summarize_multicase(raw))
        current = finalizer.measurement('exp', entry, store, calibration)
        assert current['correctness']['passed_count'] == 19
        assert current['correctness']['status'] == 'interrupted'
        assert not current['admitted']['stable']


def test_aa_admission_cannot_be_borrowed_from_another_execution_mode(tmp_path):
    run, _ = continuation(tmp_path)
    finalizer = serial.SerialFinalizer(run)
    finalizer.manifest['capture_replay'] = True
    with serial.ExportStore(tmp_path / 'new-store/episodes.sqlite') as store:
        with pytest.raises(StoreError, match='different capture/replay mode'):
            finalizer.calibration('exp', store)


def add_single_context_evidence(raw, entry, directory, reverse=False):
    """Attach the collector's complete, sequential process-lifecycle evidence."""
    raw.update(single_live_context=True, context_lifecycle='one_process_per_role_sample',
        verification_output_scope='last_process_output_per_role', pairs=30, warmup=10, repeat=100,
        precondition_samples=1, reverse_startup=reverse, checkpoint_every_pair=False,
        verification_protocol='in_process_reuse_v1', host='test-host',
        verifier_source_hash=file_hash(Path(entry['baseline']) / 'scripts/verify_result.py'))
    old_executions = {x['case_id']: x for x in raw.get('case_executions', [])}
    raw['case_executions'] = []
    for case in raw['case_ids']:
        base = case * 10000
        commands = {label: dict(argv=[str(Path(entry[label]) / 'build/exp'), '--output',
            str(directory / f'case-{case:02d}-{label}.bin')], cwd=entry[label]) for label in ('baseline', 'candidate')}
        execution = old_executions.get(case, {'case_id': case})
        execution.pop('startup_order', None)
        execution.update(context_lifecycle=raw['context_lifecycle'], commands=commands, started_at=base,
            finished_at=base+200, exit_status=0, context_sessions=[],
            verifications={label: dict(started_at=base+180, finished_at=base+190, exit_status=0)
                           for label in ('baseline', 'candidate')})
        for row in [r for r in raw['records'] if r['case_id'] == case]:
            row.update(context_lifecycle=raw['context_lifecycle'], host=raw['host'], device=0,
                order=['candidate', 'baseline'] if bool(row['round'] % 2) ^ reverse else ['baseline', 'candidate'],
                preconditioning={})
            for label in row['order']:
                row[label].update(operator='exp', warmup=10, repeat=100, sample_index=1)
                row['preconditioning'][label] = [dict(row[label], sample_index=0, elapsed_ns=1e9)]
                position = len(execution['context_sessions'])
                start = base + 2 * position
                log_path = directory / f'case-{case:02d}-round-{row["round"]:03d}-{label}.log'
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text('Synthetic timing process completed\n')
                execution['context_sessions'].append(dict(round=row['round'], label=label, **commands[label],
                    log_path=str(log_path), started_at=start, finished_at=start+1,
                    started_monotonic_ns=start*1000000000, finished_monotonic_ns=(start+1)*1000000000,
                    pid=100+position, exit_status=0, preconditioning_sample_indices=[0], formal_sample_index=1))
        raw['case_executions'].append(execution)
    return raw


def single_continuation(tmp_path, reverse=False):
    run, parent = continuation(tmp_path)
    manifest = finalize.read(run / 'run-manifest.json')
    manifest.update(single_live_context=True, capture_replay=False, reuse_verifier=True)
    entry = manifest['candidates']['exp'][0]
    verifier = Path(entry['baseline']) / 'scripts/verify_result.py'
    verifier.parent.mkdir(parents=True, exist_ok=True)
    verifier.write_text('# CPU fixture original verifier\n')
    dump(run / 'run-manifest.json', manifest)
    measurement = run / 'tasks/exp/measurements/001'
    raw = add_single_context_evidence(finalize.read(measurement / 'raw_measurements.json'), entry, measurement, reverse)
    dump(measurement / 'raw_measurements.json', raw)
    dump(measurement / 'measurement_report.json', serial.summarize_multicase(raw))
    for index in range(3):
        directory = run / 'tasks/exp/calibration' / str(index)
        raw = add_single_context_evidence(finalize.read(directory / 'raw_measurements.json'), entry, directory, index == 1)
        # A/A executes the frozen baseline in both roles.
        for execution in raw['case_executions']:
            execution['commands']['candidate']['argv'][0] = str(Path(entry['baseline']) / 'build/exp')
            execution['commands']['candidate']['cwd'] = entry['baseline']
            for session in execution['context_sessions']:
                if session['label'] == 'candidate':
                    session['argv'] = execution['commands']['candidate']['argv']
                    session['cwd'] = entry['baseline']
        dump(directory / 'raw_measurements.json', raw)
        dump(directory / 'measurement_report.json', serial.summarize_multicase(raw, raw['case_ids']))
    return run, parent


def test_single_context_exports_original_source_identity_and_only_final_output_scope(tmp_path):
    run, _ = single_continuation(tmp_path, reverse=True)
    entry = finalize.read(run / 'run-manifest.json')['candidates']['exp'][0]
    assert 'measurement_source_binding' not in entry
    result = serial.SerialFinalizer(run).run_export()
    item = result['operators'][0]['attempts'][0]
    assert item['measurement_admitted'] is True
    assert item['result']['speedup'] == pytest.approx(1.25)
    assert 'Only the last process output' in item['validation']['correctness']['reason']
    record = finalize.rows(run / 'optimization_traces.jsonl')[0]
    assert record['provenance']['candidate_source_hash'] == entry['source_hashes']['candidate']
    assert record['identity']['attempt_id'] == record['identity']['parent_attempt_id'] == 'exp-001'
    assert record['result']['graph_policy_eligible'] is False
    assert serial.SerialFinalizer(run).verify()['valid']


def test_single_context_overlap_and_missing_log_preserve_raw_but_admit_no_gain(tmp_path):
    run, _ = single_continuation(tmp_path)
    path = run / 'tasks/exp/measurements/001/raw_measurements.json'
    raw = finalize.read(path)
    sessions = raw['case_executions'][0]['context_sessions']
    sessions[1]['started_monotonic_ns'] = sessions[0]['finished_monotonic_ns'] - 1
    Path(sessions[2]['log_path']).unlink()
    dump(path, raw)
    dump(path.parent / 'measurement_report.json', serial.summarize_multicase(raw))
    result = serial.SerialFinalizer(run).run_export()
    item = result['operators'][0]['attempts'][0]
    assert item['result']['verdict'] == 'measurement_unstable'
    assert item['result']['speedup'] is None
    assert item['per_case'][0]['pair_count'] == 30
    assert any('overlapping' in r for r in item['lesson']['limitations'])
    assert any('missing its archived execution log' in r for r in item['lesson']['limitations'])


def test_single_context_cannot_borrow_resident_context_calibration(tmp_path):
    run, _ = continuation(tmp_path)
    finalizer = serial.SerialFinalizer(run)
    finalizer.manifest['single_live_context'] = True
    with serial.ExportStore(tmp_path / 'new-store/episodes.sqlite') as store:
        with pytest.raises(StoreError, match='different single-live-context lifecycle'):
            finalizer.calibration('exp', store)


def multi_operator_continuation(tmp_path):
    """Three real frozen exploration batches, with one validation operator."""
    import shutil
    from aprof_runtime.store import EpisodeStore
    from aprof_runtime.traces import GENESIS
    parent = fixture_run(tmp_path / 'parent', ('build_failed',))
    manifest = finalize.read(parent / 'run-manifest.json')
    manifest.update(operators=['exp', 'mish', 'gelu'], train_operators=['exp', 'mish'], validation_operators=['gelu'])
    dump(parent / 'run-manifest.json', manifest)
    with EpisodeStore(parent / 'train/episodes.sqlite') as store:
        for op in ('mish', 'gelu'):
            task = parent / 'tasks' / op
            shutil.copytree(parent / 'tasks/exp', task)
            directory = task / 'candidates/001'
            plan = finalize.read(directory / 'candidate_plan.json')
            plan['candidate_id'] = op + '-001'
            dump(directory / 'candidate_plan.json', plan)
            registration = finalize.read(directory / 'registration.json')
            registration.update(candidate_id=op + '-001', plan_hash=store.register_artifact(directory / 'candidate_plan.json'))
            dump(directory / 'registration.json', registration)
            roster = finalize.read(task / 'frozen-roster.json')
            roster['candidates'] = [{**registration, 'frozen_plan_sha256': file_hash(directory / 'candidate_plan.json')}]
            dump(task / 'frozen-roster.json', roster)
            events = finalize.rows(task / 'trace_events.jsonl')
            previous = GENESIS
            for index, event in enumerate(events):
                event.update(task_id=op, session_id=op + '-campaign', candidate_id=op + '-001',
                    attempt_id=op + '-001', event_id=op + '-original-' + str(index), previous_event_hash=previous)
                event['event_hash'] = serial.content_hash({k: v for k, v in event.items() if k != 'event_hash'})
                previous = event['event_hash']
            (task / 'trace_events.jsonl').write_text(''.join(serial.canonical_json(x) + '\n' for x in events))
        with EpisodeStore(parent / 'validation/episodes.sqlite') as validation:
            for (digest,) in store.connection.execute('SELECT content_hash FROM artifacts'):
                validation.register_artifact(store.object_path(digest))
    old = finalize.Finalizer(parent)
    for op in manifest['operators']:
        old.finalize_operator(op)
    old.export()
    run = tmp_path / 'incremental'
    entries = {}
    for split in ('train', 'validation'):
        for record in finalize.rows(parent / split / 'optimization_traces.jsonl'):
            op = record['identity']['operator']
            entries[op] = [dict(identifier='001', candidate_id=op + '-001',
                source_hashes={label: record['provenance'][label + '_source_hash'] for label in ('baseline', 'candidate')},
                baseline=str(parent / 'tasks' / op / 'baseline'), candidate=str(parent / 'tasks' / op / 'candidates/001/op'),
                baseline_executable_sha256='sha256:' + '1' * 64, candidate_executable_sha256='sha256:' + '2' * 64)]
    dump(run / 'run-manifest.json', dict(run_id=run.name, parent_run=str(parent), operators=manifest['operators'],
        validation_operators=['gelu'], candidates=entries, created_at='2026-09-08T01:00:00Z'))
    return run


def close_blocked_operator(run, op):
    dump(run / 'tasks' / op / 'calibration-decision.json', dict(accepted=False,
        reason='CPU fixture calibration closed without timing admission.', artifact_paths=[]))
    healthy_operator(run, op)


def test_ready_only_zero_completed_exports_empty_streams_and_pending_roster(tmp_path):
    run = multi_operator_continuation(tmp_path)
    finalizer = serial.SerialFinalizer(run)
    progress = finalizer.run_export(ready_only=True)
    assert progress['attempt_count'] == 0
    assert progress['frozen_candidate_count'] == 3
    assert progress['completed_operators'] == []
    assert progress['pending_operators'] == ['exp', 'mish', 'gelu']
    assert not (run / 'serial_summary.json').exists()
    assert not (run / 'serial_report.md').exists()
    for prefix in ('', 'train', 'validation'):
        for name in ('optimization_traces.jsonl', 'trace_events.jsonl', 'episodes.jsonl'):
            assert (run / prefix / name).read_bytes() == b''
    assert not list((run / 'tasks').glob('*/trace_events.jsonl')) if (run / 'tasks').exists() else True
    assert finalizer.verify(ready_only=True)['attempt_count'] == 0
    before = (run / 'serial_progress.json').read_bytes()
    assert finalizer.run_export(ready_only=True) == progress
    assert (run / 'serial_progress.json').read_bytes() == before
    with pytest.raises(StoreError, match='all operators to close'):
        finalizer.run_export()


def test_ready_only_out_of_order_addition_preserves_prefixes_and_reuses_sealed_ops(tmp_path, monkeypatch):
    run = multi_operator_continuation(tmp_path)
    finalizer = serial.SerialFinalizer(run)
    close_blocked_operator(run, 'gelu')
    first = finalizer.run_export(ready_only=True)
    assert first['completed_operators'] == ['gelu']
    assert first['attempt_count'] == 1
    closed_files = {p: p.read_bytes() for p in (run / 'tasks/gelu').rglob('*') if p.is_file()}
    root_prefixes = {name: (run / name).read_bytes() for name in ('optimization_traces.jsonl', 'trace_events.jsonl', 'episodes.jsonl')}
    original = finalizer.finalize_operator
    finalized = []
    def only_new(op, store, closure):
        finalized.append(op)
        assert op != 'gelu', 'sealed operators must reuse their verified report'
        return original(op, store, closure)
    monkeypatch.setattr(finalizer, 'finalize_operator', only_new)
    close_blocked_operator(run, 'mish')
    second = finalizer.run_export(ready_only=True)
    assert finalized == ['mish']
    assert second['attempt_count'] == 2
    assert second['pending_operators'] == ['exp']
    assert [x['identity']['operator'] for x in finalize.rows(run / 'optimization_traces.jsonl')] == ['gelu', 'mish']
    assert closed_files == {p: p.read_bytes() for p in (run / 'tasks/gelu').rglob('*') if p.is_file()}
    for name, prefix in root_prefixes.items():
        assert (run / name).read_bytes().startswith(prefix)
    train_prefixes = {name: (run / 'train' / name).read_bytes() for name in root_prefixes}
    close_blocked_operator(run, 'exp')
    third = finalizer.run_export(ready_only=True)
    assert third['status'] == 'ready_for_final_export'
    assert third['attempt_count'] == 3
    for name, prefix in train_prefixes.items():
        assert (run / 'train' / name).read_bytes().startswith(prefix)
    assert not (run / 'serial_summary.json').exists()
    assert finalizer.verify(ready_only=True)['attempt_count'] == 3
    final = finalizer.run_export()
    assert final['attempt_count'] == 3
    assert finalizer.verify()['valid']
    assert (run / 'serial_summary.json').exists()
    for op in ('exp', 'mish', 'gelu'):
        assert (run / 'tasks' / op / 'episodes.jsonl').read_bytes() == b''
        assert (run / 'tasks' / op / 'serial_report.md').exists()
    before = (run / 'serial_summary.json').read_bytes()
    finalizer.run_export(ready_only=True)
    assert (run / 'serial_summary.json').read_bytes() == before


def test_ready_only_pending_measurement_is_not_a_failed_candidate(tmp_path):
    run, _ = continuation(tmp_path)
    path = run / 'tasks/exp/measurements/001/execution.json'
    path.unlink()
    result = serial.SerialFinalizer(run).run_export(ready_only=True)
    assert result['pending_operators'] == ['exp']
    assert result['attempt_count'] == 0
    assert not (run / 'tasks/exp/exploration_request.json').exists()
    assert (run / 'optimization_traces.jsonl').read_bytes() == b''


def test_ready_only_refuses_changes_to_sealed_evidence(tmp_path):
    run, _ = continuation(tmp_path)
    finalizer = serial.SerialFinalizer(run)
    finalizer.run_export(ready_only=True)
    before = (run / 'optimization_traces.jsonl').read_bytes()
    path = run / 'tasks/exp/measurements/001/raw_measurements.json'
    raw = finalize.read(path)
    raw['records'][0]['candidate']['elapsed_ns'] = 81.0
    dump(path, raw)
    dump(path.parent / 'measurement_report.json', serial.summarize_multicase(raw))
    with pytest.raises(StoreError, match='differs from sealed'):
        finalizer.run_export(ready_only=True)
    assert (run / 'optimization_traces.jsonl').read_bytes() == before


@pytest.mark.parametrize('phase', ['before', 'after'])
def test_ready_only_waits_for_complete_operator_health(tmp_path, phase):
    run, _ = continuation(tmp_path)
    path = run / 'tasks/exp' / ('health-' + phase + '.json')
    complete = finalize.read(path)
    path.unlink()
    finalizer = serial.SerialFinalizer(run)
    for record in (None, {**complete, 'finished_at': ''}):
        if record is not None:
            dump(path, record)
        progress = finalizer.run_export(ready_only=True)
        assert progress['completed_operators'] == []
        assert progress['pending_operators'] == ['exp']
        assert (run / 'optimization_traces.jsonl').read_bytes() == b''
        assert not (run / 'tasks/exp/exploration_request.json').exists()
    dump(path, complete)
    assert finalizer.run_export(ready_only=True)['attempt_count'] == 1


@pytest.mark.parametrize('exit_status,empty_tables,declared', [(1, 8, True), (0, 7, True), (0, 8, False)])
def test_failed_operator_health_preserves_raw_but_blocks_performance(tmp_path, exit_status, empty_tables, declared):
    run, _ = continuation(tmp_path)
    path = run / 'tasks/exp/health-after.json'
    health = finalize.read(path)
    health.update(exit_status=exit_status, stdout='No running processes found in NPU\n' * empty_tables,
        no_device_processes=declared)
    dump(path, health)
    finalizer = serial.SerialFinalizer(run)
    summary = finalizer.run_export()
    operator = summary['operators'][0]
    item = operator['attempts'][0]
    assert item['calibration_accepted'] is True
    assert item['operator_health_accepted'] is False
    assert item['measurement_admitted'] is False
    assert item['result']['speedup'] is item['result']['speedup_lcb'] is None
    assert item['per_case'][0]['pair_count'] == 30
    assert 'Operator health rejected admission' in item['validation']['timing']['reason']
    assert operator['best_source']['candidate_id'] is None
    assert operator['measured_best_source']['candidate_id'] is None
    assert finalizer.verify()['valid']


def test_sealed_operator_health_is_bound_to_current_artifact_bytes(tmp_path):
    run, _ = continuation(tmp_path)
    finalizer = serial.SerialFinalizer(run)
    finalizer.run_export(ready_only=True)
    request = finalize.read(run / 'tasks/exp/exploration_request.json')
    for phase in ('before', 'after'):
        assert request['evidence'][0]['artifacts']['operator_health_' + phase] == file_hash(
            run / 'tasks/exp' / ('health-' + phase + '.json'))
    before = (run / 'optimization_traces.jsonl').read_bytes()
    path = run / 'tasks/exp/health-after.json'
    health = finalize.read(path)
    health['stdout'] += 'Changed health metadata; empty-table count remains eight.\n'
    dump(path, health)
    with pytest.raises(StoreError, match='operator health or calibration differs from sealed'):
        finalizer.verify(ready_only=True)
    with pytest.raises(StoreError, match='operator health or calibration differs from sealed'):
        finalizer.run_export(ready_only=True)
    assert (run / 'optimization_traces.jsonl').read_bytes() == before


def declared_location_continuation(tmp_path):
    run, parent = continuation(tmp_path)
    manifest = finalize.read(run / 'run-manifest.json')
    manifest.update(host='test-host', physical_device=0, logical_device=0)
    dump(run / 'run-manifest.json', manifest)
    for name, start, finish in [('calibration/0', '01:01:00', '01:02:00'),
            ('calibration/1', '01:02:00', '01:03:00'), ('measurements/001', '01:03:00', '01:04:00'),
            ('calibration/2', '01:04:00', '01:05:00')]:
        path = run / 'tasks/exp' / name
        execution = finalize.read(path / 'execution.json')
        execution.update(host='test-host', physical_device=0, logical_device=0,
            started_at='2026-09-08T' + start + 'Z', finished_at='2026-09-08T' + finish + 'Z')
        dump(path / 'execution.json', execution)
        raw = finalize.read(path / 'raw_measurements.json')
        raw.update(host='test-host', device=0)
        dump(path / 'raw_measurements.json', raw)
        dump(path / 'measurement_report.json', serial.summarize_multicase(raw, raw['case_ids']))
    path = run / 'tasks/exp/health-after.json'
    health = finalize.read(path)
    health.update(started_at='2026-09-08T01:05:00Z', finished_at='2026-09-08T01:05:01Z')
    dump(path, health)
    return run, parent


def test_declared_health_host_and_execution_boundaries_control_admission(tmp_path):
    run, _ = declared_location_continuation(tmp_path)
    finalizer = serial.SerialFinalizer(run)
    entry = finalizer.manifest['candidates']['exp'][0]
    changes = [('health-before.json', 'host', 'another-host'),
        ('health-after.json', 'host', 'another-host'),
        ('health-before.json', 'finished_at', '2026-09-08T01:01:01Z'),
        ('health-after.json', 'started_at', '2026-09-08T01:04:59Z'),
        ('measurements/001/execution.json', 'finished_at', '2026-09-08T01:05:02Z')]
    with serial.ExportStore(tmp_path / 'checks/episodes.sqlite') as store:
        for relative, key, value in changes:
            path = run / 'tasks/exp' / relative
            original = finalize.read(path)
            dump(path, {**original, key: value})
            calibration, _ = finalizer.calibration('exp', store)
            assert calibration['accepted'] is True
            assert calibration['operator_health']['accepted'] is False
            current = finalizer.measurement('exp', entry, store, calibration)
            assert current['admitted']['speedup'] is None
            assert current['observed']['per_case'][0]['pair_count'] == 30
            dump(path, original)
    summary = finalizer.run_export()
    assert summary['operators'][0]['attempts'][0]['measurement_admitted'] is True
    assert finalizer.verify()['valid']


def test_declared_candidate_and_control_host_device_must_match_manifest(tmp_path):
    run, _ = declared_location_continuation(tmp_path)
    finalizer = serial.SerialFinalizer(run)
    entry = finalizer.manifest['candidates']['exp'][0]
    with serial.ExportStore(tmp_path / 'checks/episodes.sqlite') as store:
        calibration, _ = finalizer.calibration('exp', store)
        directory = run / 'tasks/exp/measurements/001'
        for name, key, value in [('raw_measurements.json', 'host', 'another-host'),
                ('raw_measurements.json', 'device', 1), ('execution.json', 'host', 'another-host'),
                ('execution.json', 'physical_device', 1), ('execution.json', 'logical_device', 1)]:
            path = directory / name
            original = finalize.read(path)
            dump(path, {**original, key: value})
            if name == 'raw_measurements.json':
                dump(directory / 'measurement_report.json', serial.summarize_multicase(finalize.read(path)))
            current = finalizer.measurement('exp', entry, store, calibration)
            assert current['admitted']['speedup'] is None
            assert any('differs from the frozen measurement manifest' in reason for reason in current['admitted']['reasons'])
            dump(path, original)
            if name == 'raw_measurements.json':
                dump(directory / 'measurement_report.json', serial.summarize_multicase(original))
        directory = run / 'tasks/exp/calibration/0'
        for name, key, value in [('raw_measurements.json', 'host', 'another-host'),
                ('raw_measurements.json', 'device', 1), ('execution.json', 'host', 'another-host'),
                ('execution.json', 'physical_device', 1), ('execution.json', 'logical_device', 1)]:
            path = directory / name
            original = finalize.read(path)
            dump(path, {**original, key: value})
            if name == 'raw_measurements.json':
                dump(directory / 'measurement_report.json', serial.summarize_multicase(finalize.read(path), original['case_ids']))
            with pytest.raises(StoreError, match='host or device different'):
                finalizer.calibration('exp', store)
            dump(path, original)
            if name == 'raw_measurements.json':
                dump(directory / 'measurement_report.json', serial.summarize_multicase(original, original['case_ids']))


def add_stage_execution_envelope(run):
    entry = finalize.read(run / 'run-manifest.json')['candidates']['exp'][0]
    path = run / 'tasks/exp/measurements/001/execution.json'
    execution = finalize.read(path)
    execution.update(argv=['timing', '--baseline', entry['baseline'], '--candidate', entry['candidate']], cwd=str(ROOT))
    dump(path, execution)


def test_retrospective_attestation_uses_real_time_and_preserves_original_source_freeze(tmp_path):
    run, parent = declared_location_continuation(tmp_path)
    add_stage_execution_envelope(run)
    finalizer = serial.SerialFinalizer(run)
    earliest = serial.dt.datetime.now(serial.dt.timezone.utc)
    finalizer.run_export()
    latest = serial.dt.datetime.now(serial.dt.timezone.utc)
    task = run / 'tasks/exp'
    attestation_path = task / 'attestation.json'
    attestation = finalize.read(attestation_path)
    timestamp = serial.dt.datetime.fromisoformat(attestation['attested_at'].replace('Z', '+00:00'))
    assert earliest <= timestamp <= latest
    assert attestation['mode'] == 'retrospective_measurement_continuation'
    assert attestation['run_created_at'] == finalizer.manifest['created_at']
    assert attestation['source_frozen_at'] == finalize.read(parent / 'tasks/exp/frozen-roster.json')['frozen_at']
    assert attestation['producer_path'] == str(ROOT / 'scripts/finalize_level1_serial.py')
    assert attestation['producer_ref'] == file_hash(ROOT / 'scripts/finalize_level1_serial.py')
    record = finalize.rows(task / 'optimization_traces.jsonl')[0]
    inherited = finalize.rows(parent / 'train/optimization_traces.jsonl')[0]
    assert record['provenance']['producer_hash'] == attestation['producer_ref']
    assert record['provenance']['dependencies']['parent_producer_hash'] == inherited['provenance']['producer_hash']
    for role in ('baseline_source_hash', 'candidate_source_hash', 'patch_hash', 'harness_hash'):
        assert record['provenance'][role] == inherited['provenance'][role]
    events = finalize.rows(task / 'trace_events.jsonl')
    assert {event['timestamp'] for event in events} == {attestation['attested_at']}
    assert all(file_hash(attestation_path) in event['artifact_refs'] for event in events)
    for event in events:
        if 'reason' in event['payload']:
            assert 'Retrospective attestation' in event['payload']['reason']
        execution = event['payload'].get('execution')
        if execution:
            assert serial.execution_interval(execution)[1] <= timestamp
    request = finalize.read(task / 'exploration_request.json')
    with serial.ExportStore(run / 'train/episodes.sqlite') as store:
        frozen = finalize.read(store.verify_artifact(request['frozen_manifest_hash']))
        assert frozen['frozen_at'] == attestation['source_frozen_at']
        assert request['evidence'][0]['artifacts']['measurement_attestation'] == file_hash(attestation_path)
    before = attestation_path.read_bytes()
    finalizer.run_export()
    assert attestation_path.read_bytes() == before
    assert finalizer.verify()['valid']


def test_interrupted_export_reuses_first_attestation_and_event_prefix(tmp_path, monkeypatch):
    run, _ = continuation(tmp_path)
    finalizer = serial.SerialFinalizer(run)
    evaluate = serial.ExplorationGate.evaluate
    def interrupt(*args, **kwargs):
        raise RuntimeError('CPU fixture interrupts finalization after attempt sealing')
    monkeypatch.setattr(serial.ExplorationGate, 'evaluate', interrupt)
    with pytest.raises(RuntimeError, match='interrupts finalization'):
        finalizer.run_export()
    task = run / 'tasks/exp'
    attestation = (task / 'attestation.json').read_bytes()
    prefix = (task / 'trace_events.jsonl').read_bytes()
    monkeypatch.setattr(serial.ExplorationGate, 'evaluate', evaluate)
    finalizer.run_export()
    assert (task / 'attestation.json').read_bytes() == attestation
    assert (task / 'trace_events.jsonl').read_bytes().startswith(prefix)
    assert finalizer.verify()['valid']


def test_future_execution_cannot_be_attested_before_it_finishes(tmp_path):
    run, _ = continuation(tmp_path)
    path = run / 'tasks/exp/measurements/001/execution.json'
    execution = finalize.read(path)
    execution.update(started_at='2099-01-01T00:00:00Z', finished_at='2099-01-01T00:01:00Z')
    dump(path, execution)
    with pytest.raises(StoreError, match='execution finishes after retrospective attestation'):
        serial.SerialFinalizer(run).run_export()
    assert not (run / 'tasks/exp/attestation.json').exists()
    assert not (run / 'tasks/exp/trace_events.jsonl').exists()


def test_verify_rejects_changed_attestation_and_stage_finishing_after_attestation(tmp_path):
    from aprof_runtime.traces import GENESIS
    run, _ = declared_location_continuation(tmp_path)
    add_stage_execution_envelope(run)
    finalizer = serial.SerialFinalizer(run)
    finalizer.run_export()
    task = run / 'tasks/exp'
    path = task / 'attestation.json'
    original = path.read_bytes()
    attestation = finalize.read(path)
    attestation['mode'] = 'new_source_attempt'
    dump(path, attestation)
    with pytest.raises(StoreError, match='retrospective attestation differs'):
        finalizer.verify()
    path.write_bytes(original)
    events = finalize.rows(task / 'trace_events.jsonl')
    previous = GENESIS
    for event in events:
        if event['event_type'] == 'stage_completed' and event['payload']['execution']:
            event['payload']['execution']['finished_at'] = '2099-01-01T00:00:00Z'
        event['previous_event_hash'] = previous
        event['event_hash'] = serial.content_hash({k: v for k, v in event.items() if k != 'event_hash'})
        previous = event['event_hash']
    (task / 'trace_events.jsonl').write_text(''.join(serial.canonical_json(event) + '\n' for event in events))
    with serial.ExportStore(run / 'train/episodes.sqlite') as store:
        with pytest.raises(StoreError, match='stage execution finishes after its retrospective attestation'):
            finalizer.verify_operator('exp', store)
