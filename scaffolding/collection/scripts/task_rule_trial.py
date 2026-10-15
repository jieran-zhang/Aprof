#!/usr/bin/env python3
"""Prepare one frozen rule trial, or dispatch it once under a original frozen-budget job.

Preparation is CPU/file work. Run invokes the controller, including its real
reviewer and hardware stages, only when explicitly requested. Evidence stays
local; collection/archiving and Teacher admission are separate responsibilities.
"""
from task_budget import budget_seconds, positive, teacher_budget, rule_execution_job, collection_policy
import argparse
import json
from pathlib import Path
import sys
import time

import task_screen_bridge as screen
from eval_tool_broker import BUDGET_POLICY
from isolated_eval_worker import require_worker_build_budget_enforcement
from run_aprof_job import run as run_job
from task_rule_admission import IDENTITY, PROTOCOL, TASK_PROTOCOL, verify_task_attempt_roster
from task_rule_correctness import preflight_boundary_plan
from timing_admission import BOUNDARY_SIZES, THRESHOLDS, read, require

HERE = Path(__file__).resolve().parent
CONTROLLER = HERE / 'task_rule_controller.py'
MODEL = {'name': 'gpt-6-sol', 'reasoning_effort': 'max'}
REVIEW_KEYS = {'review_contract', 'review_checklist', 'review_boundaries'}
CHOICES = {'exp': (3, 'mte2_instructions'), 'sigmoid': (8, 'vector_wait_ratio')}
bridge, LocalEvidence = screen.bridge, screen.LocalEvidence
PRODUCERS = (
    'sdk_build_evidence.py', 'task_budget.py', 'task_rule_trial.py', 'task_rule_campaign.py', 'task_rule_controller.py', 'task_rule_recorder.py', 'task_rule_admission.py',
    'task_outer_admission.py', 'task_rule_correctness.py', 'task_profile_admission.py',
    'archive_task_rule_sources.py', 'archived_rule_correctness.py', 'shared_validation_adapter.py',
    'shared_rule_adapter.py', 'shared_mechanism_adapter.py', 'local_controller_bridge.py',
    'task_screen_bridge.py', 'screen_parser.py', 'aprof_layout.py', 'run_aprof_job.py',
    'timing_admission.py', 'eval_candidate_evidence.py', 'eval_tool_broker.py', 'isolated_eval_worker.py',
    'qualify_eval_tools.py', 'evaluate_skill_release.py', 'review_packet.py', 'validation_host_evaluator.py',
    'validation_operator_adapter.py', 'qualify_shared_timing_v051.py', 'controller_admission.py')


def producer_paths():
    release = bridge.RELEASE
    paths = {HERE/name for name in PRODUCERS}
    paths.add(HERE.parents[1]/'tools/verify_teacher_wiki.py')
    paths.add(release/'tools/release.py')
    for base, pattern in [('runtime/src', '*.py'), ('schemas', '*.json'),
            ('skills/ascendc-aprof-profiling/scripts', '*.py'),
            ('skills/ascendc-aprof-profiling/assets', '*.h'),
            ('skillgraph/source/v0002', '*'), ('skillgraph/versions/v0002', '*')]:
        paths.update(p for p in (release/base).rglob(pattern) if p.is_file() and '__pycache__' not in p.parts)
    paths.add(release/'skillgraph/registry.json')
    return sorted(paths)


def verify_frozen_files(local, plan):
    files = read(local, plan['frozen_files_ref'])
    require({str(path) for path in producer_paths()} <= files.keys(), 'execution/replay producer roster changed')
    for path, reference in files.items():
        require(pointer(path)['sha256'] == reference, 'frozen trial file changed')


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    bridge.save(path, value)
    return path


def regular(path):
    path = Path(path).absolute()
    require(path.resolve(strict=True) == path and path.is_file()
            and not any(p.is_symlink() for p in (path, *path.parents)), 'noncanonical trial file')
    return path


def pointer(path):
    path = regular(path)
    return {'path': str(path), 'sha256': bridge.file_hash(path)}


