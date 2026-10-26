"""Plan reuse of whole, independently replayed stages; never splice samples.

The verifier callback is trusted application code, not JSON supplied by a model.
Without a callback this module can enumerate pending work, but cannot authorize
reuse. It never executes a stage, changes a terminal, or grants admission.
"""
from .task_budget import _need, _read, _ref, _number, _wall, validate_budget_plan, replay_task_terminal


PLAN_KEYS = {'schema_version', 'kind', 'task_id', 'stages'}
STAGE_KEYS = {'id', 'dependencies', 'inputs', 'recovery_policy', 'max_attempts'}
RECEIPT_KEYS = {'schema_version', 'kind', 'plan_ref', 'stage_id', 'launch_ref', 'status',
                'failure_class', 'input_refs', 'dependency_refs', 'artifact_refs', 'output_refs', 'started_at', 'finished_at'}


def _inputs(value, *, symbolic=True):
    _need(isinstance(value, dict) and all(isinstance(k, str) and k for k in value), 'invalid stage input map')
    for ref in value.values():
        if isinstance(ref, dict) and symbolic:
            _need(set(ref) == {'stage_id', 'output'} and all(isinstance(x, str) and x for x in ref.values()),
                  'invalid dependency output reference')
        else:
            _ref(ref)
    return value


def validate_stage_plan(value):
    _need(isinstance(value, dict) and set(value) == PLAN_KEYS and value['schema_version'] == 1
          and type(value['schema_version']) is int and value['kind'] == 'task_stage_plan_v1'
          and isinstance(value['task_id'], str) and value['task_id']
          and isinstance(value['stages'], list) and value['stages'], 'invalid stage plan')
    seen = set()
    for stage in value['stages']:
        _need(isinstance(stage, dict) and set(stage) == STAGE_KEYS
              and isinstance(stage['id'], str) and stage['id'] and stage['id'] not in seen
              and isinstance(stage['dependencies'], list)
              and all(isinstance(x, str) for x in stage['dependencies'])
              and len(stage['dependencies']) == len(set(stage['dependencies']))
              and set(stage['dependencies']) <= seen
              and stage['recovery_policy'] in ('complete_only', 'repeat_safe')
              and type(stage['max_attempts']) is int and stage['max_attempts'] > 0,
              'invalid stage identity, dependency order or attempt bound')
        _inputs(stage['inputs'])
        _need(all(not isinstance(ref, dict) or ref['stage_id'] in stage['dependencies']
                  for ref in stage['inputs'].values()), 'input output is not a declared dependency')
        seen.add(stage['id'])
    return value


