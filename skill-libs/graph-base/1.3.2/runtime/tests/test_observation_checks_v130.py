"""合成观测算术回归，不生成或验证性能归因。"""
import math
from copy import deepcopy

import pytest

from aprof_runtime.jsonio import content_hash
from aprof_runtime.observation_checks import validate_and_derive


def sample():
    counters = []
    for layer, read, write in [('logical_gm', 2147483648, 1073741824),
                               ('hbm', 1073741824, 1073741824)]:
        for kind, value in [('read_bytes', read), ('write_bytes', write)]:
            counters.append(dict(id=layer + '.' + kind, kind=kind, value=value,
                                 unit='B', layer=layer, window_ref='/window'))
    for kind, value in [('read_calls', 32768), ('write_calls', 16384)]:
        counters.append(dict(id='logical_gm.' + kind, kind=kind, value=value,
                             unit='calls', layer='logical_gm', window_ref='/window'))
    return dict(evidence_status='synthetic_assumed_hardware_data',
                scope={'implementation': 'paper.cpp', 'workload': 'paper',
                       'objects': ['tensor.x'], 'stage': 'kernel.main'},
                window={'start': 0, 'end': 2800, 'unit': 'us'},
                durations=[dict(id=key, value=value, unit='us', window_ref='/window')
                           for key, value in [('mte_active', 2750), ('issue_wait', 40),
                                              ('steady_transfer', 2710)]],
                duration_partitions=[dict(parent_id='mte_active',
                                          member_ids=['issue_wait', 'steady_transfer'], complete=True)],
                throughput_duration_id='mte_active', counters=counters,
                references=[dict(layer='hbm', value=800, unit='GB/s',
                                 bytes_basis=['read_bytes', 'write_bytes'], duration_id='mte_active')])


def test_l_successor_has_separate_layer_budgets_and_exact_dependencies():
    raw = sample()
    before = deepcopy(raw)
    result = validate_and_derive(raw)
    assert raw == before
    assert result['status'] == 'valid'
    assert result['derived']['hbm.bandwidth']['value'] == pytest.approx(780.9031447272727)
    assert result['derived']['logical_gm.bandwidth']['value'] == pytest.approx(1171.354717090909)
    assert result['derived']['logical_gm.read_mean_payload']['value'] == 65536
    assert result['derived']['hbm.reference_ratio']['value'] == pytest.approx(0.9761289309090909)
    quantity = result['derived']['hbm.bandwidth']
    assert quantity['evidence_status'] == 'synthetic_assumed_hardware_data'
    assert quantity['independent_support'] is False
    assert quantity['input_sha256'] == content_hash(raw)
    assert quantity['dependency_hash'] == content_hash(quantity['dependencies'])
    assert {d['pointer'] for d in quantity['dependencies']} == {
        '/counters/2', '/counters/3', '/durations/0', '/window', '/throughput_duration_id'}


def test_old_l_impossible_counter_is_rejected_without_promoting_partial_derivations():
    raw = sample()
    raw['durations'][2]['value'] = 4060
    result = validate_and_derive(raw)
    assert result['status'] == 'invalid'
    assert any('观测窗口' in e['reason'] for e in result['errors'])
    assert any('互斥时间成员' in e['reason'] for e in result['errors'])
    assert all(x['usable_as_evidence'] is False for x in result['derived'].values())


def test_stale_copied_bandwidth_and_dependency_hash_are_rejected():
    raw = sample()
    actual = validate_and_derive(raw)['derived']['hbm.bandwidth']
    raw['derived_claims'] = [dict(quantity_id='hbm.bandwidth', value=785.66578634,
                                  unit='GB/s', layer='hbm', dependency_hash=actual['dependency_hash'])]
    assert validate_and_derive(raw)['status'] == 'invalid'
    raw['derived_claims'][0]['value'] = actual['value']
    assert validate_and_derive(raw)['status'] == 'valid'
    raw['durations'][0]['value'] = 2740
    raw['durations'][2]['value'] = 2700
    result = validate_and_derive(raw)
    assert any('hash' in error['reason'] for error in result['errors'])


@pytest.mark.parametrize('bad', [True, False, float('inf'), float('nan'), -1, 0.5])
def test_counter_rejects_bool_nonfinite_negative_or_fractional_count(bad):
    raw = sample()
    raw['counters'][0]['value'] = bad
    assert validate_and_derive(raw)['status'] == 'invalid'


@pytest.mark.parametrize('mutate', [
    lambda r: r['window'].update(end=0),
    lambda r: r['window'].update(end=-1),
    lambda r: r['window'].update(unit='ticks'),
    lambda r: r['durations'][0].update(value=0),
    lambda r: r['counters'][0].update(unit='bits'),
    lambda r: r['counters'][0].update(window_ref='/other-window'),
    lambda r: r['counters'][4].update(value=0),
    lambda r: r['duration_partitions'][0].update(member_ids=['issue_wait', 'issue_wait']),
])
def test_bad_time_units_scope_and_zero_denominator_are_invalid(mutate):
    raw = sample()
    mutate(raw)
    assert validate_and_derive(raw)['status'] == 'invalid'