def _freeze_inputs(local, operator, binding):
    """Compare original input bytes to the already frozen ROUND inventories."""
    root = screen.rule.ROUND / operator
    frozen = load(binding['freeze']['path'])
    protocol_path = root / 'candidate-qualification/protocol.json'
    require(local.register_artifact(protocol_path) == frozen['attempts']['candidate-qualification']['protocol_ref'],
            'original candidate protocol changed')
    original = load(protocol_path)
    inventory_path = root / 'candidate-qualification/input-inventory.json'
    require(local.register_artifact(inventory_path) == original['input_inventory_ref'], 'original input inventory changed')
    expected = load(inventory_path)
    boundary_path = root / 'boundary-plan.json'
    boundary_ref = local.register_artifact(boundary_path)
    require(boundary_ref == original['boundary_plan_ref'], 'original boundary plan changed')
    boundary = load(boundary_path)
    wanted = [(dtype, size) for dtype in THRESHOLDS for size in BOUNDARY_SIZES[operator]]
    cases = boundary['cases']
    require(boundary['schema_version'] == 1 and boundary['operator'] == operator
            and [(c['dtype'], c['numel']) for c in cases] == wanted
            and [c['case_id'] for c in cases] == list(range(101, 101 + len(wanted)))
            and boundary['verifier_ref'] == binding['roles']['baseline']['files']['scripts/verify_result.py'],
            'original 42/57 boundary plan differs')
    result = {}
    for group, ids in [('prepared', range(1, 21)), ('boundary-inputs', range(101, 101 + len(wanted)))]:
        directory = root / group
        require({p.name for p in directory.glob('case_*') if p.is_dir()}
                == {f'case_{cid:02d}' for cid in ids}, 'original case roster differs')
        for cid in ids:
            path = regular(directory / f'case_{cid:02d}/metadata.json')
            metadata = load(path)
            input_path = regular(metadata['input'])
            require(input_path == path.parent / 'input.bin' and metadata['case_id'] == cid
                    and metadata['dtype'] in THRESHOLDS
                    and input_path.stat().st_size == metadata['numel'] * (4 if metadata['dtype'] == 'float32' else 2),
                    'prepared case identity/path/size differs')
            for item in (path, input_path):
                actual = local.register_artifact(item)
                require(expected[str(item)] == actual, 'frozen input changed')
                result[str(item)] = actual
            if group == 'boundary-inputs':
                case = cases[cid - 101]
                attrs = metadata.get('attrs', {k: metadata[k] for k in ('base', 'scale', 'shift') if k in metadata})
                require(all(case[k] == metadata[k] for k in ('case_id', 'shape', 'dtype', 'numel'))
                        and case.get('attrs', {}) == attrs
                        and case['input_files'] == {str(input_path): result[str(input_path)]},
                        'boundary case differs from its frozen plan')
    return result, boundary_ref, original