def plan_stage_recovery(reader, plan_ref, *, budget_ref, terminal_refs, receipt_refs,
                        current_inputs, verify_stage=None):
    """Select missing stages under one frozen task budget and dependency graph.

    A trusted verifier must compute ``valid/status/failure_class`` from each
    stage's raw evidence. It receives ``terminal_refs`` as keyword context and
    must also prove ``not_started`` before any missing stage is ready after an
    earlier process exit. ``passed`` in a receipt alone never authorizes reuse.
    Failed controls/semantics and partial complete-only stages are blocked.
    """
    refs = {}; plan = validate_stage_plan(_read(reader, plan_ref, refs))
    budget = validate_budget_plan(_read(reader, budget_ref, refs))
    _need(budget['scope_ref'] == plan_ref and budget['task_id'] == plan['task_id'], 'stage plan changed frozen budget scope')
    stages = {s['id']: s for s in plan['stages']}
    _need(isinstance(current_inputs, dict) and set(current_inputs) == set(stages), 'current stage input scope differs')
    invalidated = set()
    for name, stage in stages.items():
        _inputs(current_inputs[name])
        for ref in list(stage['inputs'].values()) + list(current_inputs[name].values()):
            if isinstance(ref, str):
                reader.verify_artifact(ref)
        if current_inputs[name] != stage['inputs'] or set(stage['dependencies']) & invalidated:
            invalidated.add(name)
    terminals, prior, spent = {}, [], 0.0
    for ref in terminal_refs:
        terminal = replay_task_terminal(reader, ref, task_id=plan['task_id'], budget_ref=budget_ref)
        _need(terminal['prior_terminal_refs'] == prior and terminal['launch_ref'] not in terminals,
              'recovery terminal history is not one exact prefix')
        prior.append(ref); terminals[terminal['launch_ref']] = terminal; spent += terminal['segment_seconds']
    _need(isinstance(receipt_refs, (list, tuple)) and len(receipt_refs) == len(set(receipt_refs)),
          'duplicate stage receipt')
    attempts = {name: [] for name in stages}
    receipts = {}
    for ref in receipt_refs:
        row = _read(reader, ref, refs)
        _need(isinstance(row, dict) and set(row) == RECEIPT_KEYS and row['schema_version'] == 1
              and type(row['schema_version']) is int and row['kind'] == 'task_stage_receipt_v1'
              and row['plan_ref'] == plan_ref and row['stage_id'] in stages
              and row['launch_ref'] in terminals and row['status'] in ('passed', 'failed', 'interrupted')
              and row['failure_class'] in (None, 'infrastructure', 'control', 'semantic')
              and ((row['failure_class'] is None) == (row['status'] == 'passed')),
              'stage receipt identity or terminal differs')
        stage = stages[row['stage_id']]; terminal = terminals[row['launch_ref']]
        _need(isinstance(row['dependency_refs'], dict)
              and set(row['dependency_refs']) == set(stage['dependencies']), 'stage input/dependency scope differs')
        start, finish = _number(row['started_at']), _number(row['finished_at'])
        _need(_wall(terminal['execution']['started_at']) <= start <= finish <= _wall(terminal['execution']['finished_at'])
              and (terminal['budget'].get('soft_targets') or row['status'] != 'passed' or finish <= terminal['budget']['wall_deadline']),
              'stage is outside its actual process/deadline window')
        for name, dependency_ref in row['dependency_refs'].items():
            dependency = receipts.get(dependency_ref)
            _need(dependency is not None and dependency['stage_id'] == name and dependency['status'] == 'passed'
                  and dependency['finished_at'] <= start, 'stage dependency was not completed before use')
        expected_inputs = {}
        for name, item in stage['inputs'].items():
            if isinstance(item, dict):
                dependency = receipts[row['dependency_refs'][item['stage_id']]]
                _need(item['output'] in dependency['output_refs'], 'dependency output is missing')
                item = dependency['output_refs'][item['output']]
            expected_inputs[name] = item
        _need(_inputs(row['input_refs'], symbolic=False) == expected_inputs, 'stage resolved input differs')
        _inputs(row['output_refs'], symbolic=False)
        _need(isinstance(row['artifact_refs'], list) and row['artifact_refs']
              and len(row['artifact_refs']) == len(set(row['artifact_refs']))
              and set(row['output_refs'].values()) <= set(row['artifact_refs']), 'missing/duplicate complete stage artifacts')
        for artifact in row['artifact_refs']:
            reader.verify_artifact(_ref(artifact))
        old = attempts[row['stage_id']]
        _need(len(old) < stage['max_attempts'] and not any(x[1]['status'] == 'passed' for x in old),
              'stage repeated after success or exceeded frozen attempts')
        if old:
            _need(stage['recovery_policy'] == 'repeat_safe'
                  and all(x[1]['failure_class'] == 'infrastructure' for x in old)
                  and old[-1][1]['finished_at'] <= start,
                  'failed control/partial measurement cannot be retried')
        verdict = None if verify_stage is None else verify_stage(reader, stage, row, terminal_refs=list(terminal_refs))
        if verdict is not None:
            _need(isinstance(verdict, dict) and verdict.get('valid') is True
                  and verdict.get('status') == row['status'] and verdict.get('failure_class') == row['failure_class'],
                  'trusted stage replay did not confirm the receipt')
        old.append((ref, row, verdict)); receipts[ref] = row
    reused, remaining, ready, blocked = {}, [], [], {}
    for name, stage in stages.items():
        rows = attempts[name]
        if name in invalidated:
            blocked[name] = 'frozen inputs or upstream inputs changed; a new plan is required'
        elif any(dep in blocked for dep in stage['dependencies']):
            blocked[name] = 'upstream stage is blocked'
        elif rows and rows[-1][2] is None:
            blocked[name] = 'trusted stage replay is required'
        elif rows and rows[-1][1]['status'] == 'passed':
            last_ref, last, _ = rows[-1]
            if all(last['dependency_refs'][dep] == reused.get(dep) for dep in stage['dependencies']):
                reused[name] = last_ref
            else:
                blocked[name] = 'dependency receipt was not independently reusable'
        elif rows and (stage['recovery_policy'] == 'complete_only'
                       or rows[-1][1]['failure_class'] != 'infrastructure'
                       or len(rows) >= stage['max_attempts']):
            blocked[name] = 'partial/failed stage cannot be resumed or resampled'
        else:
            remaining.append(name)
            unstarted = not terminals or bool(rows)
            if not rows and terminals and verify_stage is not None:
                verdict = verify_stage(reader, stage, None, terminal_refs=list(terminal_refs))
                unstarted = (isinstance(verdict, dict) and verdict.get('valid') is True
                    and verdict.get('status') == 'not_started' and verdict.get('failure_class') is None)
            if not unstarted:
                blocked[name] = 'missing receipt does not prove the stage was never started'
            elif all(dep in reused for dep in stage['dependencies']):
                ready.append(name)
    remaining_budget = budget['budget_seconds'] - spent
    if remaining_budget <= 0:
        blocked.update({name: 'frozen task budget exhausted' for name in remaining}); ready = []
    return dict(schema_version=1, kind='task_stage_recovery_plan_v1', task_id=plan['task_id'],
        plan_ref=plan_ref, budget_ref=budget_ref, terminal_refs=list(terminal_refs),
        reused_stages=reused, remaining_stages=remaining, ready_stages=ready,
        invalidated_stages=[name for name in stages if name in invalidated], blocked_stages=blocked,
        spent_seconds=spent, remaining_budget_seconds=remaining_budget,
        admission_authority=False, execution_performed=False, archive_performed=False)


def default_stage_plan(*, task_id, source_ref, input_ref, toolchain_ref, protocol_ref):
    """Seven complete stages; binary is a verified build output, never pre-invented.

    The caller freezes the actual source/input/toolchain/protocol inventories.
    Its trusted build verifier must expose output_refs['binary']; later verifiers
    must check every resolved input, including that binary. This is only a plan.
    """
    base = dict(sources=source_ref, input=input_ref, toolchain=toolchain_ref, protocol=protocol_ref)
    _inputs(base, symbolic=False)
    names = ('prepare_review', 'build', 'correctness_boundary', 'exploratory_timing',
             'formal_timing_control', 'pmu', 'online_admission')
    stages = []
    for index, name in enumerate(names):
        dependencies = list(names[:index])
        inputs = dict(base)
        if index >= 2:
            inputs['binary'] = {'stage_id':'build', 'output':'binary'}
        stages.append(dict(id=name, dependencies=dependencies, inputs=inputs,
            recovery_policy='repeat_safe' if name == 'online_admission' else 'complete_only',
            max_attempts=2 if name == 'online_admission' else 1))
    return validate_stage_plan(dict(schema_version=1, kind='task_stage_plan_v1', task_id=task_id, stages=stages))
