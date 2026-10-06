#!/usr/bin/env python3
"""Run one explicitly selected, budgeted stage; never advances a candidate queue."""
from __future__ import annotations
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re
import time

from msprof_exploration_execute import (ALL_CASES, PROTOCOL, bootstrap_task, build_operator,
    canonical, cohort_plan, collect_cohort, comparison_manifest, diagnostic_group, event,
    load, native_started_in, now, pointer, save, sha, task_paths)
from msprof_exploration_campaign import Campaign, timing_plan


def measurement_options(value):
    """Validate explicit options without adding fields to legacy frozen plans."""
    if value is not None and not isinstance(value, dict):
        raise ValueError('timing options must be a mapping')
    result = dict(value or {})
    if set(result) - {'epoch', 'capture_storage', 'calibration_path', 'calibration_by_relation'}:
        raise ValueError('unknown timing option')
    epoch = result.get('epoch', 'epoch-01')
    if not isinstance(epoch, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', epoch) is None:
        raise ValueError('invalid measurement epoch')
    if 'capture_storage' in result:
        from msprof_raw_storage import DIRECT, LOCAL
        if result['capture_storage'] not in (DIRECT, LOCAL):
            raise ValueError('unreviewed capture storage')
        result['capture_storage'] = dict(result['capture_storage'])
        if result['capture_storage'] == LOCAL and epoch == 'epoch-01':
            raise ValueError('local capture requires an explicitly new measurement epoch')
    overrides = result.get('calibration_by_relation', {})
    if not isinstance(overrides, dict) or set(overrides) - {'direct_parent', 'original_baseline'}:
        raise ValueError('unknown calibration relation')
    paths = list(overrides.values())
    if 'calibration_path' in result:
        paths.append(result['calibration_path'])
    if any(not isinstance(path, (str, Path)) or not str(path) for path in paths):
        raise ValueError('invalid calibration path')
    if 'calibration_by_relation' in result:
        result['calibration_by_relation'] = dict(overrides)
    return result


def validate_stage_options(kind, plan_path, *, capture_storage=None, epoch='epoch-01'):
    measurement_options({'epoch': epoch, **({'capture_storage': capture_storage} if capture_storage is not None else {})})
    explicit = capture_storage is not None or epoch != 'epoch-01'
    if explicit and kind != 'control':
        raise ValueError('explicit capture settings are only valid for control; timing requires a frozen plan')
    if plan_path is not None and explicit:
        raise ValueError('capture settings cannot override an explicit frozen plan')


def validate_calibration_storage(plan, calibration):
    """Reject incompatible local A/A before launching any A/B cohort.

    This preflight checks declared identity. Full observation replay still checks
    case, source, environment and calibration quality after native collection.
    Legacy direct-storage plans keep their existing admission semantics.
    """
    from msprof_raw_storage import LOCAL, policy
    scope = plan.get('calibration_scope', {})
    requests = [row['request'] for row in plan.get('schedule', [])]
    local = scope.get('capture_storage') == LOCAL or any(request.get('capture_storage') == LOCAL for request in requests)
    if not local:
        return
    measurement_options({'epoch': scope.get('epoch'), 'capture_storage': LOCAL})
    if not requests or scope.get('capture_storage') != LOCAL or any(policy(request) != LOCAL for request in requests):
        raise ValueError('local cohort capture identity differs')
    producer = requests[0]['capture_storage_producer']['sha256']
    if scope.get('capture_storage_producer_hash') != producer or any(request['capture_storage_producer']['sha256'] != producer for request in requests):
        raise ValueError('local cohort transport producer differs')
    if (calibration.get('protocol') != plan.get('protocol')
            or calibration.get('analysis_version') != plan.get('analysis_version')
            or calibration.get('comparison_kind') != 'aa'
            or calibration.get('evidence_status') != 'verified_complete'
            or calibration.get('formal_admission') != 'not_evaluated'
            or calibration.get('calibration_scope') != scope
            or calibration.get('environment_binding', {}).get('capture_storage') != LOCAL
            or calibration.get('environment_binding', {}).get('capture_storage_producer_hash') != producer):
        raise ValueError('local measurement requires a verified fresh A/A with matching epoch and capture storage')


def source_content_identity(source):
    """Ignore archive labels: identity is the complete selected source file bytes."""
    from collect_level1_traces import candidate_source_files
    digest = hashlib.sha256()
    for name, path in sorted(candidate_source_files(Path(source)).items()):
        digest.update(name.encode() + b'\0' + path.read_bytes() + b'\0')
    return 'sha256:' + digest.hexdigest()


def require_distinct_source(source, known_sources):
    identity = source_content_identity(source)
    for label, prior in known_sources.items():
        if source_content_identity(prior) == identity:
            raise ValueError('same source as ' + label + '; add an observation, not a source attempt')
    return identity


def fresh_graph_bundle(run, graph_ref, expected_graph_hash):
    """Freeze the whole verified run graph, including its provenance bytes."""
    from aprof_runtime.graph import load_snapshot
    from aprof_runtime.jsonio import content_hash
    root = Path(run).resolve() / 'graph/v0002'
    if root.is_symlink() or Path(graph_ref['path']).resolve() != root / 'graph.json':
        raise ValueError('fresh graph must be the frozen run graph/v0002 bundle')
    graph, manifest = load_snapshot(root)
    if graph['graph_version'] != 'v0002' or content_hash(graph) != expected_graph_hash:
        raise ValueError('frozen graph content identity differs')
    if manifest.get('files', {}).get('lineage') != 'lineage.json':
        raise ValueError('fresh graph bundle must include checked lineage')
    checksums = load(root / manifest['files']['checksums'])
    names = {'manifest.json', *manifest['files'].values(), *checksums['files']}
    refs = []
    for name in sorted(names):
        path = root / name
        if path.is_symlink(): raise ValueError('fresh graph bundle rejects symlinks')
        refs.append(pointer(path))
    if pointer(root / 'graph.json') != graph_ref:
        raise ValueError('frozen graph pointer differs')
    return refs


def fresh_dispatch_launch(source, launch_ref, dispatch):
    """The captured launcher and planning contract must select the same entry."""
    from shared_context_build import source_hash
    import re
    source = Path(source).resolve()
    path = source.parent / 'dispatch-launch.json'
    if Path(launch_ref['path']).resolve() != path or sha(path) != launch_ref['sha256']:
        raise ValueError('fresh dispatch launcher pointer differs')
    launch = load(path)
    if launch.get('version') != 'level2_dispatch_launch_v1' or launch.get('source_sha256') != source_hash(source):
        raise ValueError('fresh dispatch launcher source identity differs')
    if launch.get('dispatch_plan') != dispatch:
        raise ValueError('fresh dispatch launcher planning contract differs')
    entries = [*dispatch['entries'], dispatch['fallback']]
    sequences = launch.get('sequences')
    if not isinstance(sequences, dict) or set(sequences) != {str(e['tiling_key']) for e in entries}:
        raise ValueError('fresh dispatch launch sequences do not cover exactly the declared keys')
    symbols = set()
    for host in (source / 'op_host').glob('*.asc'):
        symbols.update(re.findall(r'\b(\w+)\s*<<<', host.read_text()))
    for entry in entries:
        sequence = sequences[str(entry['tiling_key'])]
        kernels = sequence.get('kernels') if isinstance(sequence, dict) else None
        auxiliary = sequence.get('auxiliary_tasks') if isinstance(sequence, dict) else None
        if (not isinstance(kernels, list) or not kernels
                or any(not isinstance(k, str) or k not in symbols for k in kernels)
                or entry['kernel_entry'] not in kernels
                or not isinstance(auxiliary, list) or any(not isinstance(a, str) for a in auxiliary)):
            raise ValueError('fresh dispatch launch sequence has an absent entry or malformed tasks')
    return launch


def frozen_workload_metadata(row):
    ref = row.get('metadata')
    if not isinstance(ref, dict) or sha(ref['path']) != ref.get('sha256'):
        raise ValueError('frozen workload metadata changed before registration')
    return load(ref['path'])


def fresh_build_target(task, candidate_artifacts=None):
    """Resolve a compiler target from the bound probe, never a family default."""
    from aprof_runtime.planning import validate_planning_contract
    task = Path(task)
    manifest = load(task / 'manifest.json')
    if manifest.get('version') != 'msprof_task_time_exploration_v2':
        raise ValueError('fresh build requires its fresh task manifest')
    ref = (manifest.get('architecture_profile') if candidate_artifacts is None
           else candidate_artifacts.get('architecture_profile'))
    if not isinstance(ref, dict) or sha(ref['path']) != ref.get('sha256'):
        raise ValueError('fresh build architecture profile is absent or changed')
    profile = validate_planning_contract('architecture_profile', load(ref['path']))
    arch = profile['npu_arch']
    if profile['architecture_id'] == 'unknown' or arch not in (2201, 3510):
        raise ValueError('fresh build rejects unknown or unsupported compiler architecture')
    compiler_status = profile.get('compiler', {}).get('status', 'unknown')
    if compiler_status == 'error' or (arch == 3510 and compiler_status != 'verified'):
        raise ValueError('fresh build lacks verified compiler identity for this architecture')
    return {'npu_arch': f'dav-{arch}', 'architecture_profile': ref,
            'compiler_status': compiler_status,
            'scope': 'Bound SDK target; compiler acceptance is established by the actual build, never by falling back to2201.'}


def register_proposal(run, operator, candidate_id, proposal_path):
    from prepare_trace_pilot import create_source_snapshot
    from collect_level1_traces import candidate_source_files
    run, split, task, parent, source = task_paths(run, operator, candidate_id)
    ledger = Campaign(run / split / 'ledger')
    proposal = load(proposal_path)
    if proposal.get('candidate_id') != candidate_id or Path(proposal['source_dir']).resolve() != source:
        raise ValueError('proposal source identity/path differs')
    parent_id = proposal['source_parent']
    if isinstance(parent_id, dict): parent_id = parent_id.get('candidate_id')
    parent_id = None if parent_id in (None, 'baseline') else parent_id
    state = ledger.state['tasks'][operator]
    baseline = ledger.config['tasks'][operator]['baseline_source_hash']
    control_hash = baseline if parent_id is None else state['candidates'][parent_id]['source_hash']
    control_source = task / 'baseline' if parent_id is None else task / 'candidates' / parent_id / 'op'
    before, after = candidate_source_files(control_source), candidate_source_files(source)
    changed = [p for p in sorted(set(before) | set(after)) if p not in before or p not in after or before[p].read_bytes() != after[p].read_bytes()]
    if not changed: raise ValueError('same source must add an observation, not a candidate')
    if any(not p.startswith(('op_host/', 'op_kernel/')) or p.endswith(('aprof_device_timer.h', 'data_utils.h')) for p in changed):
        raise ValueError('candidate changed protected input/oracle/build/harness files')
    content_identity = require_distinct_source(source, {'baseline': task / 'baseline', **{key: task / 'candidates' / key / 'op' for key in state['candidates']}})
    patch = ''.join(''.join(difflib.unified_diff(
        before[p].read_text().splitlines(True) if p in before else [],
        after[p].read_text().splitlines(True) if p in after else [], fromfile='parent/' + p, tofile='candidate/' + p)) for p in changed)
    patch_path = parent / 'optimization.patch'
    if patch_path.exists():
        if patch_path.read_text() != patch: raise ValueError('submitted patch differs from actual parent/source')
    else:
        with patch_path.open('x') as stream: stream.write(patch)
    source_binding = create_source_snapshot(source, parent / 'source.tar', root_label=candidate_id)
    save(parent / 'source-binding.json', {**source_binding, 'source_content_identity': content_identity})
    artifacts = {'proposal': pointer(proposal_path), 'source': pointer(parent / 'source.tar'), 'patch': pointer(patch_path)}
    if ledger.config.get('schema_version') == 'msprof_exploration_campaign_v2':
        from aprof_runtime.contracts import Context
        from aprof_runtime.jsonio import content_hash
        from aprof_runtime.planning import validate_planning_context, select_dispatch
        if proposal.get('optimization_stage') not in ('algorithm_parallel', 'execution'):
            raise ValueError('fresh source attempts require an explicit optimization stage')
        implementation = sha(parent / 'source.tar')
        basis = proposal.get('plan_basis_source_hash')
        if basis not in (baseline, control_hash) or proposal.get('implementation_source_hash') != implementation:
            raise ValueError('proposal algorithm basis or emitted implementation identity differs')
        evidence = {'optimization_stage': proposal['optimization_stage']}
        for name in ('architecture_profile', 'parallel_plan', 'dispatch_plan', 'graph_snapshot'):
            ref = proposal.get('artifacts', {}).get(name)
            if not isinstance(ref, dict) or sha(ref['path']) != ref['sha256']:
                raise ValueError('missing or changed fresh planning artifact: ' + name)
            artifacts[name] = ref
            value = load(ref['path'])
            key = 'graph_hash' if name == 'graph_snapshot' else name + '_ref'
            if proposal.get(key) != content_hash(value):
                raise ValueError('proposal canonical planning reference differs: ' + name)
            if name != 'graph_snapshot':
                evidence[name] = value
                evidence[key] = proposal[key]
        for name in ('author_draft', 'dispatch_launch'):
            ref = proposal.get('artifacts', {}).get(name)
            if not isinstance(ref, dict) or sha(ref['path']) != ref['sha256']:
                raise ValueError('missing or changed author/launch artifact: ' + name)
            artifacts[name] = ref
        fresh_dispatch_launch(source, artifacts['dispatch_launch'], evidence['dispatch_plan'])
        artifacts['graph_bundle'] = fresh_graph_bundle(run, artifacts['graph_snapshot'], proposal['graph_hash'])
        artifacts['planning_evidence'] = proposal.get('artifacts', {}).get('planning_evidence', [])
        for ref in artifacts['planning_evidence']:
            if sha(ref['path']) != ref['sha256']: raise ValueError('changed planning evidence')
        bindings = load(task / 'input-bindings.json')['cases']
        from level2_adapters import workload_metadata
        selections = []
        for row in bindings:
            metadata = workload_metadata(operator, frozen_workload_metadata(row))
            selected = select_dispatch(evidence['dispatch_plan'], metadata)
            context = Context.from_dict({'schema_version': '1.0.0', 'task_id': operator, 'operator': operator,
                'hardware_fingerprint': evidence['architecture_profile']['hardware_fingerprint'], 'budget': {},
                'evidence': evidence, 'workload': {'source_hash': control_hash, 'plan_basis_source_hash': basis,
                   'implementation_source_hash': implementation, 'metadata': metadata,
                   'tiling_key': selected['tiling_key'], 'workload_group': selected['group_id']}})
            validate_planning_context(context, execution=True)
            selections.append({'case_id': row['case_id'], 'metadata': metadata, **selected})
        if proposal.get('dispatch_selections') != selections:
            raise ValueError('declared dispatch selections differ from frozen workload metadata')
    guard_ref = proposal.get('artifacts', {}).get('semantic_guard_contract')
    if guard_ref is not None:
        if ledger.config.get('schema_version') != 'msprof_exploration_campaign_v2':
            raise ValueError('candidate guard revisions require fresh Level2 protocol')
        from level2_guard_contract import resolve
        resolve(task, parent, guard_ref, source_hash=sha(parent / 'source.tar'), oracle=True)
        artifacts['semantic_guard_contract'] = guard_ref
    ledger.register(event_id=candidate_id + '-register', workload=operator, candidate_id=candidate_id,
                    source_hash=sha(parent / 'source.tar'), patch_hash=sha(patch_path),
                    source_parent={'candidate_id': parent_id, 'source_hash': control_hash},
                    decision_basis=proposal['decision_basis'], probes=proposal.get('diagnostic_cases', []),
                    artifacts=artifacts)
    event(task, 'source_attempt_registered', {'candidate_id': candidate_id, 'changed_files': changed,
                                            'proposal': pointer(proposal_path), 'source': pointer(parent / 'source.tar')})
    return source_binding


def verify_source_snapshot(archive, source):
    from msprof_exploration_archive import native_tar_hash
    return native_tar_hash(archive, source)


def actual_costs(out):
    """Count recorded native work, including partial failed collections."""
    result = {'native_processes_started': 0, 'native_processes_completed': 0,
              'role_samples': 0, 'timed_complete_calls': 0, 'warmup_complete_calls': 0,
              'formal_target_kernel_launches': 0, 'correctness_complete_calls': 0,
              'unconfirmed_warmup_blocks': 0}
    for path in Path(out).rglob('journal.jsonl'):
        rows = []
        for line in path.read_bytes().splitlines():
            try: rows.append(json.loads(line))
            except ValueError: break  # An interrupted trailing record is retained.
        result['native_processes_started'] += int(any(r.get('type') == 'process_start' for r in rows))
        result['native_processes_completed'] += int(bool(rows) and rows[-1].get('type') == 'session_end' and rows[-1].get('exit_code') == 0)
        for row in rows:
            if row.get('type') == 'case_start': result['unconfirmed_warmup_blocks'] += 1
            elif row.get('type') == 'warmup_complete':
                result['warmup_complete_calls'] += 2 * row['calls_per_role']
                result['unconfirmed_warmup_blocks'] -= 1
            elif row.get('type') == 'sample':
                result['role_samples'] += 1
                result['timed_complete_calls'] += row['repeat']
                result['formal_target_kernel_launches'] += row['repeat'] * row['launches_per_call']
    for path in Path(out).rglob('native.json'):
        row = load(path)
        result['native_processes_started'] += 1
        result['native_processes_completed'] += int(row.get('exit_code') == 0)
        calls = row.get('profile_complete_calls', 0)
        if row.get('mode') == 'correctness': result['correctness_complete_calls'] += calls
        else: result['profile_complete_calls'] = result.get('profile_complete_calls', 0) + calls
        result['warmup_complete_calls'] += row.get('warmup_complete_calls', 0)
        result['formal_target_kernel_launches'] += calls * row.get('launches_per_call', 0)
    for path in Path(out).rglob('standalone/completion.json'):
        for key, value in load(path)['actual_costs'].items():
            if key != 'wall_seconds': result[key] = result.get(key, 0) + value
    # New scoped oracle logs record calls separately from Python process starts.
    # Standalone counters above already include their own oracle executions.
    for path in (Path(out) / 'evidence').rglob('*.execution.json'):
        row = load(path)
        if row.get('mode') == 'in_process_original_verifier_v1':
            for key in ('verifier_calls', 'verifier_processes_started'):
                result[key] = result.get(key, 0) + row[key]
    return result


def successful_correctness_binding(ledger, operator, candidate_id, parent, source_hash):
    """Select a completed same-source correctness stage without changing it."""
    stages = ledger.state['tasks'][operator]['stages']
    successful = [(sid, row) for sid, row in stages.items()
                  if row['kind'] == 'correctness' and row['candidate_id'] == candidate_id
                  and row['attempts'] and row['attempts'][-1]['outcome'] == 'success'
                  and row['plan'].get('source_hash') == source_hash]
    if not successful:
        raise ValueError('runtime assessment requires a successful same-source correctness stage')
    sid, row = max(successful, key=lambda entry: entry[1]['attempts'][-1]['start_order'])
    attempt = row['attempts'][-1]
    prefix = (candidate_id or 'baseline') + '-'
    group = sid.removeprefix(prefix)
    if (not sid.startswith(prefix) or not group or Path(group).name != group
            or row['plan'].get('case_ids') != ALL_CASES):
        raise ValueError('successful correctness stage identity or coverage differs')
    result_path = Path(parent) / 'stages' / group / 'result.json'
    ref = attempt.get('evidence', {}).get('result')
    if (ref != pointer(result_path) or attempt['evidence'].get('prepared_output_checked') is not True):
        raise ValueError('successful correctness result differs from ledger evidence')
    result = load(result_path)
    if (result.get('stage_id') != sid or result.get('candidate_id') != candidate_id
            or result.get('kind') != 'correctness' or result.get('status') != 'passed'):
        raise ValueError('successful correctness result identity or outcome differs')
    return {'correctness_stage_id': sid, 'correctness_result': ref,
            'correctness_directory': str(result_path.parent / 'evidence')}


def runtime_assessment(correctness, output, standalone=None, correctness_result=None):
    """Report observed native safety separately from the uninvoked formal gate."""
    correctness = Path(correctness)
    if correctness_result is not None:
        expected_path = correctness.parent / 'result.json'
        if correctness_result != pointer(expected_path):
            raise ValueError('bound correctness result changed before runtime assessment')
        bound = load(expected_path)
        if bound.get('kind') != 'correctness' or bound.get('status') != 'passed':
            raise ValueError('bound correctness stage was not successful')
    complete = load(correctness / 'completion.json')
    if complete['status'] != 'passed' or {int(c['case_id']) for c in complete['completed']} != set(ALL_CASES):
        raise ValueError('runtime assessment requires all twenty prepared correctness calls')
    refs = []
    for case in ALL_CASES:
        path = correctness / f'case_{case:02d}/native.json'
        row = load(path)
        if row.get('exit_code') != 0 or not all(row.get(k) is True for k in ['stream_destroyed', 'context_destroyed', 'finalized']):
            raise ValueError('native lifecycle did not complete safely')
        refs.append(pointer(path))
    if standalone is not None:
        original = load(Path(standalone) / 'completion.json')
        if original.get('status') != 'passed' or original.get('passed_count') != 20:
            raise ValueError('runtime assessment requires full standalone correctness')
        refs.append(pointer(Path(standalone) / 'completion.json'))
    result = {'status': 'passed', 'native_results': refs, 'correctness': pointer(correctness / 'completion.json'),
              'correctness_stage_result': correctness_result,
              'scope': 'Observed prepared native execution and successful teardown for all20 cases; no formal runtime gate is synthesized.',
              'new_native_execution': False, 'formal_admission': 'not_evaluated', 'episode_ref': None}
    save(output, result)
    return result


def prepare_timing(run, operator, candidate_id, group, *, purpose='search', final_candidates=None, calibration_path=None, calibration_by_relation=None, epoch='epoch-01', capture_storage=None):
    measurement_options({'epoch': epoch,
        **({'capture_storage': capture_storage} if capture_storage is not None else {}),
        **({'calibration_path': calibration_path} if calibration_path is not None else {}),
        **({'calibration_by_relation': calibration_by_relation} if calibration_by_relation is not None else {})})
    run, split, task, parent, _ = task_paths(run, operator, candidate_id)
    ledger = Campaign(run / split / 'ledger')
    candidate = ledger.state['tasks'][operator]['candidates'][candidate_id]
    baseline = ledger.config['tasks'][operator]['baseline_source_hash']
    cases = ALL_CASES if purpose == 'final' else [1, 8, 14, 20] + [p['case_id'] for p in candidate['probes']]
    controls = [('direct_parent', candidate['source_parent']['candidate_id'] or 'baseline')]
    if candidate['source_parent']['source_hash'] != baseline: controls.append(('original_baseline', 'baseline'))
    if set(calibration_by_relation or {}) - {relation for relation, _ in controls}:
        raise ValueError('calibration override names an absent comparison relation')
    from msprof_raw_storage import LOCAL
    if capture_storage == LOCAL and calibration_path is None and set(calibration_by_relation or {}) != {relation for relation, _ in controls}:
        raise ValueError('local timing requires an explicit fresh calibration for every comparison')
    planning = parent / 'plans' / group
    planning.mkdir(parents=True, exist_ok=False)
    cohorts = []
    for relation, control in controls:
        control_dir = task if control == 'baseline' else task / 'candidates' / control
        roles_path = planning / (relation + '-roles.json')
        comparison_manifest(control_dir / 'build/build_manifest.json', parent / 'build/build_manifest.json', roles_path)
        name = candidate_id + '-' + group + '-' + relation.replace('_', '-')
        plan = cohort_plan(task, roles_path, run / 'tools/timing/build.json', cases, 'ab', name, epoch=epoch, **({'capture_storage': capture_storage} if capture_storage is not None else {}))
        save(planning / (relation + '-cohort.json'), plan)
        cohorts.append({'relation': relation, 'control_candidate_id': control,
                        'plan': pointer(planning / (relation + '-cohort.json'))})
        if relation in (calibration_by_relation or {}):
            cohorts[-1]['calibration_report'] = pointer(calibration_by_relation[relation])
    save(planning / 'comparisons.json', {'candidate_id': candidate_id, 'cohorts': cohorts, 'case_ids': cases})
    plan = ledger.timing_plan(operator, candidate_id, purpose=purpose, manifest_ref=sha(planning / 'comparisons.json'),
                       final_candidate_ids=final_candidates, cohorts=cohorts)
    if calibration_path is not None:
        plan['calibration_report'] = pointer(calibration_path)
    save(planning / 'stage-plan.json', plan)
    event(task, 'timing_plan_frozen', {'candidate_id': candidate_id, 'group': group, 'plan': pointer(planning / 'stage-plan.json')})
    return planning / 'stage-plan.json'


def run_stage(run, operator, candidate, kind, group, cases=None, plan_path=None, *, capture_storage=None, epoch='epoch-01'):
    validate_stage_options(kind, plan_path, capture_storage=capture_storage, epoch=epoch)
    run, split, task, parent, source = task_paths(run, operator, candidate)
    ledger = Campaign(run / split / 'ledger')
    cid = None if candidate == 'baseline' else candidate
    out = parent / 'stages' / group
    if out.exists(): raise FileExistsError(out)
    cases = ALL_CASES if cases is None else list(cases)
    stage_id = candidate + '-' + group
    if kind == 'timing' or (kind == 'control' and plan_path is not None):
        if plan_path is None: raise ValueError('timing needs a frozen plan')
        plan = load(plan_path)
    else:
        plan = {'case_ids': cases, 'source_hash': sha(task / 'baseline-source.tar' if cid is None else parent / 'source.tar'),
                'protocol': ledger.config['policy']['protocol'], 'group': group, 'producer': pointer(__file__)}
        if kind == 'control':
            plan['control_type'] = 'aa'
            plan['control_phase'] = group
            plan['manifest_ref'] = sha(task / 'manifest.json')
            plan['cohort'] = cohort_plan(task, parent / 'build/build_manifest.json', run / 'tools/timing/build.json', cases, 'aa', group, epoch=epoch, **({'capture_storage': capture_storage} if capture_storage is not None else {}))
        if kind == 'profile': plan['capture_window'] = {'warmup': 10, 'repeat': 5, 'full_operator': True}
        if kind == 'runtime':
            plan.update(successful_correctness_binding(ledger, operator, cid, parent, plan['source_hash']))
            plan['depends_on'] = [plan['correctness_stage_id']]
    ledger.validate_start(workload=operator, candidate_id=cid, stage_id=stage_id, kind=kind, plan=plan)
    out.mkdir(parents=True, exist_ok=False)
    save(out / 'stage-plan.json', plan)
    ledger.start(event_id=operator + '-' + stage_id + '-start', workload=operator, candidate_id=cid, stage_id=stage_id, kind=kind, plan=plan)
    event(task, 'stage_started', {'candidate_id': cid, 'stage': stage_id, 'kind': kind, 'plan': pointer(out / 'stage-plan.json')})
    started = time.time(); error = None; native_started = False; result = None
    try:
        if kind == 'build':
            archive = task / 'baseline-source.tar' if cid is None else parent / 'source.tar'
            verify_source_snapshot(archive, source)
            if ledger.config.get('schema_version') == 'msprof_exploration_campaign_v2':
                candidate_artifacts = None if cid is None else ledger.state['tasks'][operator]['candidates'][cid]['artifacts']
                target = fresh_build_target(task, candidate_artifacts)
                save(out / 'build-target.json', target)
                result = build_operator(source, operator, parent / 'build', npu_arch=target['npu_arch'])
            else:
                result = build_operator(source, operator, parent / 'build')
            verify_source_snapshot(archive, source)
        elif kind in ('correctness', 'profile'):
            if kind == 'correctness':
                from msprof_exploration_standalone import correctness as standalone_correctness
                standalone_correctness(task, parent / 'build/build_manifest.json',
                                       load(task / 'input-origin.json')['path'], out / 'standalone', cases, reuse_verifier=True)
            result = diagnostic_group(run, operator, candidate, kind, cases, out / 'evidence')
        elif kind == 'runtime':
            correctness_directory = Path(plan['correctness_directory'])
            result = runtime_assessment(correctness_directory, out / 'runtime.json',
                                        correctness_directory.parent / 'standalone', plan['correctness_result'])
        elif kind == 'control': result = collect_cohort(plan['cohort'], out / 'cohort')
        elif kind == 'timing':
            calibration_ref = plan.get('calibration_report')
            calibration_path = calibration_ref['path'] if calibration_ref else task / 'stages/aa-initial/cohort/report.json'
            if calibration_ref and sha(calibration_path) != calibration_ref['sha256']:
                raise ValueError('frozen calibration report changed')
            calibration = load(calibration_path) if calibration_ref or any(not row.get('calibration_report') for row in plan['cohorts']) else None
            results = []
            resolved = []
            for cohort in plan['cohorts']:
                if sha(cohort['plan']['path']) != cohort['plan']['sha256']: raise ValueError('cohort plan changed')
                selected = calibration
                if cohort.get('calibration_report'):
                    ref = cohort['calibration_report']
                    if sha(ref['path']) != ref['sha256']: raise ValueError('frozen cohort calibration report changed')
                    selected = load(ref['path'])
                frozen = load(cohort['plan']['path'])
                validate_calibration_storage(frozen, selected)
                resolved.append((cohort, frozen, selected))
            for cohort, frozen, selected in resolved:
                directory = out / cohort['relation']
                results.append(collect_cohort(frozen, directory, selected))
            result = {'comparisons': results}
        else: raise ValueError('unsupported explicit stage')
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc)}
    native_started = native_started or native_started_in(out)
    costs = actual_costs(out)
    native_started = native_started or costs['native_processes_started'] > 0
    costs['wall_seconds'] = int(time.time() - started)
    if kind == 'build':
        costs['candidate_build_commands' if cid else 'baseline_build_commands'] = int((parent / 'build/build-execution/started.json').exists())
        costs['cmake_configure_commands'] = int((parent / 'build/configure-execution/started.json').exists())
    result_record = {'status': 'failed' if error else 'passed', 'kind': kind, 'stage_id': stage_id, 'candidate_id': cid,
                     'started_at': started, 'ended_at': time.time(), 'error': error, 'native_started': native_started,
                     'actual_costs': costs, 'cost_scope': 'Confirmed lower bounds; incomplete native sections remain unknown. formal_target_kernel_launches excludes warmup.', 'formal_admission': 'not_evaluated', 'graph_policy_eligible': False, 'episode_ref': None}
    save(out / 'result.json', result_record)
    evidence = {'result': pointer(out / 'result.json')}
    if kind == 'build' and (out / 'build-target.json').exists(): evidence['build_target'] = pointer(out / 'build-target.json')
    if kind == 'build' and (parent / 'build/build_manifest.json').exists(): evidence['build'] = pointer(parent / 'build/build_manifest.json')
    if kind == 'correctness': evidence['prepared_output_checked'] = error is None
    if kind == 'runtime' and error is None: evidence['runtime'] = pointer(out / 'runtime.json')
    outcome = 'success' if error is None else 'failed'
    if error and kind == 'build': outcome = 'build_failed'
    ledger.finish(event_id=operator + '-' + stage_id + '-finish', workload=operator, stage_id=stage_id, outcome=outcome,
                  evidence=evidence, native_started=native_started, formal_samples=costs['role_samples'],
                  actual_costs=costs, reason=json.dumps(error) if error else None)
    event(task, 'stage_completed', {'candidate_id': cid, 'stage': stage_id, 'result': pointer(out / 'result.json')})
    print(json.dumps(result_record), flush=True)
    return result_record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ['run', 'operator', 'candidate', 'kind', 'group']: parser.add_argument('--' + key, required=True)
    parser.add_argument('--cases', default=','.join(map(str, ALL_CASES)))
    parser.add_argument('--plan')
    args = parser.parse_args()
    result = run_stage(args.run, args.operator, args.candidate, args.kind, args.group,
                       [int(x) for x in args.cases.split(',')], args.plan)
    raise SystemExit(0 if result['status'] == 'passed' else 1)


if __name__ == '__main__': main()