def prepare(output, *, operator, run_id, qualification, review_inputs, candidate_plan, campaign, physical_device=0):
    require(operator in CHOICES and isinstance(run_id, str) and run_id.strip(), 'invalid fixed rule identity')
    require(bridge.RELEASE.name == '1.0.0', 'rule trial requires explicitly selected 1.0.0')
    require(type(physical_device) is int and physical_device >= 0, 'invalid physical device')
    output = Path(output).absolute()
    require(output.resolve() == output, 'trial output must be canonical')
    mount = bridge.timing.old.select_mount(Path('/proc/self/mountinfo').read_text(), output)
    require(mount['filesystem_type'] in bridge.timing.old.LOCAL_PROFILE_FILESYSTEMS, 'trial output must be task-local')
    output.mkdir(mode=0o700, exist_ok=False)
    local = LocalEvidence(output / 'records')
    try:
        qualification_ref = pointer(qualification)
        require_worker_build_budget_enforcement(qualification_ref, model=MODEL['name'], effort=MODEL['reasoning_effort'])
        review = load(regular(review_inputs))
        require(set(review) == REVIEW_KEYS, 'review input pointers differ')
        frozen_files = {}

        def bind(path, expected=None):
            path = regular(path)
            digest = local.register_artifact(path)
            require(expected is None or digest == expected, 'frozen trial file changed')
            frozen_files[str(path)] = digest
            return digest

        bind(qualification, qualification_ref['sha256'])
        bind(review_inputs)
        for ref in review.values():
            require(set(ref) == {'path', 'sha256'}, 'review pointer fields differ')
            bind(ref['path'], ref['sha256'])
        import sdk_build_evidence as sdk_build
        sdk_binding = sdk_build.freeze(local, review['review_contract'])
        if sdk_binding is not None:
            bind(sdk_binding['path'], sdk_binding['sha256'])
            for ref in sdk_build.value(sdk_binding)['files'].values():
                bind(ref['path'], ref['sha256'])
        proposal = load(regular(candidate_plan))
        case, metric = CHOICES[operator]
        choice = dict(case_id=case, kernel=operator+'_kernel', metric=metric, expected_direction='decrease')
        require(proposal.get('actual_parent') == 'original baseline' and proposal.get('intent')
                and proposal.get('mechanism') == choice
                and isinstance(proposal.get('source_anchors'), list) and proposal['source_anchors'],
                'candidate plan must retain the original source mechanism and anchors')
        bind(candidate_plan)
        binding = screen.rule.frozen_binding(operator)
        campaign_ref = bind(campaign)
        schedule = load(campaign)
        import aprof_runtime
        require(set(schedule) - {'collection_stop_policy', 'scope_amendment_ref'} == {'schema_version', 'kind', 'protocol', 'task_protocol', 'runtime_build',
                'model', 'budget_seconds', 'budget_policy', 'reviewer_token_limit', 'max_attempts_per_operator',
                'stop_on_failure', 'resampling', 'created_at', 'attempts', 'source_freezes',
                'trace_index_sha256', 'split_index_sha256', 'prior_campaign_refs'} and schedule['schema_version'] == 1
                and schedule['kind'] == 'teacher_task_rule_campaign' and schedule['protocol'] == PROTOCOL
                and schedule['task_protocol'] == TASK_PROTOCOL
                and schedule['runtime_build'] == 'aprof-runtime/'+aprof_runtime.__version__
                and schedule['model'] == MODEL and budget_seconds(schedule) > 0
                and schedule['budget_policy'] == BUDGET_POLICY and schedule['reviewer_token_limit'] is None
                and schedule['max_attempts_per_operator'] == 1
                and schedule['stop_on_failure'] is True and schedule['resampling'] == 'none'
                and 0 < schedule['created_at'] <= time.time(), 'finite Teacher campaign differs')
        collection_policy(schedule)
        from task_rule_campaign import registered_operators
        if 'scope_amendment_ref' in schedule:
            scope = schedule['scope_amendment_ref']
            require(set(scope) == {'path', 'sha256'}, 'campaign scope pointer differs')
            bind(scope['path'], scope['sha256'])
        operators = registered_operators(schedule, local)
        attempts = schedule['attempts']
        require(isinstance(attempts, list) and len(attempts) == len(operators)
                and [a['operator'] for a in attempts] == list(operators)
                and len({a['run_id'] for a in attempts}) == len({a['candidate_id'] for a in attempts}) == len(operators),
                'campaign must register exactly one attempt for each frozen operator')
        freezes = []
        for attempt in attempts:
            original_binding = screen.rule.frozen_binding(attempt['operator'])
            require(set(attempt) == set(IDENTITY)
                    and attempt['candidate_id'] == attempt['run_id']+'-candidate'
                    and attempt['source_hashes'] == {r:original_binding['roles'][r]['sha256'] for r in screen.ROLES},
                    'campaign original source identity differs')
            freezes.append(original_binding['freeze'])
            bind(original_binding['freeze']['path'], original_binding['freeze']['sha256'])
        require(schedule['source_freezes'] == freezes and any(a['operator'] == operator and a['run_id'] == run_id
                for a in attempts), 'trial was not registered in the finite campaign')
        bind(HERE.parents[3]/'optimization-traces/index.json', schedule['trace_index_sha256'])
        bind(HERE.parents[1]/'benchmarks/cannbench/split_index.json', schedule['split_index_sha256'])
        workspace = output / 'worker/root/work'
        workspace.mkdir(parents=True, mode=0o700)
        roles = {}
        for role in screen.ROLES:
            source = screen.rule.ROUND / operator / role
            values = screen.rule.source_tree(source)
            require(screen.base.inventory(values) == binding['roles'][role]['files'], 'original role source changed')
            target = workspace / role
            target.mkdir()
            for name, data in values.items():
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                bind(source / name, binding['roles'][role]['files'][name])
                bind(path, binding['roles'][role]['files'][name])
            roles[role] = target
            bind(binding['roles'][role]['path'], binding['roles'][role]['sha256'])
        for anchor in proposal['source_anchors']:
            require(set(anchor) == {'path', 'line', 'why'}, 'candidate source anchor fields differ')
            path = regular(workspace/'candidate'/anchor['path'])
            require(path.is_relative_to(workspace/'candidate') and type(anchor['line']) is int
                    and 1 <= anchor['line'] <= len(path.read_text().splitlines())
                    and isinstance(anchor['why'], str) and anchor['why'].strip(), 'candidate source anchor differs')
        save(workspace / 'candidate_plan.json', proposal)
        bind(workspace / 'candidate_plan.json')
        assembly = output / 'assembly'
        proof = screen.assemble(operator, roles, assembly,
            expected_roles={r: binding['roles'][r]['files'] for r in screen.ROLES}, expected_headers=screen.rule.HEADERS)
        for name, reference in proof['adapted_files'].items():
            bind(assembly / 'source' / name, reference)
        for path, reference in proof['producer_files'].items():
            bind(path, reference)
        for path in [*producer_paths(), CONTROLLER]:
            bind(path)
        source_review_ref = bind(assembly / 'source-review.json')
        inputs, boundary_ref, original = _freeze_inputs(local, operator, binding)
        boundary=read(local,boundary_ref)
        oracle_refs={boundary['generator_ref'],boundary['verifier_ref']}
        boundary_oracles={path:bind(path,reference) for path,reference in original['oracle_files'].items()
                          if reference in oracle_refs}
        preflight_boundary_plan(local,operator=operator,
            source_hashes={r:binding['roles'][r]['sha256'] for r in screen.ROLES},
            boundary_plan_ref=boundary_ref,oracle_files=boundary_oracles)
        frozen_files.update(inputs)
        root = screen.rule.ROUND / operator
        history = [bind(binding['freeze']['path'], binding['freeze']['sha256'])]
        require(isinstance(schedule['prior_campaign_refs'], list), 'prior campaign pointers must be explicit')
        for reference in schedule['prior_campaign_refs']:
            require(set(reference) == {'path', 'sha256'}, 'prior campaign pointer differs')
            history.append(bind(reference['path'], reference['sha256']))
        for name in ('scope.json', 'historical-closure.json', 'diagnostic-summary.json', 'execution-costs.json'):
            history.append(bind(root / name))
        for kind, refs in load(binding['freeze']['path'])['attempts'].items():
            for name, reference in [('protocol.json', refs['protocol_ref']), ('registration.json', refs['registration_ref'])]:
                history.append(bind(root / kind / name, reference))
            for name in ('attempt-roster.json', 'closure.json'):
                history.append(bind(root / kind / name))
        history.append(bind(screen.rule.ROUND / 'round-plan.json'))
        # These are references to retained failed attempts, not a new acceptance verdict.
        require(original['profile_sentinel'] == case and set(original['mechanism_metrics']) == {metric},
                'original fixed profile choice differs')
        profile_ref = local.register_json({'choice': choice, 'specs': original['mechanism_metrics']})
        screen_ref = local.register_json(dict(schema_version=1, protocol=screen.PROTOCOL, operator=operator,
            case_ids=screen.CASES[operator], repeat=100, pairs=6, prepared_dir=str(root/'prepared'),
            output_dir=str(output/'screen'), physical_device=physical_device,
            profiler='/usr/local/Ascend/cann-9.0.0/tools/profiler/bin/msprof'))
        plan = dict(schema_version=1, directory=str(output), release=str(bridge.RELEASE), model=MODEL,
            boundary_oracle_files=boundary_oracles,
            review_inputs=review, worker_qualification=qualification_ref, assembly=str(assembly),
            prepared_dir=str(root/'prepared'), boundary_dir=str(root/'boundary-inputs'),
            scratch_dir=str(output/'measurement-scratch'), physical_device=physical_device,
            profiler='/usr/local/Ascend/cann-9.0.0/tools/profiler/bin/msprof',
            launch_path=str(output/'dispatcher-launch.json'), frozen_files_ref=local.register_json(frozen_files))
        if sdk_binding is not None:
            plan['sdk_build_binding_ref'] = sdk_binding
        plan_ref = local.register_artifact(save(output/'controller-plan.json', plan))
        job = dict(job_id=run_id, argv=[str(Path(sys.executable).resolve()), str(CONTROLLER),
            '--anchor', str(output/'anchor.json'), '--local-index', str(output/'prepared-local-index.json')],
            cwd=str(HERE.parents[2]), output_dir=str(output/'job'), timeout_seconds=budget_seconds(schedule),
            environment={'APROF_SKILL_LIB':str(bridge.RELEASE), 'PYTHONDONTWRITEBYTECODE':'1',
                'ASCEND_RT_VISIBLE_DEVICES':str(physical_device),
                'APROF_PHYSICAL_DEVICE':str(physical_device), 'APROF_LOGICAL_DEVICE':'0'})
        job_ref = local.register_artifact(save(output/'job.json', job))
        anchor = dict(schema_version=1, protocol=PROTOCOL, task_protocol=TASK_PROTOCOL, purpose='promotion',
            operator=operator, run_id=run_id, candidate_id=run_id+'-candidate',
            source_hashes={r:binding['roles'][r]['sha256'] for r in screen.ROLES},
            created_at=time.time(), budget_seconds=budget_seconds(schedule), job_ref=job_ref, controller_plan_ref=plan_ref,
            campaign_ref=campaign_ref,
            input_inventory_ref=local.register_json(inputs), boundary_plan_ref=boundary_ref,
            screen_plan_ref=screen_ref, profile_plan_ref=profile_ref, source_review_ref=source_review_ref,
            history_refs=list(dict.fromkeys(history)))
        if collection_policy(schedule) is not None:
            anchor['collection_stop_policy']=collection_policy(schedule)
        anchor_ref = local.register_artifact(save(output/'anchor.json', anchor))
        index = local.write_index(output/'prepared-local-index.json')
        result = dict(schema_version=1, status='prepared', anchor_ref=anchor_ref, job_ref=job_ref,
            controller_plan_ref=plan_ref, local_index=pointer(index), archive_performed=False)
        save(output/'prepared.json', result)
        return result
    except Exception as error:
        save(output/'preparation-failure.json', {'type':type(error).__name__, 'message':str(error)})
        local.write_index(output/'preparation-partial-index.json')
        raise


