"""Explicit scope changes use real CPU exits; no model, compiler or hardware."""
import json
from pathlib import Path
import sys
import time

import pytest

import task_rule_campaign as campaign
import task_rule_trial as trial
from aprof_runtime.errors import StoreError
from aprof_runtime.local_evidence import LocalEvidence
from timing_admission import read
from test_task_rule_campaign import CHILD, SCRIPTS, save


def amendment(created_at):
    return dict(schema_version=1, kind='teacher_exp_only_scope_amendment',
        authorization='user_requested_exp_only_release_on_success', release_id='graph-base/1.0.0',
        target=dict(device='910C', architecture='A3', cann_version='9.0.0'), operators=['exp'],
        validation_45='not_run', postseal_full_tests='not_run', other_rules='draft', created_at=created_at)


@pytest.fixture
def scope(tmp_path):
    local = LocalEvidence(tmp_path/'records')
    path = save(tmp_path/'scope.json', amendment(time.time()))
    pointer = dict(path=str(path), sha256=local.register_artifact(path))
    attempt = dict(operator='exp', run_id='CPU-exp', candidate_id='CPU-exp-candidate', source_hashes={})
    value = dict(scope_amendment_ref=pointer, created_at=time.time(), attempts=[attempt])
    return local, path, value


def test_registered_exp_scope_and_legacy_roster(scope):
    reader, _, value = scope
    assert campaign.registered_operators(value, reader) == ('exp',)
    value.pop('scope_amendment_ref')
    with pytest.raises(ValueError, match='authorized operator'):
        campaign.registered_operators(value, reader)
    value['attempts'].append(dict(operator='sigmoid', run_id='CPU-sigmoid',
        candidate_id='CPU-sigmoid-candidate', source_hashes={}))
    assert campaign.registered_operators(value, reader) == ('exp', 'sigmoid')


@pytest.mark.parametrize('field,value', [
    ('authorization', 'implicit'), ('release_id', 'graph-base/0.5.1'),
    ('target', dict(device='950', architecture='A5', cann_version='9.0.0')),
    ('operators', ['exp', 'sigmoid']), ('validation_45', 'passed'),
    ('postseal_full_tests', 'passed'), ('other_rules', 'stable'),
    ('created_at', 1e30), ('extra', True),
])
def test_rehashed_amendment_cannot_change_authorized_scope(scope, field, value):
    reader, path, schedule = scope
    changed = json.loads(path.read_text()); changed[field] = value
    save(path, changed)
    schedule['scope_amendment_ref']['sha256'] = reader.register_artifact(path)
    with pytest.raises(ValueError, match='scope amendment'):
        campaign.registered_operators(schedule, reader)


def test_changed_amendment_bytes_reject(scope):
    reader, path, value = scope
    path.write_text('{}')
    with pytest.raises((ValueError, StoreError)):
        campaign.registered_operators(value, reader)


@pytest.mark.parametrize('operators', [[], ['sigmoid'], ['exp', 'sigmoid'], ['exp', 'exp']])
def test_omission_extra_operator_and_retry_reject(scope, operators):
    reader, _, value = scope
    value['attempts'] = [dict(operator=op, run_id='CPU-'+str(i), candidate_id='candidate-'+str(i),
        source_hashes={}) for i, op in enumerate(operators)]
    with pytest.raises(ValueError, match='authorized operator'):
        campaign.registered_operators(value, reader)