def test_missing_data_remains_unknown_and_cannot_substitute_hbm_for_logical_bytes():
    raw = sample()
    raw['counters'] = [x for x in raw['counters'] if x['id'] != 'hbm.write_bytes']
    result = validate_and_derive(raw)
    assert result['status'] == 'unknown'
    assert 'hbm.bandwidth' not in result['derived']
    assert 'logical_gm.bandwidth' in result['derived']
    assert not result['errors']
    raw.pop('window')
    assert 'logical_gm.bandwidth' not in validate_and_derive(raw)['derived']


@pytest.mark.parametrize('location', ['value', 'unit', 'window_ref', 'layer'])
def test_missing_counter_measurement_or_interpretation_stays_unknown(location):
    raw = sample()
    raw['counters'][2][location] = None
    result = validate_and_derive(raw)
    assert result['status'] == 'unknown'
    assert 'hbm.bandwidth' not in result['derived']
    assert not result['errors']


def test_explicit_mixed_layer_aggregate_and_claim_are_rejected():
    raw = sample()
    raw['aggregates'] = [{'counter_ids': ['hbm.read_bytes', 'logical_gm.write_bytes']}]
    result = validate_and_derive(raw)
    assert result['status'] == 'invalid'
    assert any('混合' in x['reason'] for x in result['errors'])
    raw.pop('aggregates')
    actual = validate_and_derive(raw)['derived']['hbm.bandwidth']
    raw['derived_claims'] = [dict(quantity_id='hbm.bandwidth', value=actual['value'],
                                  unit='GB/s', layer='logical_gm', dependency_hash=actual['dependency_hash'])]
    assert validate_and_derive(raw)['status'] == 'invalid'


def test_byte_time_and_reference_units_convert_without_changing_meaning():
    raw = sample()
    raw['counters'][2].update(value=1024, unit='MiB')
    raw['window'].update(end=2.8, unit='ms')
    raw['durations'][0].update(value=2.75, unit='ms')
    raw['references'][0].update(value=800_000_000_000, unit='B/s')
    result = validate_and_derive(raw)
    assert result['status'] == 'valid'
    assert result['derived']['hbm.bandwidth']['value'] == pytest.approx(780.9031447272727)


def test_each_raw_field_change_revises_dependency_identity_not_original_input():
    raw = sample()
    original = validate_and_derive(raw)
    successor = deepcopy(raw)
    successor['counters'][2]['value'] += 1
    revised = validate_and_derive(successor)
    assert revised['derived']['hbm.bandwidth']['dependency_hash'] != original['derived']['hbm.bandwidth']['dependency_hash']
    assert revised['derived']['logical_gm.bandwidth']['dependency_hash'] == original['derived']['logical_gm.bandwidth']['dependency_hash']
    assert revised['input_sha256'] != original['input_sha256']


@pytest.mark.parametrize('mutate', [
    lambda r: r.update(counters={}),
    lambda r: r.update(durations=None),
    lambda r: r.update(throughput_duration_id=[]),
    lambda r: r['window'].update(unit=[]),
    lambda r: r['durations'][0].update(unit=[]),
    lambda r: r['counters'][0].update(unit=[]),
    lambda r: r['counters'][0].update(kind=[]),
    lambda r: r['counters'][0].update(kind={}),
    lambda r: r['counters'][0].update(kind=['read_bytes']),
    lambda r: r['counters'][0].update(value=10 ** 1000),
    lambda r: r['references'][0].update(layer=[]),
    lambda r: r['duration_partitions'][0].update(parent_id=[]),
    lambda r: r.update(aggregates=[{'counter_ids': ['hbm.read_bytes', 'hbm.read_bytes']}]),
])
def test_malformed_input_reports_invalid_without_crashing(mutate):
    raw = sample()
    mutate(raw)
    assert validate_and_derive(raw)['status'] == 'invalid'


@pytest.mark.parametrize('value', [10 ** 308, 1e308], ids=['integer', 'float'])
def test_counter_unit_conversion_overflow_is_invalid_before_payload_or_bandwidth(value):
    raw = sample()
    raw['counters'][0].update(value=value, unit='GiB')
    result = validate_and_derive(raw)
    assert result['status'] == 'invalid'
    assert any(e['path'] == '/counters/0/value' for e in result['errors'])
    assert 'logical_gm.read_mean_payload' not in result['derived']
    assert 'logical_gm.bandwidth' not in result['derived']
    assert all(q['usable_as_evidence'] is False for q in result['derived'].values())


