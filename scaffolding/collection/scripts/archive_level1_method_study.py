#!/usr/bin/env python3
"""Retrospectively archive rejected exp A/A method studies, with zero candidates."""
from __future__ import annotations

from aprof_layout import skill_lib

import argparse
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(skill_lib() / 'runtime/src'))
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
from aprof_runtime.errors import StoreError
from aprof_runtime.jsonio import file_hash
from aprof_runtime.store import default_object_directory
from aprof_runtime.traces import TraceWriter, execution_record, utcnow, verify_trace
from finalize_level1_serial import ExportStore
from run_level1_serial import CASES, compare_controls, read, save

SUPPORTED = {'level1-serial-20260908T003200Z', 'level1-capture-probe-20260908T005000Z'}
ARCHIVE = 'method_archive'


def frozen_producer(path, digest):
    name = 'method_archive_producer_' + digest.removeprefix('sha256:')
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def decision_replay(selection, reports, compare):
    if len(reports) == 4:
        selected = compare(reports[1], reports[2])
        if compare(reports[0], reports[3]) != selection['diagnostic_unconditioned']:
            raise StoreError('unconditioned diagnostic decision does not replay')
    elif len(reports) == 2:
        selected = compare(reports[0], reports[1])
    else:
        raise StoreError('method archive requires the complete two- or four-session A/A study')
    if any(selected[key] != selection[key] for key in ('accepted', 'reason', 'per_case')):
        raise StoreError('method admission decision does not replay')
    if selected['accepted'] is not False:
        raise StoreError('this archive only handles rejected measurement methods')
    return selected


def archived_execution(record, log_ref):
    job = record.get('job', record)
    if not all(key in record for key in ('started_at', 'finished_at', 'host')):
        return None
    return execution_record(argv=job['argv'], cwd=job['cwd'], host=record['host'],
        device=record.get('physical_device'), started_at=record['started_at'],
        finished_at=record['finished_at'], exit_status=record.get('exit_status', record.get('exit_code')),
        log_ref=log_ref, reason='Retrospective transcription of the original execution record.')


