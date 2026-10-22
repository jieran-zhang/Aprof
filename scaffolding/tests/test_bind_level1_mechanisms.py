from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from aprof_runtime.errors import ContractError, StoreError
from aprof_runtime.exploration import mechanism_alignment_from_artifacts
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import register_json_artifact, verify_trace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
spec = importlib.util.spec_from_file_location('mechanism_binder', ROOT / 'scaffolding/collection/scripts/bind_level1_mechanisms.py')
binder_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(binder_module)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n')


def raw_case(directory, values, *, field='aiv_scalar_time(us)', kernel='exp_kernel', extra=None):
    for invocation, value in enumerate(values):
        path = directory / 'raw' / 'OPPROF_20260907_test' / kernel / str(invocation) / f'PipeUtilization_20260907154719{invocation:03}.csv'
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = ['block_id', 'sub_block_id', field] + list(extra or {})
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fields)
            writer.writeheader()
            # Many core rows do not manufacture additional independent runs.
            for core in range(4):
                writer.writerow({'block_id': core, 'sub_block_id': 'vector0', field: value, **(extra or {})})


def campaign(tmp_path, *, baseline=(10, 10.1, 10.2, 10.1, 10), cases=(1,), metrics=None):
    run = tmp_path / 'campaign'
    dump(run / 'run-manifest.json', {'operators': ['exp'], 'validation_operators': [], 'sentinel_case_ids': [1, 8, 14, 20]})
    task = run / 'tasks/exp'
    dump(task / 'candidates/001/candidate_plan.json', {'candidate_id': 'exp-001', 'handler_id': 'exp.localize_tiling_and_split_tail'})
    with EpisodeStore(run / 'train/episodes.sqlite') as store:
        for case in cases:
            dump(task / 'prepared' / f'case_{case:02d}' / 'metadata.json', {'case_id': case, 'base': -1, 'scale': 1, 'shift': 0})
            directory = task / 'profiles/baseline' / f'case-{case:02d}'
            raw_case(directory, baseline, extra={'aiv_scalar_vector_stall_time(us)': 3} if metrics else None)
            binder_module.normalize_profile(directory / 'raw', directory / 'normalized-current', case, store)
    instance = binder_module.MechanismBinder(run)
    specification = None
    if metrics:
        specification = {'kernel': 'exp_kernel', 'metrics': metrics, 'applicability': 'all', 'rationale': 'Two independent predeclared scalar counters.'}
    frozen = instance.prepare('exp', '001', list(cases), specification)
    return run, task, instance, frozen


def test_freeze_then_bind_real_csv_replay_and_idempotence(tmp_path):
    run, task, binder, frozen = campaign(tmp_path)
    raw_case(task / 'profiles/001/case-01', [7, 7.1, 7.2, 7.1, 7])
    binding = binder.bind('exp', '001')
    assert binding['status'] == 'supported'
    assert binding['admitted_comparison_count'] == 1
    assert binding['comparisons'][0]['candidate_invocation_medians'] == [7, 7.1, 7.2, 7.1, 7]
    assert binder.bind('exp', '001') == binding
    assert binder.prepare('exp', '001', [1]) == frozen
    report = binder_module.read(task / 'candidates/001/mechanism_report.json')
    assert report['metrics'][0]['baseline'] == 10.1
    assert report['metrics'][0]['candidate'] == 7.1
    with EpisodeStore(run / 'train/episodes.sqlite') as store:
        digest = register_json_artifact(store, report)
        evidence = {'candidate_id': 'exp-001', **{key: 'not_run' for key in ('static_review', 'build', 'accuracy', 'runtime', 'semantic', 'scope', 'portability')},
            'artifacts': {'mechanism_report': digest}}
        assert mechanism_alignment_from_artifacts(evidence, store)
        assert verify_trace(task / 'trace_events.jsonl', store)['event_count'] == 1


@pytest.mark.parametrize('candidate,reason', [([9.5, 9.8, 9.9, 10.2, 10], 'spread'), ([10.05] * 5, '1%')])
def test_small_or_overlapping_changes_do_not_claim_attribution(tmp_path, candidate, reason):
    _, task, binder, _ = campaign(tmp_path)
    raw_case(task / 'profiles/001/case-01', candidate)
    result = binder.bind('exp', '001')
    assert result['status'] == 'inconclusive'
    assert reason in result['comparisons'][0]['reason']
    assert not (task / 'candidates/001/mechanism_report.json').exists()