def run(output, *, expected_anchor):
    began, wall = time.monotonic(), time.time()
    output = Path(output).absolute()
    prepared = load(output/'prepared.json')
    require(prepared['anchor_ref'] == expected_anchor == pointer(output/'anchor.json')['sha256'], 'trusted anchor differs')
    require(prepared['local_index'] == pointer(output/'prepared-local-index.json'), 'prepared local index changed')
    local = LocalEvidence.from_index(output/'prepared-local-index.json')
    anchor = read(local, expected_anchor)
    plan, job = read(local, anchor['controller_plan_ref']), read(local, anchor['job_ref'])
    require(plan['directory'] == str(output) and plan['launch_path'] == str(output/'dispatcher-launch.json')
            and teacher_budget(lambda ref: read(local, ref), anchor) == positive(job['timeout_seconds'])
            and job['output_dir'] == str(output/'job')
            and job['argv'] == [str(Path(sys.executable).resolve()), str(CONTROLLER), '--anchor', str(output/'anchor.json'),
                               '--local-index', str(output/'prepared-local-index.json')], 'prepared dispatcher job differs')
    require(not (output/'job').exists() and not (output/'controller-start.json').exists(), 'trial already attempted')
    for key in ('job_ref', 'controller_plan_ref', 'input_inventory_ref', 'boundary_plan_ref',
                'screen_plan_ref', 'profile_plan_ref', 'source_review_ref', 'campaign_ref'):
        local.verify_artifact(anchor[key])
    for reference in anchor['history_refs']:
        local.verify_artifact(reference)
    verify_frozen_files(local, plan)
    budget=teacher_budget(lambda ref: read(local, ref), anchor)
    issued=time.monotonic()
    launch = dict(schema_version=2, anchor_ref=expected_anchor, job_ref=anchor['job_ref'],
                  started_at=wall, started_monotonic=began, monotonic_deadline=began+budget,
                  issued_monotonic=issued, child_timeout_seconds=began+budget-issued)
    save(output/'dispatcher-launch.json', launch)
    launch_ref = local.register_artifact(output/'dispatcher-launch.json')  # Exclusive even after a failed/partial prior attempt.
    result = dict(schema_version=1, status='failed', anchor_ref=expected_anchor,
                  archive_performed=False, admission_authority=False, error=None)
    try:
        actual_job=rule_execution_job(lambda ref: read(local, ref), anchor, job, launch)
        execution = run_job(actual_job)
        index = output/'controller-local-index.json'
        if index.exists():
            child = LocalEvidence.from_index(index)
            require(child.directory == local.directory, 'child local evidence workspace changed')
            require(all(ref == launch_ref for ref, path in child._paths.items()
                        if path == output/'dispatcher-launch.json'), 'child changed the parent launch reference')
            # Early failures may not index the launch. Retain parent identities;
            # the child reader already advances the shared record sequence.
            child._paths.update(local._paths)
            local = child
            local.register_artifact(index)
        local.verify_artifact(launch_ref)
        execution_ref = local.register_artifact(output/'job/execution.json')
        require(read(local, execution_ref) == execution, 'actual execution receipt differs')
        for name in ('stdout', 'stderr'):
            ref = execution[name]
            require(local.register_artifact(ref['path']) == ref['sha256'], 'actual dispatcher log changed')
        result['execution_ref'] = execution_ref
        child_path = output/'controller-result.json'
        if child_path.exists():
            result['controller_result_ref'] = local.register_artifact(child_path)
            terminal = load(child_path)
            require(terminal.get('anchor_ref') == expected_anchor, 'child result anchor differs')
            if terminal.get('child_report_ref'):
                report = read(local, terminal['child_report_ref'])
                require('execution_ref' not in report, 'child attempted to bind its own exit')
                expected = {k: anchor[k] for k in IDENTITY}
                expected.update(anchor_ref=expected_anchor, protocol_ref=report['protocol_ref'],
                    qualification_registration_ref=report['qualification_registration_ref'], execution_ref=execution_ref)
                result.update(child_report_ref=terminal['child_report_ref'], expected=expected,
                    report_ref=local.register_json(dict(report, execution_ref=execution_ref)),
                    measurement_expected=terminal.get('measurement_expected'))
            if (execution['status'] == 'passed' and execution['exit_code'] == 0 and not execution.get('error')
                    and 0 < execution['duration_seconds'] <= actual_job['timeout_seconds']
                    and time.monotonic() <= launch['monotonic_deadline'] and terminal.get('status') == 'passed'
                    and result.get('report_ref')):
                verify_frozen_files(local, plan)
                verify_task_attempt_roster(local, result['report_ref'], expected=result['expected'])
                result['status'] = 'completed_child'  # Outer component/gate replay remains required.
        if result['status'] == 'failed':
            result['error'] = {'type':'ChildFailure', 'message':'real child failed or did not produce a complete handoff'}
    except Exception as error:
        result['error'] = {'type':type(error).__name__, 'message':str(error)}
    finally:
        # Even a malformed child handoff must retain the actual dispatcher exit.
        execution_path = output/'job/execution.json'
        if execution_path.is_file():
            result['execution_ref'] = local.register_artifact(execution_path)
            for ref in load(execution_path).get('stdout', {}), load(execution_path).get('stderr', {}):
                if ref.get('path') and Path(ref['path']).is_file():
                    local.register_artifact(ref['path'])
        result['finished_at'] = time.time()
        local.register_artifact(save(output/'dispatcher-result.json', result))
        local.write_index(output/'dispatcher-local-index.json')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('--output', required=True, type=Path)
    prep.add_argument('--operator', required=True, choices=tuple(CHOICES))
    prep.add_argument('--run-id', required=True)
    prep.add_argument('--qualification', required=True, type=Path)
    prep.add_argument('--review-inputs', required=True, type=Path)
    prep.add_argument('--candidate-plan', required=True, type=Path)
    prep.add_argument('--campaign', required=True, type=Path)
    prep.add_argument('--physical-device', type=int, default=0)
    dispatch = commands.add_parser('run')
    dispatch.add_argument('--output', required=True, type=Path)
    dispatch.add_argument('--expected-anchor', required=True)
    args = vars(parser.parse_args()); action = args.pop('action')
    result = prepare(**args) if action == 'prepare' else run(**args)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] in ('prepared', 'completed_child') else 2


if __name__ == '__main__':
    raise SystemExit(main())