def verify(run, *, require_closure=True):
    run = Path(run).resolve()
    decision_path = run / ARCHIVE / 'decision.json'
    decision = read(decision_path)
    if decision.get('attempt_count') != 0 or decision.get('status') != 'blocked' or decision.get('accepted') is not False:
        raise StoreError('method archive must remain blocked with zero optimization attempts')
    with ExportStore(run / 'train/episodes.sqlite') as store:
        trace = run / 'train/trace_events.jsonl'
        checked = verify_trace(trace, store)
        events = [json.loads(line) for line in trace.read_text().splitlines()]
        if not events or any(row['attempt_id'] is not None or row['candidate_id'] is not None
                             or row['run_id'] != run.name for row in events):
            raise StoreError('method events acquired optimization candidate identity')
        if events[-1]['event_type'] != 'task_finished' or events[-1]['payload']['status'] != 'blocked':
            raise StoreError('method task must finish blocked')
        if events[-1]['payload']['attempt_count'] != 0 or events[-1]['payload']['summary_ref'] != file_hash(decision_path):
            raise StoreError('method decision differs from the sealed trace')
        indexed = {row[0] for row in store.connection.execute('SELECT content_hash FROM artifacts')}
        if set(store.verified) != indexed:
            raise StoreError('method CAS contains evidence not covered by its trace')
        for name in ('optimization_traces.jsonl', 'episodes.jsonl'):
            if (run / 'train' / name).read_bytes():
                raise StoreError('method study exported optimization records or episodes')
        if store.connection.execute('SELECT COUNT(*) FROM episodes').fetchone()[0]:
            raise StoreError('method study added a policy episode')
        index = read(store.verify_artifact(decision['artifact_index_ref']))
        paths = {row['path']: row['artifact_ref'] for row in index['artifacts']}
        controller_path = str(run / 'setup/run_level1_serial.py')
        active_path = str(run / 'setup/active-controller.json')
        if active_path in paths:
            controller_path = read(store.verify_artifact(paths[active_path]))['path']
        controller_ref = paths[controller_path]
        controller = frozen_producer(store.verify_artifact(controller_ref), controller_ref)
        producer = frozen_producer(store.verify_artifact(decision['timing_producer_ref']), decision['timing_producer_ref'])
        reports = []
        for session in decision['sessions']:
            raw = read(store.verify_artifact(session['raw_ref']))
            report = read(store.verify_artifact(session['report_ref']))
            if producer.summarize_multicase(raw, controller.CASES) != report:
                raise StoreError('archived A/A report no longer reproduces its raw samples')
            reports.append(report)
        selection = read(store.verify_artifact(decision['selection_ref']))
        decision_replay(selection, reports, controller.compare_controls)
        projection_ref = paths.get(str(run / ARCHIVE / 'verifier-qualification-status.json'))
        projection = read(store.verify_artifact(projection_ref)) if projection_ref else None
        closure = None
        if projection:
            seals = [event for event in events if event['event_type'] == 'next_step_decided'
                     and event['payload']['action'] == 'seal_heldout_qualification_closure']
            if require_closure and len(seals) != 1:
                raise StoreError('held-out qualification closure is not anchored in the method trace')
            if seals:
                closure = read(store.verify_artifact(seals[0]['payload']['evidence_refs'][0]))
        store.verify_integrity()
        result = dict(valid=True, run_id=run.name, status='blocked', attempt_count=0, episode_count=0,
            trace=checked, unique_train_artifacts_verified=len(indexed),
            verification_scope='Strict JSONL chain and every indexed CAS object verified once per invocation; frozen A/A producer and decision replay.')
    validation = run / 'validation/method_evidence_index.json'
    if projection and not validation.exists():
        raise StoreError('required held-out qualification evidence index is missing')
    if validation.exists():
        if closure and file_hash(validation) != closure['validation_index_ref']:
            raise StoreError('held-out qualification index differs from its train trace anchor')
        with ExportStore(run / 'validation/episodes.sqlite') as store:
            index = read(validation)
            if store.verify_artifact(file_hash(validation)).read_bytes() != validation.read_bytes():
                raise StoreError('validation evidence index changed')
            for row in index['artifacts']:
                store.verify_artifact(row['artifact_ref'])
            if projection:
                qualification_ref = 'sha256:' + projection['source_digest_hex']
                if qualification_ref not in {row['artifact_ref'] for row in index['artifacts']}:
                    raise StoreError('held-out qualification original is absent from its index')
                qualification = read(store.verify_artifact(qualification_ref))
                for key in ('all_exact_result_and_exit_matches', 'old_sources_metadata_results_unchanged', 'operator_count'):
                    if qualification[key] != projection[key]:
                        raise StoreError('global qualification status differs from its original evidence')
            indexed = {row[0] for row in store.connection.execute('SELECT content_hash FROM artifacts')}
            if set(store.verified) != indexed or store.connection.execute('SELECT COUNT(*) FROM episodes').fetchone()[0]:
                raise StoreError('invalid held-out qualification CAS')
            result['unique_validation_artifacts_verified'] = len(indexed)
    return result


def seal_closure(run):
    """Append a cross-split anchor while retaining the original archive events."""
    projection = run / ARCHIVE / 'verifier-qualification-status.json'
    if not projection.exists():
        return verify(run)
    anchor_path = run / ARCHIVE / 'validation-closure-binding.json'
    if not anchor_path.exists():
        save(anchor_path, dict(kind='separate_validation_cas_anchor', sealed_at=utcnow(),
            validation_index_ref=file_hash(run / 'validation/method_evidence_index.json'),
            qualification_status_ref=file_hash(projection),
            scope='Only the validation index digest is anchored in train; held-out qualification values remain in validation CAS.'))
    anchor = read(anchor_path)
    with ExportStore(run / 'train/episodes.sqlite') as store:
        ref = store.install(anchor_path)
        decision_ref = file_hash(run / ARCHIVE / 'decision.json')
        writer = TraceWriter(run / 'train/trace_events.jsonl', run_id=run.name, task_id='exp-measurement-method',
            session_id='retrospective-method-archive', store=store, verify_history_artifacts=False)
        writer.append('next_step_decided', dict(action='seal_heldout_qualification_closure',
            reason='Bind the separate held-out qualification CAS without importing held-out values into train.', evidence_refs=[ref]),
            event_id='method-validation-closure', timestamp=anchor['sealed_at'])
        writer.append('task_finished', dict(status='blocked', reason='Measurement method remains unqualified; separate validation evidence is now anchored.',
            attempt_count=0, summary_ref=decision_ref), event_id='method-validation-closure-finished',
            timestamp=anchor['sealed_at'], artifact_refs=[row[0] for row in store.connection.execute('SELECT content_hash FROM artifacts')])
    result = verify(run)
    save(run / ARCHIVE / 'closure-verification.json', result)
    return result