def test_complete_predeclared_case_set_required_and_missing_can_resume(tmp_path):
    _, task, binder, _ = campaign(tmp_path, cases=(1, 8))
    raw_case(task / 'profiles/001/case-01', [7] * 5)
    first = binder.bind('exp', '001')
    assert first['status'] == 'inconclusive'
    assert len(first['comparisons']) == 2
    assert first['admitted_comparison_count'] == 0
    assert not (task / 'candidates/001/mechanism_report.json').exists()
    raw_case(task / 'profiles/001/case-08', [7] * 5)
    assert binder.bind('exp', '001')['status'] == 'supported'
    assert len(list((task / 'candidates/001/mechanism_bindings').glob('*.json'))) == 2


def test_no_favorable_counter_subset_when_second_counter_refutes(tmp_path):
    metrics = [{'name': binder_module.SCALAR, 'expected_direction': 'decrease'}, {'name': binder_module.VECTOR_STALL, 'expected_direction': 'decrease'}]
    _, task, binder, _ = campaign(tmp_path, metrics=metrics)
    raw_case(task / 'profiles/001/case-01', [7] * 5, extra={'aiv_scalar_vector_stall_time(us)': 6})
    result = binder.bind('exp', '001')
    assert [item['status'] for item in result['comparisons']] == ['supported', 'refuted']
    assert result['status'] == 'inconclusive'
    assert not (task / 'candidates/001/mechanism_report.json').exists()


def test_frozen_direction_cannot_be_rewritten_after_profile(tmp_path):
    _, task, binder, _ = campaign(tmp_path)
    raw_case(task / 'profiles/001/case-01', [20] * 5)
    path = task / 'candidates/001/mechanism_plan.json'
    altered = binder_module.read(path)
    altered['predictions'][0]['expected_direction'] = 'increase'
    dump(path, altered)
    with pytest.raises(StoreError, match='event/CAS commitment'):
        binder.bind('exp', '001')


def test_cannot_prepare_after_candidate_profiles_exist(tmp_path):
    _, task, binder, _ = campaign(tmp_path)
    (task / 'candidates/001/mechanism_plan.json').unlink()
    raw_case(task / 'profiles/001/case-01', [7] * 5)
    with pytest.raises(StoreError, match='before candidate profiling'):
        binder.prepare('exp', '001', [1])


def test_no_pseudoreplication_from_many_core_rows(tmp_path):
    _, task, binder, _ = campaign(tmp_path)
    raw_case(task / 'profiles/001/case-01', [7, 7])
    result = binder.bind('exp', '001')
    assert result['status'] == 'inconclusive'
    assert 'three recorded invocation' in result['comparisons'][0]['reason']


def test_applicability_uses_effective_exp_attributes_and_dtype():
    assert binder_module.applicable('exp_zero', {'base': 1, 'scale': 1.5, 'shift': 1})
    assert not binder_module.applicable('exp_zero', {'base': -1, 'scale': 1, 'shift': 0})
    assert binder_module.applicable('exp_identity', {'base': -1, 'scale': 1, 'shift': 0})
    assert not binder_module.applicable('exp_identity', {'base': -1, 'scale': 2, 'shift': 1})
    assert binder_module.applicable('norm_common', {'scalar': 4})
    assert not binder_module.applicable('norm_common', {'scalar': 2.5})
    assert binder_module.applicable('masked_fp32', {'x_dtype': 'float16', 'mask_dtype': 'float32'})


def test_duration_only_spec_is_rejected():
    with pytest.raises(ContractError, match='duration is not mechanism'):
        binder_module.MechanismBinder.validate_specification({'kernel': 'exp_kernel', 'applicability': 'all',
            'metrics': [{'name': 'OpBasicInfo/Task Duration(us)', 'expected_direction': 'decrease'}], 'rationale': 'Looks faster.'})


def test_new_handler_mappings_are_specific_source_predictions():
    expected = {
        'sigmoid.align_block_ownership': ('sigmoid_kernel', binder_module.BANDWIDTH, 'increase'),
        'sigmoid.double_buffer_prefetch': ('sigmoid_kernel', binder_module.INPUT_STALL, 'decrease'),
        'sigmoid.coalesce_dma_chunks': ('sigmoid_kernel', binder_module.COPIES, 'decrease'),
        'gelu_prefetch_double_buffer': ('gelu_kernel', binder_module.INPUT_STALL, 'decrease'),
        'gelu_capacity_batched_tiles': ('gelu_kernel', binder_module.COPIES, 'decrease'),
        'gelu_hoist_launch_invariants': ('gelu_kernel', binder_module.SCALAR, 'decrease'),
    }
    for handler, (kernel, metric, direction) in expected.items():
        actual = binder_module.SPECS[handler]
        assert actual[0] == kernel
        assert actual[1] == [(metric, direction)]
    assert '4096-element compute' in binder_module.SPECS['sigmoid.coalesce_dma_chunks'][3]