@pytest.fixture
def exp_trial(tmp_path, monkeypatch, request):
    """One actual prebuild CPU rejection under the existing dispatcher and clock."""
    root = tmp_path/'campaign'; root.mkdir(); top = LocalEvidence(root/'records')
    child = root/'task_rule_controller.py'; child.write_text('SCRIPTS='+repr(str(SCRIPTS))+'\n'+CHILD)
    monkeypatch.setattr(trial, 'CONTROLLER', child)
    monkeypatch.setattr(trial, 'producer_paths', lambda: [child])
    sources = {role: top.register_json({'CPU_fixture': role}) for role in ('baseline', 'candidate')}
    attempt = dict(operator='exp', run_id='CPU-exp', candidate_id='CPU-exp-candidate', source_hashes=sources)
    freeze = save(root/'freeze.json', dict(schema_version=1, operator='exp', source_hashes=sources))
    scope = save(root/'scope.json', amendment(time.time()))
    scope_pointer = dict(path=str(scope), sha256=top.register_artifact(scope))
    value = dict(schema_version=1, kind='teacher_task_rule_campaign', protocol=campaign.PROTOCOL,
        task_protocol=campaign.TASK_PROTOCOL, runtime_build='aprof-runtime/0.2.3', model=campaign.MODEL,
        budget_seconds=3600, budget_policy='time_only_v1', reviewer_token_limit=None,
        max_attempts_per_operator=1, stop_on_failure=True, resampling='none', created_at=time.time(),
        attempts=[attempt], source_freezes=[dict(path=str(freeze), sha256=top.register_artifact(freeze))],
        trace_index_sha256=sources['baseline'], split_index_sha256=sources['candidate'],
        prior_campaign_refs=[], scope_amendment_ref=scope_pointer)
    path = save(root/'campaign.json', value); reference = top.register_artifact(path)
    d = root/'exp'; d.mkdir(); local = LocalEvidence(d/'records')
    for ref in top._paths: local.register_artifact(top.verify_artifact(ref))
    qual = save(root/'qualification.json', dict(model='gpt-6-sol', reasoning_effort='max',
        budget_policy='time_only_v1', review_submission_protocol='final_json_review_v1'))
    frozen_files = {str(path): reference, str(child): local.register_artifact(child)}
    if getattr(request, 'param', None) != 'omit_frozen_scope':
        frozen_files[str(scope)] = scope_pointer['sha256']
    frozen = local.register_json(frozen_files)
    plan = dict(directory=str(d), release=str(trial.bridge.RELEASE), model=campaign.MODEL,
        launch_path=str(d/'dispatcher-launch.json'), physical_device=0, frozen_files_ref=frozen,
        worker_qualification=dict(path=str(qual), sha256=local.register_artifact(qual)), CPU_mode='prebuild')
    plan_ref = local.register_artifact(save(d/'controller-plan.json', plan))
    job = dict(job_id=attempt['run_id'], argv=[str(Path(sys.executable).resolve()), str(child),
        '--anchor', str(d/'anchor.json'), '--local-index', str(d/'prepared-local-index.json')],
        cwd=str(root), output_dir=str(d/'job'), timeout_seconds=3600,
        environment=dict(APROF_SKILL_LIB=str(trial.bridge.RELEASE), PYTHONDONTWRITEBYTECODE='1',
            ASCEND_RT_VISIBLE_DEVICES='0', APROF_PHYSICAL_DEVICE='0', APROF_LOGICAL_DEVICE='0'))
    job_ref = local.register_artifact(save(d/'job.json', job)); stub = local.register_json({'CPU_fixture': True})
    anchor = dict(schema_version=1, protocol=campaign.PROTOCOL, task_protocol=campaign.TASK_PROTOCOL,
        purpose='promotion', **attempt, campaign_ref=reference, controller_plan_ref=plan_ref, job_ref=job_ref,
        budget_seconds=3600, created_at=time.time(), input_inventory_ref=stub, boundary_plan_ref=stub,
        screen_plan_ref=stub, profile_plan_ref=stub, source_review_ref=stub, history_refs=[])
    anchor_ref = local.register_artifact(save(d/'anchor.json', anchor))
    local.write_index(d/'prepared-local-index.json')
    save(d/'prepared.json', dict(anchor_ref=anchor_ref, local_index=trial.pointer(d/'prepared-local-index.json')))
    result = trial.run(d, expected_anchor=anchor_ref)
    reader = LocalEvidence.from_index(d/'dispatcher-local-index.json')
    trials = dict(exp=dict(reader=reader, index_ref=top.register_artifact(d/'dispatcher-local-index.json'),
        dispatcher_result_ref=reader.register_artifact(d/'dispatcher-result.json')))
    return top, reference, trials, result, scope_pointer


def test_exp_only_replays_actual_failed_exit_without_admission(exp_trial):
    reader, reference, trials, _, _ = exp_trial
    result = campaign.replay_task_rule_campaign(reader, reference, trials=trials)
    assert result['valid'] and result['complete'] and not result['all_components_valid']
    assert not result['admission_authority'] and not result['eligible_for_publication']
    assert [(x['operator'], x['status'], x['exit_code']) for x in result['trials']] == [('exp', 'failed', 2)]


@pytest.mark.parametrize('exp_trial', ['omit_frozen_scope'], indirect=True)
def test_exp_scope_must_be_frozen_before_the_actual_attempt(exp_trial):
    reader, reference, trials, _, _ = exp_trial
    with pytest.raises(ValueError, match='scope amendment was not frozen'):
        campaign.replay_task_rule_campaign(reader, reference, trials=trials)


@pytest.mark.parametrize('defect', ['missing_trial', 'extra_sigmoid', 'retry', 'missing_index_scope'])
def test_exp_campaign_requires_exact_trial_and_index_scope(exp_trial, defect):
    reader, reference, trials, _, scope = exp_trial
    if defect == 'missing_trial': trials.clear()
    elif defect == 'extra_sigmoid': trials['sigmoid'] = trials['exp']
    elif defect == 'retry': trials['retry'] = trials['exp']
    else:
        index = read(reader, trials['exp']['index_ref']); index['artifacts'].pop(scope['sha256'])
        trials['exp']['index_ref'] = reader.register_json(index)
    with pytest.raises(ValueError, match='omitted|unregistered'):
        campaign.replay_task_rule_campaign(reader, reference, trials=trials)