@pytest.mark.parametrize('value', [10 ** 308, 1e308], ids=['integer', 'float'])
def test_byte_sum_overflow_cannot_feed_bandwidth_or_reference(value):
    raw = sample()
    for counter in raw['counters']:
        if counter['layer'] == 'hbm':
            counter['value'] = value
    result = validate_and_derive(raw)
    assert result['status'] == 'invalid'
    assert any(e['path'] == 'hbm.total_bytes' for e in result['errors'])
    assert not {'hbm.total_bytes', 'hbm.bandwidth', 'hbm.reference_ratio'} & result['derived'].keys()
    assert all(q['usable_as_evidence'] is False for q in result['derived'].values())


def test_duration_partition_sum_overflow_is_reported_at_the_partition():
    raw = sample()
    raw['window'].update(end=1.5e308, unit='s')
    for duration, value in zip(raw['durations'], [1.5e308, 1e308, 1e308]):
        duration.update(value=value, unit='s')
    result = validate_and_derive(raw)
    assert result['status'] == 'invalid'
    assert any(e['path'] == '/duration_partitions/0' and '派生运算' in e['reason']
               for e in result['errors'])
    assert all(math.isfinite(q['value']) and q['usable_as_evidence'] is False
               for q in result['derived'].values())


@pytest.mark.parametrize('target', ['window', 'duration'])
def test_positive_time_unit_underflow_is_invalid_instead_of_a_zero_denominator(target):
    raw = sample()
    raw['duration_partitions'] = []
    if target == 'window':
        raw['window'].update(end=1e-320, unit='ns')
    else:
        raw['durations'][0].update(value=1e-320, unit='ns')
    result = validate_and_derive(raw)
    assert result['status'] == 'invalid'
    assert any('下溢' in e['reason'] for e in result['errors'])
    assert 'hbm.bandwidth' not in result['derived']
    assert all(q['usable_as_evidence'] is False for q in result['derived'].values())


def test_bandwidth_intermediate_overflow_is_rejected_even_if_gb_scaling_would_fit():
    raw = sample()
    raw['window'].update(end=1e-300, unit='s')
    raw['durations'] = [dict(id='active', value=1e-300, unit='s', window_ref='/window')]
    raw['duration_partitions'] = []
    raw['throughput_duration_id'] = 'active'
    raw['references'][0]['duration_id'] = 'active'
    result = validate_and_derive(raw)
    assert result['status'] == 'invalid'
    assert any(e['path'] == 'hbm.bandwidth' for e in result['errors'])
    assert 'hbm.bandwidth' not in result['derived']
    assert 'hbm.reference_ratio' not in result['derived']
    assert all(q['usable_as_evidence'] is False for q in result['derived'].values())


@pytest.mark.parametrize('value,unit', [(1e308, 'GiB/s'), (5e-324, 'B/s')])
def test_reference_conversion_or_ratio_overflow_cannot_become_a_valid_zero(value, unit):
    raw = sample()
    raw['references'][0].update(value=value, unit=unit)
    result = validate_and_derive(raw)
    assert result['status'] == 'invalid'
    assert 'hbm.reference_ratio' not in result['derived']
    assert all(q['usable_as_evidence'] is False for q in result['derived'].values())


@pytest.mark.parametrize('value', [800, 400])
def test_duplicate_reference_identity_is_invalid_without_choosing_either_value(value):
    raw = sample()
    raw['references'].append(dict(raw['references'][0], value=value))
    result = validate_and_derive(raw)
    assert result['status'] == 'invalid'
    assert any(e['path'] == '/references/1' and '重复' in e['reason'] for e in result['errors'])
    assert 'hbm.reference_ratio' not in result['derived']
    assert all(q['usable_as_evidence'] is False for q in result['derived'].values())


def test_references_for_separate_layers_and_zero_bytes_remain_valid():
    raw = sample()
    for counter in raw['counters']:
        if counter['layer'] == 'hbm':
            counter['value'] = 0
    raw['references'].append(dict(raw['references'][0], layer='logical_gm'))
    result = validate_and_derive(raw)
    assert result['status'] == 'valid'
    assert result['derived']['hbm.reference_ratio']['value'] == 0
    assert result['derived']['logical_gm.reference_ratio']['value'] > 0


def test_large_finite_arithmetic_is_preserved_without_clipping():
    raw = sample()
    raw['window'].update(end=1, unit='s')
    raw['durations'] = [dict(id='active', value=1, unit='s', window_ref='/window')]
    raw['duration_partitions'] = []
    raw['throughput_duration_id'] = 'active'
    raw['counters'] = [c for c in raw['counters'] if c['layer'] == 'hbm']
    for counter in raw['counters']:
        counter['value'] = 10 ** 307
    raw['references'][0].update(value=10 ** 307, unit='B/s', duration_id='active')
    result = validate_and_derive(raw)
    assert result['status'] == 'valid'
    assert result['derived']['hbm.total_bytes']['value'] == 2 * 10 ** 307
    assert result['derived']['hbm.bandwidth']['value'] == pytest.approx(2e298)
    assert result['derived']['hbm.reference_ratio']['value'] == pytest.approx(2)
