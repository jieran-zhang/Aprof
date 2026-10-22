"""Shared task budgets and real process costs, independent of any benchmark.

A new segment may spend only the remainder of one frozen budget. Earlier
launches, deadlines and failed exits are immutable evidence, not renewed leases.
"""
from datetime import datetime
import math
import re

from .errors import ContractError


PLAN_KEYS = {'schema_version', 'kind', 'task_id', 'scope_ref', 'budget_seconds', 'collection_stop_policy'}
LAUNCH_KEYS = {'schema_version', 'kind', 'budget_ref', 'task_id', 'job_ref', 'prior_terminal_refs',
               'started_at', 'started_monotonic', 'issued_monotonic', 'deadline_monotonic', 'child_timeout_seconds'}
TERMINAL_KEYS = {'schema_version', 'kind', 'launch_ref', 'execution_ref', 'status', 'finished_at', 'finished_monotonic'}


def _need(value, message):
    if not value:
        raise ContractError('task budget: ' + message)


def _number(value):
    _need(type(value) in (int, float) and math.isfinite(value), 'non-finite numeric value')
    return value


def _ref(value):
    _need(isinstance(value, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', value), 'invalid artifact reference')
    return value


def _read(reader, ref, references):
    path = reader.verify_artifact(_ref(ref)); references[ref] = str(path)
    from .profile_evidence import _load
    return _load(reader, ref)


def validate_budget_plan(value):
    _need(isinstance(value, dict) and set(value) == PLAN_KEYS and type(value['schema_version']) is int
          and value['schema_version'] in (1, 2) and value['kind'] == f"task_budget_v{value['schema_version']}"
          and isinstance(value['task_id'], str) and bool(value['task_id']), 'invalid frozen budget plan')
    _ref(value['scope_ref'])
    validate_budget_values(value['budget_seconds'], value['collection_stop_policy'], soft_targets=value['schema_version'] == 2)
    return value


def validate_budget_values(budget_seconds, collection_stop_policy=None, *, soft_targets=False):
    """Shared numeric policy checks for generic and explicit legacy adapters."""
    total = _number(budget_seconds)
    _need(total > 0, 'budget must be positive')
    policy = collection_stop_policy
    if policy is not None:
        keys = {'kind', 'reserve_seconds', 'task_unit_seconds', 'pmu_unit_seconds', 'terminal_seconds'}
        _need(isinstance(policy, dict) and set(policy) == keys
              and policy['kind'] == 'finish_started_unit_v1', 'invalid collection stop policy')
        _need(all(_number(policy[key]) > 0 for key in keys - {'kind'}), 'non-positive collection allowance')
        _need(soft_targets or max(policy['task_unit_seconds'], policy['pmu_unit_seconds']) + policy['terminal_seconds']
              <= policy['reserve_seconds'] < total, 'collection reserve does not fit budget')
    return total


def _wall(value):
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
        except ValueError as error:
            raise ContractError('task budget: invalid execution timestamp') from error
    return _number(value)


def replay_task_budget(reader, binding, *, task_id):
    """Return the verified original/current windows; no Teacher or matrix schema.

    All prior terminals form one ordered prefix. Each cost covers its original
    supervisor launch through terminal completion, including failed segments.
    """
    _need(isinstance(binding, dict) and set(binding) == {'kind', 'launch_ref'}
          and binding['kind'] == 'task', 'invalid generic budget binding')
    references, active, memo = {}, set(), {}

    def launch(ref):
        if ref in memo:
            return memo[ref]
        _need(ref not in active, 'cyclic budget history')
        active.add(ref)
        value = _read(reader, ref, references)
        _need(isinstance(value, dict) and set(value) == LAUNCH_KEYS and type(value['schema_version']) is int
              and value['schema_version'] in (1, 2) and value['kind'] == f"task_launch_v{value['schema_version']}"
              and value['task_id'] == task_id, 'launch identity/schema differs')
        plan = validate_budget_plan(_read(reader, value['budget_ref'], references))
        _need(plan['task_id'] == task_id, 'budget belongs to another task')
        _read(reader, plan['scope_ref'], references)
        prior = value['prior_terminal_refs']
        _need(isinstance(prior, list) and len(prior) == len(set(prior)), 'duplicate prior terminal')
        spent, previous_finish, previous_launches = 0.0, None, []
        for index, terminal_ref in enumerate(prior):
            old = terminal(terminal_ref)
            _need(old['budget_ref'] == value['budget_ref'] and old['prior_terminal_refs'] == prior[:index]
                  and old['launch_ref'] not in previous_launches, 'prior terminal is not the exact budget prefix')
            spent += old['segment_seconds']; previous_finish = old['finished_at']
            previous_launches.append(old['launch_ref'])
        soft = plan['schema_version'] == 2
        if soft and prior:
            spent = value['started_monotonic'] - launch(previous_launches[0])['started_monotonic']
        remaining = plan['budget_seconds'] - spent
        wall, start, issued, deadline, child = (_number(value[k]) for k in
            ('started_at', 'started_monotonic', 'issued_monotonic', 'deadline_monotonic', 'child_timeout_seconds'))
        job = _read(reader, value['job_ref'], references)
        _need(start <= issued and deadline == start + remaining
              and child == deadline - issued
              and (soft or remaining > 0 and issued < deadline and child > 0
                   and _number(job['timeout_seconds']) == remaining)
              and (previous_finish is None or wall >= previous_finish), 'launch renewed or overspent frozen budget')
        result = {**value, 'budget_seconds': plan['budget_seconds'], 'scope_ref': plan['scope_ref'],
            'collection_stop_policy': plan['collection_stop_policy'], 'remaining_budget_seconds': remaining,
            'soft_targets': soft, 'spent_seconds': spent, 'wall_deadline': wall + remaining, 'references': references,
            'prior_launch_refs': previous_launches, 'job': job}
        memo[ref] = result; active.remove(ref)
        return result

    def terminal(ref):
        value = _read(reader, ref, references)
        return _check_terminal(reader, value, launch(value['launch_ref']), references)

    return launch(binding['launch_ref'])


def _execution_job(parent, launch_ref):
    """Only these deterministic supervisor fields may differ from the frozen job."""
    from pathlib import Path
    job = parent['job']
    environment = dict(job.get('environment', {}))
    if parent.get('soft_targets'):
        environment['APROF_EXECUTION_POLICY'] = 'soft_targets_local_v1'
    environment.update(APROF_TASK_LAUNCH_REF=launch_ref,
        APROF_TASK_DEADLINE_MONOTONIC=str(parent['deadline_monotonic']),
        APROF_TASK_LOCAL_INDEX=str(Path(job['output_dir']) / 'launch-index.json'))
    return dict(job, timeout_seconds=parent['child_timeout_seconds'],
        deadline_monotonic=parent['deadline_monotonic'], environment=environment)


def _check_terminal(reader, value, parent, references):
    _need(isinstance(value, dict) and set(value) == TERMINAL_KEYS
          and type(value['schema_version']) is int and value['schema_version'] in (1, 2)
          and value['kind'] == f"task_terminal_v{value['schema_version']}" and value['status'] in ('passed', 'failed'),
          'invalid task terminal')
    execution = _read(reader, value['execution_ref'], references)
    start, end = (_wall(execution[k]) for k in ('started_at', 'finished_at'))
    mono, wall = _number(value['finished_monotonic']), _number(value['finished_at'])
    cost = mono - parent['started_monotonic']
    passed = value['status'] == 'passed'
    _need(execution['kind'] == 'aprof_execution_report' and execution['schema_version'] == '1.0.0'
          and execution['job'] == _execution_job(parent, value['launch_ref'])
          and execution['status'] in (('passed',) if passed else ('failed', 'timeout'))
          and (not passed or execution['exit_code'] == 0 and not execution.get('error'))
          and parent['started_at'] <= start <= end <= wall
          and parent['issued_monotonic'] <= mono
          and (parent.get('soft_targets') or not passed or wall <= parent['wall_deadline'] and mono <= parent['deadline_monotonic'])
          and 0 <= _number(execution['duration_seconds']) <= cost and cost > 0,
          'terminal result, cost or deadline differs')
    expected_indices = parent['job'].get('evidence_indices', [])
    if expected_indices:
        rows = execution.get('evidence_indices')
        _need(isinstance(rows, list) and [row.get('path') for row in rows] == expected_indices,
              'child evidence index handoff differs from frozen job')
        for row in rows:
            _need(row.get('status') in ('merged', 'missing', 'invalid')
                  and (not passed or row['status'] == 'merged'), 'passed task omitted child evidence')
            if row['status'] == 'merged':
                index = _read(reader, row['index_ref'], references)
                _need(isinstance(index, dict) and set(index) == {'schema_version', 'kind', 'directory', 'artifacts'}
                      and index['schema_version'] == 1 and index['kind'] == 'local_evidence_index'
                      and isinstance(index['artifacts'], dict), 'child evidence index schema differs')
                for ref in index['artifacts']:
                    _ref(ref)
                # Bulk raw bytes are checked by their stage replay/archive. The
                # immutable index binds their complete roster without rehashing
                # every large profile on each inherited-budget check.
    for key in ('stdout', 'stderr'):
        pointer = execution[key]
        _need(isinstance(pointer, dict) and set(pointer) == {'path', 'sha256'}, 'execution log pointer differs')
        path = reader.verify_artifact(_ref(pointer['sha256']))
        references[pointer['sha256']] = str(path)
    return {**value, 'budget_ref': parent['budget_ref'], 'prior_terminal_refs': parent['prior_terminal_refs'],
            'segment_seconds': cost, 'cumulative_seconds': parent['spent_seconds'] + cost,
            'execution': execution, 'budget': parent}


def replay_task_terminal(reader, terminal_ref, *, task_id, budget_ref):
    """Failures can finish late: retain their actual exit and charge all time."""
    references = {}; value = _read(reader, terminal_ref, references)
    parent = replay_task_budget(reader, {'kind': 'task', 'launch_ref': value['launch_ref']}, task_id=task_id)
    _need(parent['budget_ref'] == budget_ref, 'terminal changed frozen budget')
    return _check_terminal(reader, value, parent, references)


def prepare_budget_plan(*, task_id, scope_ref, budget_seconds, collection_stop_policy=None):
    return validate_budget_plan(dict(schema_version=2, kind='task_budget_v2', task_id=task_id,
        scope_ref=scope_ref, budget_seconds=budget_seconds, collection_stop_policy=collection_stop_policy))


def remaining_task_budget(reader, *, budget_ref, prior_terminal_refs=()):
    references = {}; plan = validate_budget_plan(_read(reader, budget_ref, references))
    _read(reader, plan['scope_ref'], references)
    prior = list(prior_terminal_refs)
    _need(all(isinstance(ref, str) for ref in prior) and len(prior) == len(set(prior)), 'duplicate prior terminal')
    spent, previous_finish, launches = 0.0, None, []
    for index, ref in enumerate(prior):
        old = replay_task_terminal(reader, ref, task_id=plan['task_id'], budget_ref=budget_ref)
        _need(old['prior_terminal_refs'] == prior[:index] and old['launch_ref'] not in launches,
              'prior terminal is not the exact budget prefix')
        launches.append(old['launch_ref']); spent = old['cumulative_seconds']; previous_finish = old['finished_at']
    return dict(plan=plan, spent_seconds=spent, remaining_budget_seconds=plan['budget_seconds'] - spent,
                previous_finished_at=previous_finish, prior_launch_refs=launches)


def prepare_task_launch(reader, *, budget_ref, job_ref, prior_terminal_refs=(),
                        started_at, started_monotonic, issued_monotonic):
    state = remaining_task_budget(reader, budget_ref=budget_ref, prior_terminal_refs=prior_terminal_refs)
    remaining = state['remaining_budget_seconds']; job = _read(reader, job_ref, {})
    start, issued, wall = map(_number, (started_monotonic, issued_monotonic, started_at))
    soft = state['plan']['schema_version'] == 2
    if soft and prior_terminal_refs:
        first = replay_task_budget(reader, {'kind': 'task', 'launch_ref': state['prior_launch_refs'][0]}, task_id=state['plan']['task_id'])
        remaining = state['plan']['budget_seconds'] - (start-first['started_monotonic'])
    deadline = start + remaining
    _need(_number(job['timeout_seconds']) > 0 and start <= issued and (soft or remaining > 0 and issued < deadline and _number(job['timeout_seconds']) == remaining)
          and (state['previous_finished_at'] is None or wall >= state['previous_finished_at']),
          'launch renewed or exhausted frozen budget')
    return dict(schema_version=2 if soft else 1, kind='task_launch_v2' if soft else 'task_launch_v1', budget_ref=budget_ref,
        task_id=state['plan']['task_id'], job_ref=job_ref, prior_terminal_refs=list(prior_terminal_refs),
        started_at=wall, started_monotonic=start, issued_monotonic=issued,
        deadline_monotonic=deadline, child_timeout_seconds=deadline-issued)


def run_task(local, *, budget_ref, job_ref, destination, prior_terminal_refs=()):
    """Run one frozen argv under its remaining budget, with local evidence only.

    This is a process supervisor, not a stage scheduler. The child receives its
    verified launch/index/deadline in APROF_TASK_*; no SDK shell or inherited
    environment is added. A caller freezes required environment in the job.
    """
    import os
    from pathlib import Path
    import signal
    import socket
    import subprocess
    import time
    wall, mono = time.time(), time.monotonic()
    job = _read(local, job_ref, {})
    from .local_archive import verify_package_identity
    _need('package_identity_ref' in job, 'frozen job package identity is missing')
    verify_package_identity(local, job['package_identity_ref'])
    path = Path(destination).absolute()
    _need(path.resolve() == path and str(path) == job['output_dir']
          and Path(job['cwd']).is_dir() and Path(job['cwd']).resolve() == Path(job['cwd'])
          and isinstance(job['argv'], list) and job['argv'] and all(isinstance(x, str) and x for x in job['argv'])
          and isinstance(job.get('environment', {}), dict)
          and all(isinstance(k, str) and isinstance(v, str) for k, v in job.get('environment', {}).items()),
          'invalid frozen process job')
    indices = job.get('evidence_indices', [])
    scope = _read(local, validate_budget_plan(_read(local, budget_ref, {}))['scope_ref'], {})
    _need(isinstance(indices, list) and all(isinstance(index, str) for index in indices)
          and len(indices) == len(set(indices))
          and all(Path(index).is_absolute() and str(Path(index)) == index and Path(index).resolve() == Path(index)
                  and Path(index).is_relative_to(local.directory.parent) for index in indices)
          and (scope.get('kind') != 'task_stage_plan_v1' or bool(indices)),
          'stage task must freeze its child evidence indices inside the workspace')
    from .execution_policy import local_path
    if validate_budget_plan(_read(local, budget_ref, {}))['schema_version'] == 2:
        local_path(path); local_path(job['cwd'])
    path.mkdir(mode=0o700, exist_ok=False)  # One real attempt; never overwrite/retry.
    launch = prepare_task_launch(local, budget_ref=budget_ref, job_ref=job_ref,
        prior_terminal_refs=prior_terminal_refs, started_at=wall, started_monotonic=mono,
        issued_monotonic=time.monotonic())
    launch_ref = local.register_json(launch)
    parent = replay_task_budget(local, {'kind': 'task', 'launch_ref': launch_ref}, task_id=launch['task_id'])
    actual = _execution_job(parent, launch_ref)
    local.write_index(path / 'launch-index.json')
    process, failure, timed_out, code = None, None, False, -1
    started, began = time.time(), time.monotonic()
    stdout_path, stderr_path = path / 'stdout.log', path / 'stderr.log'
    def stop():
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
    with stdout_path.open('xb') as stdout, stderr_path.open('xb') as stderr:
        try:
            if not parent.get('soft_targets') and time.monotonic() >= launch['deadline_monotonic']:
                raise subprocess.TimeoutExpired(actual['argv'], 0)
            process = subprocess.Popen(actual['argv'], cwd=actual['cwd'], env=actual['environment'],
                stdout=stdout, stderr=stderr, start_new_session=True)
            if parent.get('soft_targets'):
                from .execution_policy import wait
                code = wait(process, target_seconds=min(job['timeout_seconds'], launch['deadline_monotonic']-time.monotonic()), checkpoint=path/'checkpoints.jsonl')
            else:
                code = process.wait(timeout=max(0, launch['deadline_monotonic'] - time.monotonic()))
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                pass
            else:
                stop()
                raise RuntimeError('task exited while child processes were still running')
            timed_out = not parent.get('soft_targets') and time.monotonic() > launch['deadline_monotonic']
        except subprocess.TimeoutExpired:
            timed_out = True; stop(); code = process.returncode if process is not None else -1
        except BaseException as error:
            failure = error; stop(); code = process.returncode if process is not None else -1
    handoff = []
    for index in indices:
        if not Path(index).exists():
            handoff.append({'path': index, 'status': 'missing'})
            if failure is None:
                failure = ValueError('declared child evidence index is missing: ' + index)
            continue
        try:
            index_ref = local.merge_index(index)
            handoff.append({'path': index, 'status': 'merged', 'index_ref': index_ref})
        except Exception as error:
            handoff.append({'path': index, 'status': 'invalid',
                'error': {'type': type(error).__name__, 'message': str(error)}})
            failure = failure or error
    finished = time.time(); elapsed = time.monotonic() - began
    execution = dict(schema_version='1.0.0', kind='aprof_execution_report', job=actual,
        host=socket.gethostname(), physical_device=None, started_at=started, finished_at=finished,
        duration_seconds=elapsed, exit_code=code,
        status='timeout' if timed_out else ('passed' if code == 0 and failure is None else 'failed'),
        stdout={'path': str(stdout_path), 'sha256': local.register_artifact(stdout_path)},
        stderr={'path': str(stderr_path), 'sha256': local.register_artifact(stderr_path)})
    if indices:
        execution['evidence_indices'] = handoff
    if failure is not None:
        execution['error'] = {'type': type(failure).__name__, 'message': str(failure)}
    if parent.get('soft_targets'):
        execution['budget_warnings'] = ['target_exceeded'] if time.monotonic() > launch['deadline_monotonic'] else []
        execution['target_seconds'] = parent['budget_seconds']
        execution['overrun_seconds'] = max(0, time.monotonic()-launch['deadline_monotonic'])
        execution['stage_target_seconds'] = job['timeout_seconds']
        execution['stage_overrun_seconds'] = max(0, elapsed-job['timeout_seconds'])
        if execution['stage_overrun_seconds'] and 'target_exceeded' not in execution['budget_warnings']:
            execution['budget_warnings'].append('stage_target_exceeded')
    execution_ref = local.register_json(execution)
    # Record terminal costs after the execution/logs have actually been closed.
    terminal = dict(schema_version=launch['schema_version'], kind=f"task_terminal_v{launch['schema_version']}", launch_ref=launch_ref,
        execution_ref=execution_ref, status='passed' if execution['status'] == 'passed' else 'failed',
        finished_at=time.time(), finished_monotonic=time.monotonic())
    if not parent.get('soft_targets') and terminal['status'] == 'passed' and (terminal['finished_at'] > parent['wall_deadline']
            or terminal['finished_monotonic'] > parent['deadline_monotonic']):
        execution.update(status='timeout'); execution_ref = local.register_json(execution)
        terminal.update(status='failed', execution_ref=execution_ref)
    terminal_ref = local.register_json(terminal)
    local.write_index(path / 'terminal-index.json')
    result = dict(terminal_ref=terminal_ref, execution_ref=execution_ref, launch_ref=launch_ref,
        status=terminal['status'], local_index=str(path / 'terminal-index.json'), archive_performed=False)
    if isinstance(failure, (KeyboardInterrupt, SystemExit)):
        raise failure
    return result