def write_report(run, decision, result):
    report = run / ARCHIVE / 'report.md'
    text = '\n'.join(['# Rejected exp A/A method study', '',
        f'Run: `{run.name}`', '', '**Method admission: blocked. Optimization candidates: 0. Policy episodes: 0.**', '',
        'Reason: ' + decision['reason'], '', 'Next method experiment: ' + decision['next_experiment'], '',
        f"Archived {len(decision['sessions'])} original A/A sessions and {result['unique_train_artifacts_verified']} unique train CAS objects.",
        'The strict JSONL chain, all indexed CAS objects, frozen measurement reports and the rejection decision replay successfully.', '',
        'Event timestamps describe this retrospective archive. Execution payloads retain original recorded intervals.',
        'The old optimization run is read-only. No candidate budget exhaustion, optimized speedup, or causal explanation is asserted.',
        'Global input-binding documents are not followed transitively. Only exp A/A input bytes and the exp baseline source are imported.',
        'If present, held-out verifier qualification details are isolated in validation CAS; missing outer qualification commands and times remain missing.', ''])
    if report.exists() and report.read_text() != text:
        raise StoreError('immutable method report differs')
    report.write_text(text)


def archive(run):
    run = Path(run).resolve()
    if run.name not in SUPPORTED:
        raise StoreError('only the two explicitly authorized method-study runs may be archived')
    manifest = read(run / 'run-manifest.json')
    parent = Path(manifest['parent_run']).resolve()
    if run == parent or parent in run.parents:
        raise StoreError('method archive must be separate from the immutable optimization run')
    study = read(run / 'method_study.json')
    if study.get('kind') != 'measurement_method_study' or study.get('status') != 'rejected' or study.get('candidate_measurements') != 0:
        raise StoreError('method study is not a rejected zero-candidate measurement study')
    if any((run / 'tasks').glob('*/measurements/*/execution.json')):
        raise StoreError('candidate performance exists; refusing a zero-candidate archive')
    if (run / ARCHIVE / 'verification.json').exists():
        write_report(run, read(run / ARCHIVE / 'decision.json'), read(run / ARCHIVE / 'verification.json'))
        return seal_closure(run)
    selection_path = run / 'calibration/selection.json'
    if not selection_path.exists():
        selection_path = run / 'selection.json'
    selection = read(selection_path)
    if selection.get('accepted') is not False:
        raise StoreError('method selection must be explicitly rejected')
    context_path = run / ARCHIVE / 'context.json'
    if not context_path.exists():
        save(context_path, dict(schema_version='1.0.0', archived_at=utcnow(), kind='retrospective_method_archive',
            attempt_count=0, candidate_budget_consumed=0,
            timestamp_policy='Trace timestamps record this retrospective archive. Payload execution intervals come only from original execution records.',
            scope='exp baseline A/A only. Existing roster/configuration documents are opaque provenance, not optimization attempts or transitive import requests.',
            qualification_scope='Held-out gelu qualification details and the original global qualification document use a separate validation CAS; no referenced held-out input is imported.'))
    timestamp = read(context_path)['archived_at']
    source_hash = manifest['candidates']['exp'][0]['source_hashes']['baseline']
    source_database = parent / 'train/episodes.sqlite'
    with sqlite3.connect(source_database.as_uri() + '?mode=ro&immutable=1', uri=True) as connection:
        if not connection.execute('SELECT 1 FROM artifacts WHERE content_hash=?', (source_hash,)).fetchone():
            raise StoreError('exp baseline source is not indexed in the immutable parent')
    digest = source_hash.removeprefix('sha256:')
    source_path = default_object_directory(source_database) / 'sha256' / digest[:2] / digest[2:]
    with ExportStore(run / 'train/episodes.sqlite') as store:
        artifacts, by_path = [], {}
        def add(path, category, expected=None):
            path = Path(path)
            if path.is_symlink() or not path.is_file():
                raise StoreError(f'evidence must be a regular non-symlink file: {path}')
            key = str(path.resolve())
            ref = store.install(path, expected)
            if key not in by_path:
                artifacts.append(dict(path=key, artifact_ref=ref, category=category, size_bytes=path.stat().st_size))
                by_path[key] = ref
            return ref
        baseline_ref = add(source_path, 'inherited exp baseline source snapshot', source_hash)
        for path in (context_path, run / 'run-manifest.json', run / 'method_study.json', selection_path):
            add(path, 'method declaration and decision')
        add(Path(__file__), 'retrospective archive producer')
        for path in sorted((run / 'calibration').rglob('*')):
            if path.is_file():
                add(path, 'original exp A/A evidence')
        for pattern in ('health*.json', 'registration.json', 'exp-source.tar', 'exp-harness.patch'):
            for path in sorted(run.glob(pattern)):
                add(path, 'method setup and health')
        for directory in ('exp-configure', 'exp-build'):
            for path in sorted((run / directory).rglob('*')):
                if path.is_file():
                    add(path, 'harness-only build evidence')
        heldout = []
        for path in sorted((run / 'setup').rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            rel = path.relative_to(run / 'setup')
            if rel.parts[0].startswith('verifier-qualification') and ('gelu' in rel.parts or path.name == 'qualification.json'):
                heldout.append(path)
            else:
                add(path, 'original method setup and verifier qualification')
        qualification_path = run / 'setup/verifier-qualification/qualification.json'
        if qualification_path.exists():
            qualification = read(qualification_path)
            projected = run / ARCHIVE / 'verifier-qualification-status.json'
            save(projected, dict(kind='global_cpu_verifier_qualification_status_only',
                all_exact_result_and_exit_matches=qualification['all_exact_result_and_exit_matches'],
                old_sources_metadata_results_unchanged=qualification['old_sources_metadata_results_unchanged'],
                operator_count=qualification['operator_count'], source_path=str(qualification_path),
                source_digest_hex=file_hash(qualification_path).removeprefix('sha256:'),
                heldout_details='Original global document and gelu logs are confined to validation CAS; no qualification input paths are followed.',
                missing_outer_execution='The initial and final outer qualification scripts, terminal logs, command lines and execution intervals were not saved. No values are reconstructed.'))
            add(projected, 'global verifier qualification status without held-out values')
        if heldout:
            with ExportStore(run / 'validation/episodes.sqlite') as validation_store:
                index_path = run / 'validation/method_evidence_index.json'
                index = dict(kind='heldout_cpu_verifier_qualification_evidence', attempt_count=0,
                    purpose='Preserve original qualification records separately; no operator inputs, candidate performance, or optimization knowledge are imported.',
                    artifacts=[dict(path=str(path), artifact_ref=validation_store.install(path)) for path in heldout])
                save(index_path, index)
                validation_store.install(index_path)
        knowledge = []
        recorded_reads = run / 'setup/knowledge-reads.json'
        if recorded_reads.exists():
            for item in read(recorded_reads)['reads']:
                ref = add(item['path'], 'recorded methodology knowledge', item['sha256'])
                knowledge.append(dict(path=item['path'], content_hash=ref, purpose='Methodology read recorded in the original study; imported retrospectively.'))
        producer_path = run / 'setup/cannbench_device_timing.py'
        producer_ref = add(producer_path, 'frozen timing producer')
        if not knowledge:
            knowledge.append(dict(path=str(producer_path), content_hash=producer_ref,
                purpose='Method implementation inspected during retrospective archive; no historical knowledge-read event is inferred.'))
        producer = frozen_producer(producer_path, producer_ref)
        controller_path = run / 'setup/run_level1_serial.py'
        if (run / 'setup/active-controller.json').exists():
            controller_path = Path(read(run / 'setup/active-controller.json')['path'])
        controller_ref = add(controller_path, 'frozen method admission controller')
        controller = frozen_producer(controller_path, controller_ref)
        sessions, reports, executions = [], [], []
        for report_location in selection['artifact_paths']:
            report_path = Path(report_location).resolve()
            if not report_path.is_relative_to(run / 'calibration'):
                raise StoreError('A/A report is outside this method run')
            directory = report_path.parent
            raw_path, execution_path = directory / 'raw_measurements.json', directory / 'execution.json'
            raw, report, execution = read(raw_path), read(report_path), read(execution_path)
            if raw.get('operator') != 'exp' or raw.get('case_ids') != CASES or not raw.get('complete'):
                raise StoreError('method archive requires complete exp sentinel A/A sessions')
            if raw['baseline_executable_sha256'] != raw['candidate_executable_sha256']:
                raise StoreError('method evidence is not same-binary A/A')
            argv = execution['argv']
            baseline = argv[argv.index('--baseline') + 1]
            candidate = argv[argv.index('--candidate') + 1]
            if baseline != candidate or execution.get('exit_status') != 0:
                raise StoreError('method A/A execution must successfully run the same baseline for both roles')
            if raw['producer_sha256'].removeprefix('sha256:') != execution['timing_producer_sha256'].removeprefix('sha256:'):
                raise StoreError('raw samples identify a different timing producer')
            binding = execution.get('source_binding', {})
            if binding.get('actual_candidate_source_hash', source_hash) != source_hash:
                raise StoreError('A/A evidence identifies a different source than the original baseline')
            for changed_source in binding.get('measurement_source_binding', {}).values():
                if isinstance(changed_source, dict):
                    for path_key, hash_key in [('source_snapshot_path', 'source_snapshot_sha256'), ('harness_patch_path', 'harness_patch_sha256')]:
                        if path_key in changed_source:
                            add(changed_source[path_key], 'bound harness-only measurement source', changed_source[hash_key])
            add(Path(baseline) / 'build/exp', 'executed exp baseline binary', raw['baseline_executable_sha256'])
            add(producer_path, 'frozen timing producer', execution['timing_producer_sha256'])
            if producer.summarize_multicase(raw, CASES) != report:
                raise StoreError('A/A report differs from its frozen producer replay')
            logs = {}
            for label in ('stdout', 'stderr'):
                logs[label] = add(directory / (label + '.log'), 'A/A process log', execution[label]['sha256'])
            for item in raw['case_executions']:
                path = Path(item['metadata_path']).resolve()
                if not path.is_relative_to(parent / 'tasks/exp'):
                    raise StoreError('method input lies outside exp; no other operator data may be imported')
                add(path, 'exp A/A prepared metadata', item['metadata_sha256'])
                metadata = read(path)
                for key, value in item['input_hashes'].items():
                    input_path = Path(metadata[key]).resolve()
                    if not input_path.is_relative_to(parent / 'tasks/exp'):
                        raise StoreError('method input lies outside exp')
                    add(input_path, 'exp A/A prepared input', value)
            sessions.append(dict(name=directory.name, raw_ref=add(raw_path, 'A/A raw samples'),
                report_ref=add(report_path, 'A/A descriptive report'), execution_ref=add(execution_path, 'A/A execution record')))
            reports.append(report)
            executions.append((f'aa/{directory.name}', execution, logs['stdout'], sessions[-1]['execution_ref']))
        replayed = decision_replay(selection, reports, controller.compare_controls)
        for name in ('exp-configure', 'exp-build'):
            path = run / name / 'execution.json'
            if path.exists():
                record = read(path)
                log_ref = add(run / name / 'stdout.log', 'harness-only build log', record['stdout']['sha256'])
                add(run / name / 'stderr.log', 'harness-only build log', record['stderr']['sha256'])
                executions.insert(0, (name, record, log_ref, add(path, 'harness-only build execution')))
        index_path = run / ARCHIVE / 'artifact-index.json'
        save(index_path, dict(schema_version='1.0.0', artifacts=artifacts,
            import_rule='Only explicit exp raw metadata/input references are followed. Configuration JSON remains opaque; other operators and old candidate CAS closures are not traversed.'))
        index_ref = store.install(index_path)
        decision_path = run / ARCHIVE / 'decision.json'
        decision = dict(schema_version='1.0.0', kind='measurement_method_archive', run_id=run.name,
            archived_at=timestamp, status='blocked', accepted=False, attempt_count=0, candidate_measurements=0,
            episode_count=0, graph_policy_eligible=False, optimization_candidate_budget_consumed=0,
            reason=replayed['reason'], source_ref=baseline_ref, selection_ref=by_path[str(selection_path.resolve())],
            timing_producer_ref=producer_ref, artifact_index_ref=index_ref, sessions=sessions,
            next_experiment=study['next_experiment'],
            limitations=['A/A method admission failed; no optimized candidate performance was measured.',
                'Host-submission gaps and context effects are hypotheses, not established causes.',
                'These retrospective events do not claim optimization candidate budget exhaustion.',
                'Original execution documents may include unused roster identities; all method event candidate and attempt IDs remain null.'])
        save(decision_path, decision)
        decision_ref = store.install(decision_path)
        writer = TraceWriter(run / 'train/trace_events.jsonl', run_id=run.name, task_id='exp-measurement-method',
            session_id='retrospective-method-archive', store=store, verify_history_artifacts=False)
        def event(kind, payload, suffix, refs=()):
            writer.append(kind, payload, event_id='method-' + suffix, timestamp=timestamp, artifact_refs=refs)
        event('task_started', dict(operator='exp', split='train', knowledge_manifest_hash=None,
            baseline_source_hash=baseline_ref, budget=dict(candidate_limit=0, build_limit=sum(x[0] == 'exp-build' for x in executions),
                timing_limit=len(sessions), full_profile_limit=0)), 'started', [index_ref])
        event('knowledge_loaded', dict(entries=knowledge), 'knowledge')
        for stage, record, log_ref, record_ref in executions:
            status = 'passed' if record.get('exit_status', record.get('exit_code')) == 0 else 'failed'
            event('stage_completed', dict(stage=stage, status=status, execution=archived_execution(record, log_ref),
                reason='Actual completed method execution; successful execution does not imply A/A admission.',
                artifact_refs=[record_ref, log_ref]), stage.replace('/', '-'))
        for path in sorted([*(run / 'calibration').glob('health*.json'), *run.glob('health*.json')]):
            record = read(path)
            ref = by_path[str(path.resolve())]
            event('stage_completed', dict(stage='health/' + str(path.relative_to(run)),
                status='passed' if record['exit_status'] == 0 else 'failed', execution=archived_execution(record, ref),
                reason='Historical device inventory; archival did not query hardware.', artifact_refs=[ref]),
                'health-' + str(path.relative_to(run)).replace('/', '-'))
        preflight = run / 'setup/controller-preflight-failure.json'
        if preflight.exists():
            event('stage_completed', dict(stage='controller_input_preflight', status='failed', execution=None,
                reason=read(preflight)['reason'] + ' Original execution interval was not recorded.',
                artifact_refs=[by_path[str(preflight.resolve())]]), 'preflight')
        if qualification_path.exists():
            initial_refs = [row['artifact_ref'] for row in artifacts if '/verifier-qualification-initial/' in row['path']]
            event('stage_completed', dict(stage='verifier_reuse_initial_stdout_comparison', status='failed', execution=None,
                reason='The initial full-stdout comparison differed because process preload warnings were emitted differently. Original result and warning logs are retained; the outer command, interval and exit record were not saved.',
                artifact_refs=sorted(set(initial_refs))), 'verifier-initial')
            event('stage_completed', dict(stage='verifier_reuse_qualification', status='passed' if qualification['all_exact_result_and_exit_matches'] else 'failed',
                execution=None, reason='The saved qualification attests exact result/exit and main-output agreement. Held-out numerical details remain in the validation CAS.',
                artifact_refs=[by_path[str((run / ARCHIVE / 'verifier-qualification-status.json').resolve())]]), 'verifier-final')
        event('diagnosis_recorded', dict(symptoms=[replayed['reason']],
            mechanisms=['The selected same-binary A/A method failed its frozen role-bias or session-reproducibility threshold.'],
            assessment_basis='measured', supporting_evidence=[decision['selection_ref']], contradicting_evidence=[],
            missing_evidence=['No optimized candidate timing was collected.', 'The causal source of the A/A role bias remains unresolved.'],
            source_anchors=['exp baseline source snapshot: ' + str(source_path)]), 'diagnosis')
        event('next_step_decided', dict(action='continue_measurement_method_study', reason=study['next_experiment'],
            evidence_refs=[decision['selection_ref'], decision_ref]), 'next-step')
        all_refs = [row[0] for row in store.connection.execute('SELECT content_hash FROM artifacts')]
        event('task_finished', dict(status='blocked', reason='Measurement method not admitted: ' + replayed['reason'],
            attempt_count=0, summary_ref=decision_ref), 'finished', all_refs)
        for name in ('optimization_traces.jsonl', 'episodes.jsonl'):
            path = run / 'train' / name
            if path.exists() and path.read_bytes():
                raise StoreError('refusing to replace optimization evidence')
            path.touch(exist_ok=True)
    result = verify(run, require_closure=False)
    write_report(run, decision, result)
    save(run / ARCHIVE / 'verification.json', result)
    return seal_closure(run)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True, action='append')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    for run in args.run:
        print(json.dumps(verify(run) if args.verify_only else archive(run), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