def test_alignment_controls_derive_from_source_geometry():
    rule = 'unaligned_core_ownership32'
    assert binder_module.applicable(rule, {'numel': 1048576, 'dtype': 'float16', '__baseline_block_dim': 48})
    assert binder_module.applicable(rule, {'numel': 10549248, 'dtype': 'float32', '__baseline_block_dim': 48}) is False
    assert binder_module.applicable(rule, {'numel': 10549248, 'dtype': 'float32'}) is None


def test_nonpositive_baseline_cannot_admit_a_direction(tmp_path):
    _, task, binder, frozen = campaign(tmp_path, baseline=[0] * 5)
    assert 'not positive' in frozen['predictions'][0]['limitation']
    raw_case(task / 'profiles/001/case-01', [-1] * 5)
    result = binder.bind('exp', '001')
    assert result['status'] == 'inconclusive'
    assert 'not positive' in result['comparisons'][0]['reason']
    assert not (task / 'candidates/001/mechanism_report.json').exists()


@pytest.mark.parametrize('values,status', [([7] * 5, 'supported'), ([20] * 5, 'refuted'),
                                          ([10.05] * 5, 'inconclusive')])
def test_every_binding_status_replays_without_writes(tmp_path, monkeypatch, values, status):
    run, task, binder, plan = campaign(tmp_path)
    raw_case(task / 'profiles/001/case-01', values)
    binding = binder.bind('exp', '001')
    assert binding['status'] == status
    before = {str(p): p.read_bytes() for p in task.rglob('*') if p.is_file()}
    def forbidden(*args, **kwargs):
        raise AssertionError('replay must not normalize, register, or write artifacts')
    monkeypatch.setattr(binder_module, 'normalize_profile', forbidden)
    monkeypatch.setattr(binder_module, 'register_json_artifact', forbidden)
    monkeypatch.setattr(binder_module, 'write', forbidden)
    with EpisodeStore(run / 'train/episodes.sqlite') as store:
        monkeypatch.setattr(store, 'register_artifact', forbidden)
        assert binder.verify_binding('exp', '001', plan, binding, store) == binding
        forged = json.loads(json.dumps(binding))
        forged['comparisons'][0]['candidate_value'] = 999
        with pytest.raises(StoreError, match='does not replay'):
            binder.verify_binding('exp', '001', plan, forged, store)
    assert before == {str(p): p.read_bytes() for p in task.rglob('*') if p.is_file()}


def test_missing_profile_binding_is_rejected_after_profiles_arrive(tmp_path):
    run, task, binder, plan = campaign(tmp_path)
    missing = binder.bind('exp', '001')
    history = {p: p.read_bytes() for p in (task / 'candidates/001/mechanism_bindings').glob('*.json')}
    raw_case(task / 'profiles/001/case-01', [20] * 5)
    with EpisodeStore(run / 'train/episodes.sqlite') as store:
        with pytest.raises(StoreError, match='fresh mechanism bind'):
            binder.verify_binding('exp', '001', plan, missing, store)
        folder = task / 'profiles/001/case-01'
        binder_module.normalize_profile(folder / 'raw', folder / 'normalized-current', 1, store)
        with pytest.raises(StoreError, match='does not replay'):
            binder.verify_binding('exp', '001', plan, missing, store)
    assert all(p.read_bytes() == data for p, data in history.items())
    assert binder_module.read(task / 'candidates/001/mechanism_binding.json') == missing


def test_replay_rejects_changed_current_raw_even_with_intact_cas(tmp_path):
    run, task, binder, plan = campaign(tmp_path)
    folder = task / 'profiles/001/case-01'
    raw_case(folder, [20] * 5)
    binding = binder.bind('exp', '001')
    raw_case(folder, [7] * 5)
    with EpisodeStore(run / 'train/episodes.sqlite') as store:
        with pytest.raises(StoreError, match='current raw profile differs'):
            binder.verify_binding('exp', '001', plan, binding, store)


def test_replay_preserves_genuinely_missing_kernel_result(tmp_path):
    run, task, binder, plan = campaign(tmp_path)
    raw_case(task / 'profiles/001/case-01', [7] * 5, kernel='other_kernel')
    binding = binder.bind('exp', '001')
    assert binding['status'] == 'inconclusive'
    with EpisodeStore(run / 'train/episodes.sqlite') as store:
        assert binder.verify_binding('exp', '001', plan, binding, store) == binding
