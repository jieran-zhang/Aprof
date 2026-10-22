"""CPU FakeRunner evidence exercises HAP's version dispatch, never NPU qualification."""
from copy import deepcopy
from datetime import datetime, timedelta

import pytest

import hap_report
from aprof_runtime import unified_timing as timing
from test_median_timing import new_campaign
from test_unified_timing import campaign


@pytest.mark.parametrize('version,values,valid,reason', [
    (1, [96., 104.] * 10, True, None),
    (1, [92., 108.] * 10, False, 'within_process_cv_over_limit'),
    (2, [92., 108.] * 10, True, None),
    (2, [88., 112.] * 10, False, 'within_process_cv_over_limit'),
    (2, [80.] * 16 + [140.] * 4, True, None),
    (2, [80.] * 15 + [140.] * 5, False, 'outlier_limit_exceeded'),
])
def test_actual_replay_uses_its_declared_policy(tmp_path, version, values, valid, reason):
    kwargs = {'samples': {'candidate': values}}
    if version == 2:
        new_campaign(tmp_path, **kwargs)
    else:
        campaign(tmp_path, stability_policy='bounded_outlier_v1', **kwargs)
    path = tmp_path / 'candidate/case_1/capture.json'
    replay = timing.replay_capture(path)
    row = hap_report.normalize_replay(replay, path)
    assert row['timing_valid'] is valid
    assert row['stability_policy'] == f'bounded_outlier_v{version}'
    assert row['max_within_process_cv'] == (.10 if version == 2 else .05)
    assert row['raw_values_us'] == values
    if reason:
        assert reason in row['validation_reasons']
    else:
        assert row['validation_reasons'] == []


def test_policy_mismatch_and_age_still_reject(tmp_path):
    new_campaign(tmp_path)
    path = tmp_path / 'candidate/case_1/capture.json'
    replay = timing.replay_capture(path)
    altered = deepcopy(replay)
    altered['sample_statistics']['policy'] = 'bounded_outlier_v1'
    assert 'missing_current_stability_policy' in hap_report.normalize_replay(altered, path)['validation_reasons']
    declaration = timing.declaration(path.parent, replay['capture']['artifacts']['declaration'])
    expired = datetime.fromisoformat(replay['captured_at'].replace('Z', '+00:00')) + timedelta(
        seconds=declaration['reuse_policy']['max_age_seconds'] + 1)
    assert 'outside_declared_capture_age' in hap_report.normalize_replay(
        replay, path, evaluated_at=expired.isoformat())['validation_reasons']


def test_formula_boundary_and_complete_coverage_remain_required():
    assert hap_report.hap_values(107, 100, 113)['threshold_met'] is True
    assert hap_report.hap_values(107, 100, 113.00001)['threshold_met'] is False
    anchor = {'level': {'op': {str(i): {'baseline_perf_us': 107, 't_hw_us': 100}
                               for i in range(1, 21)}}}
    row = {'case_id': 1, 'operator': 'op', 'correctness_valid': True,
           'correctness_status': 'verified', 'timing_valid': True, 'observed_median_us': 100}
    report = hap_report.score_rows(anchor, 'op', [row])
    assert report['valid_case_count'] == report['qualified_case_count'] == 1
    assert not report['complete_20_valid_cases'] and not report['operator_hap_qualified']
    assert report['missing_case_ids'] == list(range(2, 21))
