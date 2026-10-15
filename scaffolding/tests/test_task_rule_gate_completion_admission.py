"""Tiny CPU evidence for a third, gate-only task; no hardware qualification."""
import copy

import pytest

import task_rule_gate_completion_admission as gate
from test_task_rule_continuation_final_admission import continued, proposed


@pytest.fixture
def completed(continued, monkeypatch):
    def make(defect=None, retained_defect=None):
        f = continued(retained_defect)
        put, read = f.put, lambda ref: gate.read(f.local, ref)
        old_plan, pmu = copy.deepcopy(f.plan), copy.deepcopy(f.child)
        # This is the actual original collector schema, not the newer test-only
        # environment/timeout schema used by the previous orchestration fixture.
        for role in ('baseline', 'candidate'):
            record = read(f.oracle_refs[role][0])
            del record['environment']; del record['timeout_seconds']
            if defect == 'invented_oracle_field' and role == 'candidate': record['environment'] = {}
            ref = put(record)
            if role == 'baseline':
                old_plan['baseline_oracle_ref'] = ref
                index = read(f.trials['exp']['index_ref'])
                index['artifacts'][ref] = str(f.local.verify_artifact(ref))
                f.trials['exp']['index_ref'] = put(index)
            else: pmu['candidate_oracle_ref'] = ref
        old_plan_ref = put(old_plan)
        original_request = copy.deepcopy(f.request)
        original_request['evidence'][0]['artifacts']['continuation_plan'] = old_plan_ref
        monkeypatch.setattr(gate, 'MISSING_REQUEST', gate.content_hash(original_request))
        old_launch = dict(f.launch, plan_ref=old_plan_ref)
        old_execution = dict(f.execution_record, status='failed', exit_code=2)
        if defect == 'parent_execution_passed': old_execution.update(status='passed', exit_code=0)
        pmu.update(status='failed', error={'type': 'ValueError', 'message':
                   'continuation evidence not found: '+gate.MISSING_REQUEST}, plan_ref=old_plan_ref)
        if defect == 'different_pmu_failure': pmu['error']['message'] = 'unrelated failure'
        for key in ('gate_finished_at', 'exploration_request_ref', 'exploration_outcome_ref', 'trace_ref', 'formal_outcome'):
            pmu.pop(key, None)
        pmu_terminal = dict(f.terminal, status='failed', child_result_ref=put(pmu), plan_ref=old_plan_ref,
                            launch_ref=put(old_launch), execution_ref=put(old_execution))
        if defect == 'parent_terminal_passed': pmu_terminal['status'] = 'passed'
        pmu_ref = put(pmu_terminal)
        root = f.root.parent/'gate-only'
        runner = f.repo/'scaffolding/collection/scripts/task_rule_gate_completion.py'
        plan = dict(schema_version=1, kind='exp_gate_completion_v1', directory=str(root), created_at=1150,
            pmu_continuation_ref=pmu_ref, pmu_plan_ref=old_plan_ref, campaign_ref=f.campaign_ref,
            amendment_ref=f.amendment_ref, prefix_replay_ref=old_plan['prefix_replay_ref'],
            trusted_review_refs=f.trusted, original_parent_seconds=100, pmu_execution_seconds=100,
            total_budget_seconds=5400, additional_budget_seconds=5200,
            actual_new_builds=0, new_formal_timing_pairs=0, actual_new_captures=0,
            frozen_candidate_ref=old_plan['frozen_candidate_ref'], source_hashes=old_plan['source_hashes'],
            binary_ref=old_plan['binary_ref'], frozen_files={str(runner): f.local.register_artifact(runner)})
        if defect == 'pmu_cost_is_duration': plan['pmu_execution_seconds'] = 99
        if defect == 'renewed_gate_budget': plan['additional_budget_seconds'] = 5300
        if defect == 'different_pmu_plan': plan['pmu_plan_ref'] = f.plan_ref
        if defect == 'different_source': plan['source_hashes'] = dict(f.sources, candidate=f.stdout_ref)
        plan_ref = put(plan)
        launch = dict(schema_version=1, plan_ref=plan_ref, started_at=1200,
                      started_monotonic=400, deadline_monotonic=5600)
        if defect == 'renewed_gate_deadline': launch['deadline_monotonic'] += 1
        job = dict(f.job, argv=['python', str(runner), '--plan', str(root/'plan.json')],
                   output_dir=str(root/'job'), timeout_seconds=5200, deadline_monotonic=5600)
        execution = dict(f.execution_record, job=job, started_at=f.timestamp(1201),
                         finished_at=f.timestamp(1250), duration_seconds=49)
        if defect == 'gate_exit_failed': execution.update(status='failed', exit_code=2)
        child = dict(f.child, kind='exp_gate_completion_result_v1', plan_ref=plan_ref,
            pmu_continuation_ref=pmu_ref, actual_new_captures=0, started_at=1202,
            gate_started_at=1203, gate_finished_at=1248, finished_at=1249, duration_seconds=47,
            cumulative_online_seconds=250, candidate_oracle_ref=pmu['candidate_oracle_ref'])
        child.pop('profile_finished_at')
        if defect == 'recaptured': child['actual_new_captures'] = 1
        if defect == 'new_build': child['actual_new_builds'] = 1
        if defect == 'new_pairs': child['new_formal_timing_pairs'] = 1
        if defect == 'underreported_cost': child['cumulative_online_seconds'] = 246
        if defect == 'new_manifest': child['candidate_manifest_ref'] = f.manifests['baseline']
        if defect == 'new_oracle': child['candidate_oracle_ref'] = old_plan['baseline_oracle_ref']
        if defect == 'wrong_gate_window': child['gate_started_at'] = 1201
        request = read(child['exploration_request_ref'])
        request['evidence'][0]['artifacts']['continuation_plan'] = plan_ref
        if defect == 'old_gate_plan_binding': request['evidence'][0]['artifacts']['continuation_plan'] = old_plan_ref
        child['exploration_request_ref'] = put(request)
        outcome = dict(read(child['exploration_outcome_ref']), request_hash=child['exploration_request_ref'])
        child['exploration_outcome_ref'] = put(outcome)
        trace = read(child['trace_ref']); trace['result']['exploration_outcome_ref'] = child['exploration_outcome_ref']
        child['trace_ref'] = put(trace)
        terminal = dict(f.terminal, kind='exp_gate_completion_dispatcher_v1', plan_ref=plan_ref,
            child_result_ref=put(child), execution_ref=put(execution), launch_ref=put(launch), job_ref=put(job),
            finished_at=1251)
        terminal_ref = put(terminal)
        def replay():
            return gate.verify_gate_continuation(f.local, terminal_ref, campaign_ref=f.campaign_ref,
                trials=f.trials, amendment_ref=f.amendment_ref, trusted_review_refs=f.trusted)
        return f, replay
    return make


