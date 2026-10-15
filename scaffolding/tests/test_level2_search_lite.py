"""Search budget/lineage and CLI policy stay distinct from frozen final evidence."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scaffolding/collection/scripts'))
import level2_iteration as iteration
import msprof_exploration_campaign as campaign
import run_msprof_exploration_stage as stage
from msprof_search_protocol import LITE_PROTOCOL, LITE_PRODUCER
from test_manifest_campaign import declaration
from test_msprof_exploration_campaign import h, register, ready, start, finish, observe


def test_lite_search_parent_identity_budget_and_full_final_are_separate(tmp_path):
    ledger = campaign.create_fresh(tmp_path / 'ledger', campaign_id='lite', workloads={'maximum': declaration()})
    register(ledger, 'maximum001', workload='maximum')
    ready(ledger, 'maximum001', workload='maximum')
    observe(ledger, 'first', ['maximum001-build', 'maximum001-correctness', 'maximum001-runtime'],
            cid='maximum001', workload='maximum')
    parent = {'candidate_id': 'maximum001', 'source_hash': h(200)}
    register(ledger, 'maximum002', source=201, parent=parent, basis=['first'], workload='maximum')
    ready(ledger, 'maximum002', workload='maximum')
    plan = ledger.timing_plan('maximum', 'maximum002', purpose='search', manifest_ref=h(3), search_lite=True)
    assert plan['protocol'] == LITE_PROTOCOL and plan['producer_protocol'] == LITE_PRODUCER
    assert plan['comparisons'] == [{'control_source_hash': h(200), 'candidate_source_hash': h(201), 'roles': ['child_vs_parent']}]
    assert campaign.expected_samples(plan) == 4 * 2 * 2 * 6 * 2
    assert campaign.expected_complete_calls(plan) == 31 * 2 * 2 * 6 * 2
    start(ledger, 'lite-search', 'timing', plan, cid='maximum002', workload='maximum')
    assert ledger.state['tasks']['maximum']['used']['timing_groups'] == 1
    assert ledger.state['tasks']['maximum']['reserved_final_candidate_ids'] == ['maximum002']
    assert ledger.verify()['valid']
    with pytest.raises(ValueError, match='only for fresh Level2 search'):
        ledger.timing_plan('maximum', 'maximum002', purpose='final', manifest_ref=h(4), search_lite=True)
    full = ledger.timing_plan('maximum', 'maximum002', purpose='final', manifest_ref=h(4))
    assert full['processes'] == 6 and full['pairs_per_case'] == 30 and len(full['comparisons']) == 2
    assert len(full['case_ids']) == 20


@pytest.mark.parametrize('fault', ['processes', 'pairs_per_case', 'comparisons', 'repeat_by_case'])
def test_lite_plan_cannot_relax_frozen_scope_or_repeats(tmp_path, fault):
    ledger = campaign.create_fresh(tmp_path / 'ledger', campaign_id='lite', workloads={'maximum': declaration()})
    register(ledger, 'maximum001', workload='maximum'); ready(ledger, 'maximum001', workload='maximum')
    plan = ledger.timing_plan('maximum', 'maximum001', purpose='search', manifest_ref=h(3), search_lite=True)
    if fault == 'repeat_by_case': plan[fault]['20'] = 10
    elif fault == 'comparisons': plan[fault] = []
    else: plan[fault] = 1
    with pytest.raises(ValueError, match='frozen'):
        start(ledger, 'bad', 'timing', plan, cid='maximum001', workload='maximum')
    assert ledger.state['tasks']['maximum']['used']['timing_groups'] == 0


def test_new_cli_uses_lite_without_parent_calibration(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(iteration, 'candidate', lambda *a, **kw: calls.append(kw) or {'status': 'measured'})
    monkeypatch.setattr(sys, 'argv', ['level2_iteration.py', 'candidate', '--run', str(tmp_path),
        '--operator', 'gcd', '--candidate', 'gcd001'])
    assert iteration.main() == 0
    assert calls == [{'measurement': {'search_lite': True}, 'deduplicate_outputs': False}]


def test_baseline_lite_checks_all_correctness_but_only_search_control_cases(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(iteration, 'stage', lambda *a, **kw: calls.append((a[3], kw)) or {'status': 'passed'})
    result = iteration.baseline(tmp_path, 'gcd', control_group='aa-lite', measurement={'search_lite': True})
    assert result['status'] == 'baseline_validated_and_self_checked'
    assert calls[0][1]['cases'] == list(range(1, 21))
    assert calls[2][1] == {'cases': [1, 8, 14, 20], 'search_lite': True}


def test_lite_never_relabels_full_aa_and_never_automatically_chases_noise():
    with pytest.raises(ValueError, match='relabel'):
        stage.measurement_options({'search_lite': True, 'calibration_path': '/tmp/full-aa.json'})
    report = {'case_ids': ['1'], 'results': [
        {'case_id': '1', 'buffer_config': config, 'process_ratios': [1.018, .988], 'cv_status': 'within_limit'}
        for config in ['normal', 'swapped']]}
    result = iteration.search_decision(report)
    assert result['near_flat_or_uncertain_cases'] == ['1']
    assert result['default_parent'] == 'retain_direct_parent' and result['automatic_remeasure'] is False
    report['results'][0]['process_ratios'] = [1.15, 1.16]
    report['results'][1]['process_ratios'] = [1.14, 1.15]
    assert iteration.search_decision(report)['clear_gain_cases'] == ['1']
