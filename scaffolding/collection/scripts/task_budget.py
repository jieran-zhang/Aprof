"""Frozen parent budget checks; no clock renewal or process execution."""
import hashlib
import json
import math
from pathlib import Path


def positive(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError('budget must be a finite positive number')
    return value


def _generic_runtime():
    # Existing installed releases retain their exact historical helpers.
    try:
        import aprof_runtime
    except ImportError:
        return None
    if aprof_runtime.__version__ != '0.2.4':
        return None
    from aprof_runtime import task_budget as generic
    return generic


def budget_seconds(plan):
    """Historical wall-time alias is accepted only when it agrees with B."""
    values = [positive(plan[key]) for key in ('budget_seconds', 'wall_time_limit_seconds') if key in plan]
    if not values or any(value != values[0] for value in values):
        raise ValueError('missing or conflicting frozen parent budget')
    generic = _generic_runtime()
    return values[0] if generic is None else generic.validate_budget_values(values[0])


def checked_pointer(pointer):
    if not isinstance(pointer, dict) or set(pointer) != {'path', 'sha256'}:
        raise ValueError('frozen parent pointer required')
    path = Path(pointer['path'])
    if not path.is_absolute() or path.resolve() != path or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('noncanonical parent pointer')
    raw = path.read_bytes()
    if 'sha256:' + hashlib.sha256(raw).hexdigest() != pointer['sha256']:
        raise ValueError('frozen parent changed')
    return json.loads(raw)


def evaluation_budget(manifest):
    return budget_seconds(checked_pointer(manifest['plan'])['equal_budget_evaluation'])


def teacher_budget(read, anchor):
    budget = budget_seconds(anchor)
    if 'campaign_ref' in anchor:
        parent=read(anchor['campaign_ref'])
        if budget_seconds(parent) != budget or collection_policy(anchor) != collection_policy(parent):
            raise ValueError('child budget differs from frozen campaign')
    elif budget != 3600:  # Only existing historical receipts lack this parent binding.
        raise ValueError('adjustable budget requires a frozen parent campaign')
    return budget


def rule_execution_job(read, anchor, job, launch):
    """Replay the new absolute launch, or retain the original 3600 job shape."""
    budget = teacher_budget(read, anchor)
    if positive(job['timeout_seconds']) != budget:
        raise ValueError('job budget differs from parent')
    if launch is None or launch.get('schema_version') == 1:
        if budget != 3600:
            raise ValueError('adjustable rule task requires an absolute parent launch')
        return job
    keys = {'schema_version', 'anchor_ref', 'job_ref', 'started_at', 'started_monotonic',
            'monotonic_deadline', 'issued_monotonic', 'child_timeout_seconds'}
    if set(launch) != keys or launch['schema_version'] != 2:
        raise ValueError('rule launch schema differs')
    start, deadline, issued = (positive(launch[k]) for k in
        ('started_monotonic', 'monotonic_deadline', 'issued_monotonic'))
    if (read(launch['anchor_ref']) != anchor or launch['job_ref'] != anchor['job_ref']
            or not anchor['created_at'] <= positive(launch['started_at'])
            or deadline != start + budget or not start <= issued < deadline
            or positive(launch['child_timeout_seconds']) != deadline - issued):
        raise ValueError('rule launch renewed or changed its original frozen budget')
    return dict(job, timeout_seconds=launch['child_timeout_seconds'], deadline_monotonic=deadline)


def collection_policy(parent):
    policy = parent.get('collection_stop_policy')
    if policy is None:
        return None  # No new budget is inferred for a historical missing policy.
    generic = _generic_runtime()
    if generic is not None:
        generic.validate_budget_values(budget_seconds(parent), policy)
        return None if policy is None else dict(policy)
    if policy is None:
        return None  # Historical hard stop; no retroactive drain permission.
    keys = {'kind', 'reserve_seconds', 'task_unit_seconds', 'pmu_unit_seconds', 'terminal_seconds'}
    if not isinstance(policy, dict) or set(policy) != keys or policy['kind'] != 'finish_started_unit_v1':
        raise ValueError('unsupported frozen collection-stop policy')
    for key in keys - {'kind'}:
        positive(policy[key])
    if not max(policy['task_unit_seconds'], policy['pmu_unit_seconds']) + policy['terminal_seconds'] <= policy['reserve_seconds'] < budget_seconds(parent):
        raise ValueError('drain reserve does not cover the frozen complete-unit bound and terminal write')
    return dict(policy)


class CollectionBoundaryStop(TimeoutError):
    """No new collection was started; existing completed units remain evidence."""


def collection_unit_deadline(deadline, policy, kind, *, now=None):
    import time
    now = time.monotonic() if now is None else now
    if policy is None:
        if now >= deadline:
            raise TimeoutError('original task deadline expired')
        return deadline
    bound = policy[kind + '_unit_seconds']
    if now >= deadline - policy['reserve_seconds'] or deadline - now < bound + policy['terminal_seconds']:
        raise CollectionBoundaryStop('collection cutoff reached; finish prior units, start no new unit')
    return min(deadline - policy['terminal_seconds'], now + bound)


def _generic_parent(local, kind, parent_ref, scope_ref):
    from aprof_runtime.profile_evidence import _load
    from aprof_runtime.stage_recovery import validate_stage_plan
    if kind not in ('teacher', 'baseline', 'validation'):
        raise ValueError('unknown parent budget adapter')
    parent = _load(local, parent_ref)
    policy_parent = parent['equal_budget_evaluation'] if kind == 'validation' else parent
    scope = validate_stage_plan(_load(local, scope_ref))
    if not any(stage['inputs'].get('parent_budget') == parent_ref for stage in scope['stages']):
        raise ValueError('generic stage scope does not freeze its original parent')
    return scope, budget_seconds(policy_parent), collection_policy(policy_parent)


def freeze_generic_task_budget(local, *, kind, parent_ref, task_id, scope_ref):
    """Opt-in new task; never translate a historical dispatcher/exit in place."""
    generic = _generic_runtime()
    if generic is None:
        raise ValueError('generic task budgets require the explicitly selected candidate runtime')
    scope, total, policy = _generic_parent(local, kind, parent_ref, scope_ref)
    if scope['task_id'] != task_id:
        raise ValueError('parent adapter task scope differs')
    return local.register_json(generic.prepare_budget_plan(task_id=task_id, scope_ref=scope_ref,
        budget_seconds=total, collection_stop_policy=policy))


def replay_generic_task_budget(local, binding, *, kind, parent_ref, task_id):
    generic = _generic_runtime()
    if generic is None:
        raise ValueError('generic task budgets require the explicitly selected candidate runtime')
    value = generic.replay_task_budget(local, binding, task_id=task_id)
    _, total, policy = _generic_parent(local, kind, parent_ref, value['scope_ref'])
    if value['budget_seconds'] != total or value['collection_stop_policy'] != policy:
        raise ValueError('generic task changed its frozen comparison budget or drain policy')
    return value