def test_gate_only_preserves_both_failures_and_actual_full_pmu_window(completed):
    f, replay = completed(); result = replay()
    assert result['valid'] and result['eligible_for_rule'] and not result['eligible_for_publication']
    assert result['parent_status'] == result['pmu_parent_status'] == 'failed'
    assert result['pmu_execution_seconds'] == 100  # Includes the one second before process start.
    assert result['gate_execution_seconds'] == 49 and result['cumulative_online_seconds'] == 250
    assert [x[0] for x in f.calls].count('prefix') == 1
    assert [x[0] for x in f.calls].count('profile') == 1
    assert [x[0] for x in f.calls].count('gate') == 1
    assert next(x for x in f.calls if x[0] == 'profile')[2]['window'] == [10, 1080]


@pytest.mark.parametrize('defect', ['invented_oracle_field', 'parent_execution_passed',
    'different_pmu_failure', 'parent_terminal_passed', 'pmu_cost_is_duration', 'renewed_gate_budget',
    'different_pmu_plan', 'different_source', 'renewed_gate_deadline', 'gate_exit_failed', 'recaptured',
    'new_build', 'new_pairs', 'underreported_cost', 'new_manifest', 'new_oracle', 'wrong_gate_window',
    'old_gate_plan_binding'])
def test_gate_only_rejects_mutated_parent_budget_sample_or_gate(completed, defect):
    _, replay = completed(defect)
    with pytest.raises(ValueError): replay()


@pytest.mark.parametrize('defect', ['candidate_capture_window', 'candidate_oracle_stdout',
    'candidate_output_short', 'plan_source', 'plan_binary', 'profile_leaf_reject', 'gate_leaf_reject'])
def test_retained_leaf_failures_still_reject(completed, defect):
    _, replay = completed(retained_defect=defect)
    with pytest.raises(ValueError): replay()


def test_promotion_uses_new_full_replay_and_real_skill_source_checks(proposed, monkeypatch):
    f = proposed()
    monkeypatch.setattr(gate, 'verify_gate_continuation', f.continuation_leaf)
    result = gate.verify_continuation_promotion(f.local, f.promotion_ref, campaign_ref=f.campaign_ref,
        trials=f.trials, amendment_ref=f.amendment_ref, trusted_before_inventory_ref=f.before_ref,
        repo=f.repo, release=f.release, trusted_review_refs=f.trusted)
    assert result['valid'] and result['operator'] == 'exp' and result['eligible_for_teacher_edit']
    assert [x[0] for x in f.calls] == ['continuation', 'skills', 'sources']
