#!/usr/bin/env python3
"""Explicit, serial execution adapter for the msprof exploration campaign.

Commands own immutable output directories. Importing this module never discovers
devices or opens a runtime store. The campaign ledger is charged before execution.
"""
from __future__ import annotations
from aprof_layout import skill_lib

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import difflib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tarfile
import time
from types import SimpleNamespace
from msprof_search_protocol import LITE_PROTOCOL, LITE_ANALYSIS, LITE_PRODUCER, LITE_DESIGN

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = 'msprof_task_time_exploration_v1'
MATRIX = [('AB', 'AB', 'normal,swapped'), ('BA', 'AB', 'swapped,normal'),
          ('AB', 'BA', 'normal,swapped'), ('BA', 'BA', 'swapped,normal'),
          ('AB', 'AB', 'swapped,normal'), ('BA', 'BA', 'normal,swapped')]
ALL_CASES = list(range(1, 21))


def now():
    return datetime.now(timezone.utc).isoformat()


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return 'sha256:' + h.hexdigest()


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n').encode()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())


def pointer(path):
    return {'path': str(Path(path).resolve()), 'sha256': sha(path)}


def event(task, kind, value):
    """External public-work recorder, separate from the optimization agent."""
    task = Path(task)
    task.mkdir(parents=True, exist_ok=True)
    with (task / '.recorder.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = task / 'events.jsonl'
        rows = path.read_bytes().splitlines() if path.exists() else []
        record = {'sequence': len(rows), 'recorded_at': now(), 'kind': kind,
                  'previous_hash': json.loads(rows[-1])['hash'] if rows else None, 'value': value}
        record['hash'] = 'sha256:' + hashlib.sha256(canonical(record)).hexdigest()
        with path.open('ab') as stream:
            stream.write(canonical(record)); stream.flush(); os.fsync(stream.fileno())
    return record


def read_recorded(task, path, purpose):
    task, path = Path(task).resolve(), Path(path).resolve()
    # Validate the destination before accessing even shared knowledge. A typo in
    # --task must not create a second recorder outside the declared task store.
    manifest_path = task / 'manifest.json'
    if not manifest_path.is_file():
        raise ValueError('recorded access needs an existing campaign task manifest')
    manifest = load(manifest_path)
    if (not isinstance(manifest, dict) or manifest.get('version') not in (PROTOCOL, 'msprof_task_time_exploration_v2')
            or not isinstance(manifest.get('task_dir'), str)
            or Path(manifest['task_dir']).resolve() != task):
        raise ValueError('recorded access task manifest identity differs')
    if not purpose.strip(): raise ValueError('recorded access needs an actual purpose')
    allowed = [task, skill_lib() / 'skills', skill_lib() / 'workflows',
               ROOT / 'scaffolding/collection/workflows']
    if not any(path.is_relative_to(root) for root in allowed):
        raise ValueError('read is outside this task and declared knowledge roots')
    if path.is_relative_to(task) and not any(path.is_relative_to(task / p) for p in ['baseline', 'candidates', 'feedback', 'agent']):
        raise ValueError('raw campaign reports are coordinator-only during search')
    data = path.read_bytes()
    digest = 'sha256:' + hashlib.sha256(data).hexdigest()
    snapshot = task / 'read-evidence' / digest[7:]
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    if not snapshot.exists():
        with snapshot.open('xb') as stream: stream.write(data)
    record = {'timestamp': now(), 'path': str(path), 'sha256': digest, 'snapshot': str(snapshot),
              'purpose': purpose, 'classification': 'knowledge_read' if not path.is_relative_to(task) else 'source_or_feedback_read',
              'decision_use': 'not_inferred_from_reading'}
    save(task / 'knowledge-reads' / (str(time.time_ns()) + '.json'), record)
    event(task, 'actual_read', record)
    return data.decode()


def extract_source(archive, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive) as tar:
        members = [m for m in tar.getmembers() if m.name.startswith('source/')]
        if not members:
            raise ValueError('source archive contains no source tree')
        for member in members:
            rel = Path(member.name).relative_to('source')
            if rel.is_absolute() or '..' in rel.parts or not (member.isfile() or member.isdir()):
                raise ValueError('unsafe source archive member')
            target = output / rel
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as source, target.open('xb') as dest:
                    shutil.copyfileobj(source, dest)
                target.chmod(member.mode & 0o777)


def bootstrap_task(run, prior, operator):
    run, prior = Path(run).resolve(), Path(prior).resolve()
    split = 'validation' if operator == 'gelu' else 'train'
    old = prior.parent / 'tasks' / operator
    task = run / split / 'tasks' / operator
    task.mkdir(parents=True, exist_ok=False)
    binding = load(old / 'baseline-binding.json')
    if sha(binding['path']) != binding['sha256']:
        raise ValueError('historical baseline archive changed')
    shutil.copyfile(binding['path'], task / 'baseline-source.tar')
    extract_source(task / 'baseline-source.tar', task / 'baseline')
    save(task / 'baseline-binding.json', {**pointer(task / 'baseline-source.tar'), 'origin': binding})
    inputs = load(old / 'input-bindings.json')
    # Inputs stay immutable; only metadata and outputs belong to the new run.
    checked = set()
    for row in inputs['cases']:
        for item in [row['metadata'], *row['inputs'].values(), *([row['oracle_file']] if row.get('oracle_file') else [])]:
            if item['path'] not in checked:
                if sha(item['path']) != item['sha256']:
                    raise ValueError('historical input identity changed: ' + item['path'])
                checked.add(item['path'])
        row['verifier'] = pointer(task / 'baseline/scripts/verify_result.py')
    save(task / 'input-bindings.json', inputs)
    shutil.copyfile(old / 'input-origin.json', task / 'input-origin.json')
    for filename in ['task-parity.json', 'split.json']:
        if (old / filename).exists():
            shutil.copyfile(old / filename, task / filename)
    if operator == 'exp':
        dest = task / 'candidates/exp001'; dest.mkdir(parents=True)
        for filename in ['source.tar', 'optimization.patch', 'inheritance.json', 'registration.json']:
            source = old / 'candidates/exp001' / filename
            if source.exists(): shutil.copyfile(source, dest / filename)
        extract_source(dest / 'source.tar', dest / 'op')
        old_store = prior.parent / 'archive/train/v2'
        save(task / 'inheritance-context.json', {
            'prior_dataset': {'path': str(old_store), 'current': pointer(old_store / 'current.json')},
            'inherited_attempt_id': 'level1-feedback-20260908T114740Z/train/exp001',
            'prior_checkpoint': pointer(prior), 'historical_observations_immutable': True})
    references = ['skill-libs/graph-base/0.4.1/skills/ascendc-aprof-workflow/SKILL.md',
                  'skill-libs/graph-base/0.4.1/skills/ascendc-aprof-diagnosis/SKILL.md',
                  'skill-libs/graph-base/0.4.1/skills/ascendc-aprof-profiling/SKILL.md',
                  'skill-libs/graph-base/0.4.1/skills/ascendc-aprof-optimization/SKILL.md',
                  'skill-libs/graph-base/0.4.1/skills/ascendc-aprof-optimization/references/vector-scalar-pipeline-playbook.md',
                  'scaffolding/collection/workflows/optimization_experiment_playbook.md']
    catalog = {'operator': operator, 'split': split, 'entries': [pointer(ROOT / p) for p in references],
               'read_is_not_decision_use': True, 'optional_references': 'Load precise relevant references only as needed.'}
    save(task / 'knowledge-catalog.json', catalog)
    checkpoint = load(prior)
    manifest = {'version': PROTOCOL, 'run_id': run.name, 'operator': operator, 'split': split,
                'task_dir': str(task), 'baseline_tree': str(task / 'baseline'),
                'baseline': pointer(task / 'baseline-source.tar'), 'input_bindings': pointer(task / 'input-bindings.json'),
                'knowledge_catalog': pointer(task / 'knowledge-catalog.json'),
                'remaining_budget': checkpoint['remaining_budgets'][operator], 'new_source_round_limit': 3,
                'sentinels': [1, 8, 14, 20], 'max_predeclared_diagnostic_cases': 2,
                'correctness_cases': ALL_CASES, 'hardware_execution': 'coordinator_only',
                'formal_admission': 'not_evaluated', 'graph_policy_eligible': False, 'episode_ref': None,
                'agent_artifacts': {'proposal': str(task / 'agent/proposal.json'), 'decisions': str(task / 'agent')},
                'instructions': 'Use original AProf workflow. One source intervention after feedback. Do not author training JSONL. Do not read other tasks, historical outcome views, or nondeclared performance. Publish public rationale, mechanism predictions, exact changes and a continue/stop decision; missing predictions remain missing.'}
    save(task / 'manifest.json', manifest)
    event(task, 'task_bootstrapped', {'manifest': pointer(task / 'manifest.json'), 'input_files_verified': len(checked)})
    return manifest


def task_paths(run, operator, candidate):
    run = Path(run).resolve()
    matches = [s for s in ('train', 'validation') if (run / s / 'tasks' / operator / 'manifest.json').is_file()]
    if len(matches) > 1: raise ValueError('ambiguous campaign task split')
    split = matches[0] if matches else ('validation' if operator == 'gelu' else 'train')
    task = run / split / 'tasks' / operator
    parent = task if candidate == 'baseline' else task / 'candidates' / candidate
    source = task / 'baseline' if candidate == 'baseline' else parent / 'op'
    return run, split, task, parent, source


def execution_modules(task=None):
    import cannbench_msprof_timing as timing
    import cannbench_shared_context_profile as diagnostic
    from msprof_exploration_safety import health
    from msprof_exploration_oracle import ScopedOracle, make_run_logged
    # The override is scoped to this explicitly identified new producer process.
    timing.health = diagnostic.health = health
    original_logger = diagnostic.run_logged
    while isinstance(original_logger, ScopedOracle):
        original_logger = original_logger.delegate
    if task is not None:
        task = Path(task).resolve()
        verifier = task / 'baseline/scripts/verify_result.py'
        bindings = load(task / 'input-bindings.json')['cases']
        expected = {row['verifier']['sha256'] for row in bindings}
        if len(expected) != 1 or any(Path(row['verifier']['path']).resolve() != verifier for row in bindings):
            raise ValueError('scoped oracle requires one unchanged task baseline verifier')
        diagnostic.run_logged = make_run_logged(original_logger, verifier=verifier, expected_hash=next(iter(expected)),
                                               metadata_root=task, cpu_affinity='8')
    else:
        diagnostic.run_logged = original_logger
    return timing, diagnostic, health


def build_operator(source, operator, out, *, npu_arch="dav-2201"):
    from shared_context_build import build
    from feedback_hardware import run_process
    from run_level1_serial import exclusive_host
    source, out = Path(source).resolve(), Path(out).resolve()
    if out.exists(): raise FileExistsError(out)
    with exclusive_host():
        args = SimpleNamespace(source_a=str(source), source_b=str(source), output_dir=str(out),
                               operator=operator, npu_arch=npu_arch, jobs=2, generate_only=True)
        manifest = build(args)
        original = (out / 'CMakeLists.txt').read_text()
        standalone = f'''\nadd_executable(standalone "{source}/op_host/{operator}.asc")
target_include_directories(standalone PRIVATE "{source}/op_host" "{source}/op_kernel")
target_link_libraries(standalone PRIVATE tiling_api register platform unified_dlog dl m graph_base ascendcl ascendc_runtime)
target_link_directories(standalone PRIVATE "$ENV{{ASCEND_HOME_PATH}}/lib64" "$ENV{{ASCEND_HOME_PATH}}/aarch64-linux/lib64")
target_compile_options(standalone PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch={npu_arch}>)
'''
        (out / 'generated-CMakeLists.txt').write_text(original)
        (out / 'CMakeLists.txt').write_text(original + standalone)
        (out / 'standalone-build.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True), (original + standalone).splitlines(True))))
        run_process(['cmake', '-S', out, '-B', out / 'build'], ROOT, out / 'configure-execution', cpu='40-43', timeout=1200)
        run_process(['cmake', '--build', out / 'build', '-j2'], ROOT, out / 'build-execution', cpu='40-43', timeout=1800)
        for role in 'AB': manifest['roles'][role]['binary_sha256'] = sha(manifest['roles'][role]['binary'])[7:]
        manifest['runner'] = {'path': str(out / 'build/shared_context_runner'), 'sha256': sha(out / 'build/shared_context_runner')[7:]}
        manifest['standalone'] = pointer(out / 'build/standalone')
        manifest['campaign_build'] = {'generator': pointer(__file__), 'cmake': pointer(out / 'CMakeLists.txt'),
                                      'targets': ['role_A', 'role_B', 'shared_context_runner', 'standalone']}
        # generate-only manifest is retained rather than overwritten.
        (out / 'build_manifest.json').rename(out / 'generated-build-manifest.json')
        save(out / 'build_manifest.json', manifest)
    return manifest


def build_tools(run, *, per_case=False, search_lite=False):
    timing, diagnostic, _ = execution_modules()
    root = Path(run).resolve() / 'tools'
    root.mkdir(exist_ok=True)
    if search_lite:
        timing.build_runner(root / 'timing-search-lite', 10, per_case=True, search_lite=True)
        save(root / 'search-lite-completion.json', {'status': 'passed', 'completed_at': now(),
             'protocol': LITE_PROTOCOL, 'candidate_budget_charge': False,
             'cost_kind': 'fixed_measurement_harness_builds'})
        return
    timing.build_runner(root / 'timing', 10, per_case=True) if per_case else timing.build_runner(root / 'timing', 10)
    diagnostic.build_runner(SimpleNamespace(output=str(root / 'diagnostic'), ascend_home=os.environ['ASCEND_HOME_PATH'], timeout=120))
    save(root / 'completion.json', {'status': 'passed', 'completed_at': now(), 'protocol': 'msprof_task_time_exploration_v2' if per_case else PROTOCOL,
                                  'candidate_budget_charge': False, 'cost_kind': 'fixed_measurement_harness_builds'})


def comparison_manifest(control_build, candidate_build, output):
    a, b = load(control_build), load(candidate_build)
    if a['operator'] != b['operator']: raise ValueError('different comparison operators')
    result = {'version': 'shared_context_build_v1', 'operator': a['operator'],
              'roles': {'A': a['roles']['A'], 'B': b['roles']['B']},
              'harness': a['harness'], 'component_builds': [pointer(control_build), pointer(candidate_build)]}
    save(output, result)
    return result


def cohort_plan(task, role_build, runner_build, case_ids, kind, name, epoch='epoch-01', *, capture_storage=None, search_lite=False):
    task = Path(task)
    import cannbench_msprof_timing as timing
    inputs = load(task / 'input-bindings.json')
    specs = {r['case_id']: r for r in inputs['cases']}
    request = {'version': 'msprof_kernel_time_study_v1', 'role_build': str(Path(role_build).resolve()),
               'runner_build': str(Path(runner_build).resolve()), 'profiler_mode': 'task_time_l1_ai_core_off',
               'device': 0, 'cpu': 8, 'host_delay_a_us': 0, 'host_delay_b_us': 0, 'timeout': 1800,
               'cases': [{'case_id': c, 'metadata': specs[c]['metadata']['path'], 'verifier': specs[c]['verifier']['path']} for c in case_ids]}
    manifest = load(task / 'manifest.json') if (task / 'manifest.json').is_file() else {}
    fresh = manifest.get('version') == 'msprof_task_time_exploration_v2'
    if search_lite and not fresh:
        raise ValueError('search-lite requires a Level2 v2 task with frozen per-case repeats')
    if fresh:
        measurement = load(task / 'measurement-policy.json')
        repeats = measurement['repeat_by_case']
        request['version'] = 'msprof_kernel_time_study_v2'
        for row in request['cases']: row['repeat'] = repeats[str(row['case_id'])]
        request['timeout'] = measurement['timing_timeout_seconds']
    if search_lite:
        request['version'] = LITE_PRODUCER
    if capture_storage is not None:
        import msprof_raw_storage
        from msprof_raw_storage import policy as storage_policy
        request['capture_storage']=capture_storage
        if capture_storage==msprof_raw_storage.LOCAL:request['capture_storage_producer']=pointer(msprof_raw_storage.__file__)
        storage_policy(request)
    environment = task.parents[2] / 'bootstrap/environment.json'
    return {'protocol': LITE_PROTOCOL if search_lite else 'msprof_task_time_exploration_v2' if fresh else PROTOCOL, 'analysis_version': LITE_ANALYSIS if search_lite else 'msprof_exploration_analysis_v2' if fresh else 'msprof_exploration_analysis_v1', 'comparison_kind': kind,
            'identity_bindings': {'role_build': pointer(role_build), 'runner_build': pointer(runner_build),
                                  'input_bindings': pointer(task / 'input-bindings.json'), 'producer': pointer(timing.__file__)},
            'case_ids': list(case_ids), 'calibration_scope': {**({'capture_storage':capture_storage} if capture_storage is not None else {}), **({'capture_storage_producer_hash':request['capture_storage_producer']['sha256']} if 'capture_storage_producer' in request else {}), 'epoch': epoch, 'host': socket.gethostname(), 'physical_device': 0,
                'cpu': 8, 'runner_hash': load(runner_build)['runner_hash'], 'inputs': sha(task / 'input-bindings.json'),
                'environment': pointer(environment) if environment.is_file() else {'status': 'not_recorded', 'reason': 'synthetic CPU test environment'},
                'profiler_mode': 'task_time_l1_ai_core_off'},
            'schedule': [{'name': f'{name}-p{i + 1:02d}', 'request': dict(request, load_order=l, first_order=f, buffer_configs=c)}
                         for i, (l, f, c) in enumerate(LITE_DESIGN if search_lite else MATRIX)]}


def preflight_cohort(plan):
    """Read-only identity replay before any native process or output creation.

    Older immutable plans retain their original input/runner anchors. New plans
    additionally bind both manifests and the collector producer at freeze time.
    No verifier module is imported or executed by this check.
    """
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        import msprof_exploration_report as report
        from msprof_exploration_provenance import verify_pointer_tree
        frozen = report.validate_plan(plan)
        request = frozen['schedule'][0]['request']
        role_path = Path(request['role_build'])
        scope = frozen['calibration_scope']
        provenance = []
        verify_pointer_tree(frozen, evidence_path=role_path, producer_bindings=provenance)
        identities = frozen.get('identity_bindings')
        if identities is not None:
            if set(identities) != {'role_build', 'runner_build', 'input_bindings', 'producer'}:
                raise ValueError('frozen identity_bindings fields differ')
            for key in ('role_build', 'runner_build'):
                if identities[key]['path'] != request[key]:
                    raise ValueError('frozen build pointer differs from request: ' + key)
            input_path = Path(identities['input_bindings']['path'])
        else:
            input_path = next((p / 'input-bindings.json' for p in role_path.parents
                               if (p / 'input-bindings.json').is_file()), None)
            if input_path is None:
                raise ValueError('frozen task input bindings are unavailable')
        if sha(input_path) != scope.get('inputs'):
            raise ValueError('frozen task input bindings hash differs')
        task = input_path.parent
        if not role_path.is_relative_to(task):
            raise ValueError('role build is outside the frozen input task')
        runner = report.load(request['runner_build'])
        if runner.get('runner_hash') != scope.get('runner_hash'):
            raise ValueError('frozen runner identity differs')
        bindings = {request[key]: sha(request[key]) for key in ('role_build', 'runner_build')}
        bindings[runner['runner']] = sha(runner['runner'])
        timing, build, _ = report._build_identity(request, bindings, provenance_out=provenance)
        if identities is not None and identities['producer']['path'] != str(Path(timing.__file__).resolve()):
            raise ValueError('frozen collector producer path differs')
        for field in ('cpu', 'device', 'profiler_mode'):
            scope_field = 'physical_device' if field == 'device' else field
            if str(request[field]) != str(scope.get(scope_field)):
                raise ValueError('frozen calibration execution identity differs: ' + field)
        rows = report.load(input_path).get('cases')
        if not isinstance(rows, list) or any(not isinstance(row, dict) or type(row.get('case_id')) is not int for row in rows):
            raise ValueError('invalid frozen case bindings')
        by_case = {str(row['case_id']): row for row in rows}
        if len(by_case) != len(rows):
            raise ValueError('duplicate frozen input case')
        for spec in request['cases']:
            case = str(spec['case_id'])
            if case not in by_case:
                raise ValueError('requested case is absent from frozen input bindings')
            row = by_case[case]
            for field in ('metadata', 'verifier'):
                if row[field]['path'] != spec[field]:
                    raise ValueError('requested ' + field + ' differs from frozen input binding')
            if Path(spec['verifier']) != task / 'baseline/scripts/verify_result.py':
                raise ValueError('only the frozen original task verifier is allowed')
            if not isinstance(row.get('inputs'), dict) or not row['inputs']:
                raise ValueError('frozen input file identities required')
            paths = verify_pointer_tree(row, evidence_path=input_path)
            checked = {str(path.resolve()) for path in paths}
            metadata = report.load(spec['metadata'], opaque=True)
            if 'case_id' in metadata and str(metadata['case_id']) != case:
                raise ValueError('prepared metadata case ID differs')
            for key in ('input', 'x', 'mask', 'x1', 'x2', 'x3', 'golden'):
                if key in metadata and str(Path(metadata[key]).resolve()) not in checked:
                    raise ValueError('metadata references an unbound input/oracle: ' + key)
            for key, value in metadata.items():
                if key != 'output' and isinstance(value, str) and Path(value).is_file() and str(Path(value).resolve()) not in checked:
                    raise ValueError('metadata references an unbound file: ' + key)
            argv = timing.command_from_metadata(build['roles']['A']['source_dir'], metadata, 0, task / 'unused.bin')[1:]
            if any('\t' in value or '\n' in value for value in argv):
                raise ValueError('invalid native argument separator')
            for role in 'AB':
                timing.count_launches(build['operator'], build['roles'][role]['source_dir'], metadata)
        return {'status': 'passed', 'read_only': True, 'plan_hash': 'sha256:' + hashlib.sha256(canonical(frozen)).hexdigest(),
                'identity_binding_mode': 'frozen_manifest_pointers' if identities is not None else 'legacy_frozen_scope_and_components',
                'input_bindings': pointer(input_path), 'checked_case_ids': list(frozen['case_ids']),
                'producer_bindings': provenance}
    finally:
        sys.dont_write_bytecode = previous


def collect_cohort(plan, out, calibration=None):
    from msprof_exploration_report import validate_plan, ObservationCache, analyze_task_cohort
    started = time.monotonic()
    plan = validate_plan(plan)
    preflight = preflight_cohort(plan)
    elapsed = {'identity_preflight': time.monotonic() - started,
               'native_collection': 0.0, 'observation_verification': 0.0,
               'report_analysis': 0.0, 'producer_summary': 0.0, 'sessions': []}
    timing, _, _ = execution_modules()
    out = Path(out); out.mkdir(parents=True, exist_ok=False)
    save(out / 'plan.json', plan)
    save(out / 'identity-preflight.json', preflight)
    provenance = list(preflight['producer_bindings'])
    completed = []
    verified = ObservationCache()
    error = None
    try:
        for index, entry in enumerate(plan['schedule']):
            if index:
                phase_start = time.monotonic()
                provenance.extend(preflight_cohort(plan)['producer_bindings'])
                elapsed['identity_preflight'] += time.monotonic() - phase_start
            request_path = out / (entry['name'] + '-request.json')
            save(request_path, entry['request'])
            directory = out / entry['name']
            print(json.dumps({'phase': 'native_process_start', 'session': entry['name'], 'time': now()}), flush=True)
            phase_start = time.monotonic()
            timing.collect(request_path, directory)
            collection_seconds = time.monotonic() - phase_start
            elapsed['native_collection'] += collection_seconds
            phase_start = time.monotonic()
            verified.verify(directory, entry['request'], provenance_out=provenance)
            verification_seconds = time.monotonic() - phase_start
            elapsed['observation_verification'] += verification_seconds
            elapsed['sessions'].append({'session_id': entry['name'],
                                        'native_collection': collection_seconds,
                                        'observation_verification': verification_seconds})
            completed.append(str(directory))
            print(json.dumps({'phase': 'native_process_verified', 'session': entry['name'], 'time': now()}), flush=True)
        phase_start = time.monotonic()
        report = analyze_task_cohort(completed, plan, calibration=calibration, provenance_out=provenance, _verified_sessions=verified)
        elapsed['report_analysis'] = time.monotonic() - phase_start
        save(out / 'report.json', report)
        phase_start = time.monotonic()
        save(out / 'producer-summary.json', timing.summarize(completed))
        elapsed['producer_summary'] = time.monotonic() - phase_start
        return report
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        unique = {canonical(row): row for row in provenance}
        save(out / 'identity-resolution.json', {'read_only_resolution': True, 'producer_bindings': list(unique.values())})
        save(out / 'group-completion.json', {'status': 'failed' if error else 'passed', 'error': error,
              'completed_sessions': completed,
              'sessions': [{'directory': d, 'completion': pointer(Path(d) / 'completion.json'),
                            'samples': pointer(Path(d) / 'samples.json'),
                            'journal': pointer(Path(d) / 'native/journal.jsonl')} for d in completed],
              'ended_at': now(), 'protocol': plan['protocol'],
              **({'elapsed_seconds': {**elapsed, 'total': time.monotonic() - started},
                  'elapsed_scope': 'collector phases; native_collection includes profiler, oracle and capture work; failed in-flight phase is included only in total'}
                 if plan['protocol'] == LITE_PROTOCOL else {})})


def native_started_in(directory):
    directory = Path(directory)
    return any(directory.rglob('native.json')) or any(directory.rglob('journal.jsonl'))


def diagnostic_group(run, operator, candidate, stage, cases, out):
    run, split, task, parent, source = task_paths(run, operator, candidate)
    _, diagnostic, _ = execution_modules(task)
    build = parent / 'build/build_manifest.json'
    common = dict(role_build=str(build), runner_build=str(run / 'tools/diagnostic/profile-build.json'),
                  role='A' if candidate == 'baseline' else 'B', opdir=str(task / 'baseline'), device=0, cpu='8', timeout=1800)
    if stage == 'correctness':
        return diagnostic.correctness(SimpleNamespace(**common, input_root=load(task / 'input-origin.json')['path'],
                                                      cases=','.join(map(str, cases)), output=str(out)))
    inputs = {c['case_id']: c for c in load(task / 'input-bindings.json')['cases']}
    Path(out).mkdir(parents=True, exist_ok=False)
    results = []
    for case in cases:
        directory = Path(out) / f'case_{case:02d}'
        results.append(diagnostic.profile(SimpleNamespace(**common, metadata=inputs[case]['metadata']['path'], case_id=str(case), output=str(directory))))
    save(Path(out) / 'completion.json', {'status': 'passed', 'case_ids': cases, 'capture': {'warmup': 10, 'repeat': 5},
                                        'performance_comparison': False, 'profile_summaries': results})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('bootstrap-task')
    for k in ['run', 'prior', 'operator']: p.add_argument('--' + k, required=True)
    p = sub.add_parser('build-tools'); p.add_argument('--run', required=True)
    p.add_argument('--per-case', action='store_true', help='Build the full Level2 runner with frozen per-case repeat=1 or 10')
    p.add_argument('--search-lite', action='store_true', help='Build the separate two-process search runner; implies --per-case')
    p = sub.add_parser('read')
    for k in ['task', 'path', 'purpose']: p.add_argument('--' + k, required=True)
    p = sub.add_parser('build-operator')
    for k in ['source', 'operator', 'output']: p.add_argument('--' + k, required=True)
    p = sub.add_parser('cohort')
    p.add_argument('--plan', required=True); p.add_argument('--output', required=True); p.add_argument('--calibration')
    p = sub.add_parser('diagnostic')
    for k in ['run', 'operator', 'candidate', 'stage', 'output']: p.add_argument('--' + k, required=True)
    p.add_argument('--cases', default=','.join(map(str, ALL_CASES)))
    args = parser.parse_args(argv)
    if args.command == 'read':
        print(read_recorded(args.task, args.path, args.purpose))
        return
    if args.command == 'bootstrap-task': result = bootstrap_task(args.run, args.prior, args.operator)
    elif args.command == 'build-tools':
        result = build_tools(args.run, per_case=args.per_case or args.search_lite, search_lite=args.search_lite)
    elif args.command == 'build-operator': result = build_operator(args.source, args.operator, args.output)
    elif args.command == 'cohort': result = collect_cohort(load(args.plan), args.output, load(args.calibration) if args.calibration else None)
    else: result = diagnostic_group(args.run, args.operator, args.candidate, args.stage, [int(x) for x in args.cases.split(',')], args.output)
    print(json.dumps({'command': args.command, 'status': 'completed'}, allow_nan=False), flush=True)
    return result


if __name__ == '__main__':
    main()
