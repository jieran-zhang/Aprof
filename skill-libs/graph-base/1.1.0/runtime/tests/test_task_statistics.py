import json
from pathlib import Path

import jsonschema
import pytest

from aprof_runtime.errors import ContractError
from aprof_runtime.task_statistics import BOUNDED_OUTLIER_POLICY, bounded_statistics
from aprof_runtime.unified_timing import evaluate_request, finalize_timing, verify_timing
from test_unified_timing import campaign


def test_two_sided_outliers_and_raw_data_are_retained():
    values = [100.] * 18 + [50., 200.]
    result = bounded_statistics(values)
    assert result['excluded_indices'] == [19, 20]
    assert result['raw_values_us'] == values
    assert result['raw_cv'] > .05 and result['cv'] == 0
    assert result['median_us'] == 100 and result['retained_count'] == 18
    assert not result['exclusion_limit_exceeded']


def test_too_many_outliers_cannot_be_trimmed_until_pass():
    result = bounded_statistics([100.] * 17 + [150., 200., 250.])
    assert result['exclusion_limit_exceeded']
    assert result['outlier_indices'] == [18, 19, 20]
    assert result['excluded_indices'] == [] and result['retained_count'] == 20
    assert result['cv'] > .05


def test_zero_mad_uses_relative_floor_and_strict_boundary():
    result = bounded_statistics([100.] * 18 + [90., 110.])
    assert result['mad_us'] == 0 and result['outlier_threshold_us'] == 10
    assert result['excluded_indices'] == []


def test_broad_variation_is_not_classified_away():
    result = bounded_statistics([80., 120.] * 10)
    assert result['excluded_indices'] == [] and result['cv'] > .05


@pytest.mark.parametrize('values', [[1.] * 19, [1.] * 21, [1.] * 19 + [0],
                                   [1.] * 19 + [float('nan')], [1.] * 19 + [float('inf')]])
def test_requires_complete_positive_samples(values):
    with pytest.raises(ContractError):
        bounded_statistics(values)


def test_opt_in_gate_excludes_spike_and_replays_decision(tmp_path):
    request, _ = campaign(tmp_path, stability_policy=BOUNDED_OUTLIER_POLICY,
                          samples={'candidate': [80.] * 19 + [140.]})
    output = tmp_path / 'result.json'
    result = finalize_timing(request, output)
    assert result['verdict'] == 'accepted' and result['speedup'] == 1.25
    stats = result['cases'][0]['candidate_statistics']
    assert stats['excluded_indices'] == [20] and stats['raw_cv'] > .05
    assert verify_timing(output)['valid']
    schemas = Path(__file__).parents[2] / 'schemas'
    jsonschema.validate(result, json.loads((schemas / 'unified-timing-result.schema.json').read_text()))
    result['cases'][0]['candidate_statistics']['excluded_indices'] = []
    output.write_text(json.dumps(result))
    with pytest.raises(ContractError, match='原始证据'):
        verify_timing(output)


def test_legacy_declaration_keeps_original_no_exclusion_gate(tmp_path):
    request, _ = campaign(tmp_path, samples={'candidate': [80.] * 19 + [140.]})
    result = evaluate_request(request)
    assert result['verdict'] == 'inconclusive'
    assert 'stability_policy' not in result and 'candidate_statistics' not in result['cases'][0]


def test_persistent_regression_and_excess_outliers_still_fail(tmp_path):
    (tmp_path / 'regression').mkdir()
    (tmp_path / 'excess').mkdir()
    request, _ = campaign(tmp_path / 'regression', candidate_us=104,
                          stability_policy=BOUNDED_OUTLIER_POLICY,
                          samples={'candidate': [104.] * 19 + [170.]})
    assert evaluate_request(request)['verdict'] == 'rejected'
    request, _ = campaign(tmp_path / 'excess', stability_policy=BOUNDED_OUTLIER_POLICY,
                          samples={'candidate': [80.] * 17 + [140., 150., 160.]})
    result = evaluate_request(request)
    assert result['verdict'] == 'inconclusive'
    assert any('2/20' in reason for reason in result['reasons'])


def test_unknown_policy_fails_before_native_execution(tmp_path):
    with pytest.raises(ContractError, match='stability_policy'):
        campaign(tmp_path, stability_policy='drop_whatever_is_slow')
    assert not (tmp_path / 'baseline_correctness/case_1').exists()
