"""CPU 实测链替身和统计反例；不启动 NPU、真实 oracle 或重测。"""
import json
from pathlib import Path

import jsonschema
import pytest

from aprof_runtime.errors import ContractError
from aprof_runtime.median_timing import (STABILITY_POLICY, STABILITY_PROTOCOL, compare_windows,
                                         sample_statistics, validate_schema, window_stability)
from aprof_runtime.unified_timing import evaluate_request, file_hash, finalize_timing, verify_timing
from test_unified_capture import FakeRunner
from test_unified_timing import campaign, ref, write
from single_role_task import collect

PACKAGE = Path(__file__).resolve().parents[2]


def new_campaign(root, *, max_retests=1, **kwargs):
    request_path, config = campaign(root, declaration_overrides={
        'schema_version': 3, 'stability_protocol': STABILITY_PROTOCOL, 'stability_policy': STABILITY_POLICY,
        'replication_policy': {'max_retests': max_retests, 'estimator': 'last_executed_window'}}, **kwargs)
    req = json.loads(request_path.read_text())
    req.update(schema_version=2, stability_protocol=STABILITY_PROTOCOL,
               replications={'baseline': [], 'candidate': []})
    write(request_path, req)
    return request_path, config


def replicate(request_path, config, role, duration, suffix='retest'):
    req = json.loads(request_path.read_text()); root = request_path.parent
    Path(config['source_files'][0]).write_text('kernel.cpp' if role == 'baseline' else 'candidate source')
    Path(config['binary']).write_text('binary' if role == 'baseline' else 'candidate binary')
    correctness = root / req[role + '_correctness']['path']
    config['correctness'] = {'path': str(correctness), 'sha256': file_hash(correctness)}
    out = root / (role + '_' + suffix)
    collect(config, out, runner=FakeRunner(config, duration=duration))
    req['replications'][role].append(ref(root, out / 'case_1/capture.json'))
    write(request_path, req)


def compare(a, b):
    return compare_windows([{'case_id': 1, 'baseline': a, 'candidate': b}])


def test_four_symmetric_spikes_are_bounded_and_all_raw_values_remain():
    values = [100.] * 16 + [40., 50., 180., 200.]
    stats = sample_statistics(values)
    assert stats['raw_values_us'] == values and stats['raw_cv'] > .1
    assert stats['outlier_count'] == 4 and stats['retained_count'] == 16
    assert stats['excluded_indices'] == [17, 18, 19, 20]
    assert stats['median_us'] == stats['raw_median_us'] == 100 and stats['cv'] == 0
    assert stats['quality_status'] == 'within_window_acceptable'


def test_five_spikes_are_not_partially_or_iteratively_removed():
    stats = sample_statistics([100.] * 15 + [150., 180., 200., 220., 250.])
    assert stats['outlier_count'] == 5 and stats['excluded_indices'] == []
    assert stats['retained_count'] == 20 and stats['exclusion_limit_exceeded']
    assert stats['quality_status'] == 'variable_review_required'


def test_mad_zero_boundary_and_broad_variation_are_distinct():
    stats = sample_statistics([100.] * 18 + [90., 110.])
    assert stats['outlier_threshold_us'] == 10 and stats['outlier_count'] == 0
    moderate = sample_statistics([93., 107.] * 10)
    broad = sample_statistics([80., 120.] * 10)
    assert moderate['quality_status'] == 'within_window_acceptable' and moderate['outlier_count'] == 0
    assert broad['quality_status'] == 'variable_review_required' and broad['outlier_count'] == 0


@pytest.mark.parametrize('values', [[1.] * 19, [1.] * 21, [1.] * 19 + [0],
                                    [1.] * 19 + [True], [1.] * 19 + [float('nan')]])
def test_malformed_samples_remain_invalid(values):
    with pytest.raises(ContractError):
        sample_statistics(values)


@pytest.mark.parametrize('value,status', [(102., 'stable_evidence'), (103., 'stable_evidence'),
                                         (104., 'caution'), (105., 'caution'), (106., 'uncertain')])
def test_raw_median_drift_trial_boundaries(value, status):
    assert window_stability([{'raw_median_us': 100}, {'raw_median_us': value}])['status'] == status


def test_known_median_stable_spikes_and_real_drift_are_not_conflated():
    good = compare([[100.] * 20] * 2, [[24.592] * 17 + [40, 80, 100], [25.042] * 17 + [40, 80, 100]])
    assert good['verdict'] == 'accepted'
    assert good['cases'][0]['candidate']['median_stability']['max_drift_fraction'] == pytest.approx(.018298633702017033)
    bad = compare([[100.] * 20] * 2, [[28.488] * 20, [35.150] * 20])
    assert bad['verdict'] == 'inconclusive' and bad['timing_quality'] == 'uncertain'


def test_stable_median_does_not_auto_admit_high_variability():
    values = [64., 96.] * 10
    report = compare([[100.] * 20] * 2, [values, values])
    assert report['engineering_assessment']['verdict'] == 'accepted'
    assert report['cases'][0]['candidate']['further_benefit_review_possible']
    assert report['verdict'] == 'inconclusive' and report['timing_quality'] == 'review_required'


def test_exclusion_crossing_engineering_threshold_is_not_silently_admitted():
    values = [95. + .25 * i for i in range(16)] + [150.] * 4
    report = compare([[100.] * 20], [values])
    assert report['engineering_assessment']['verdict'] == 'accepted'
    assert report['raw_engineering_assessment']['verdict'] == 'rejected'
    assert report['exclusion_changes_conclusion'] and report['verdict'] == 'inconclusive'


def test_all_windows_and_each_side_matter_not_just_last_or_ratio():
    report = compare([[100.] * 20] * 3, [[80.] * 20, [120.] * 20, [80.] * 20])
    assert report['engineering_assessment']['speedup'] == 1.25 and report['verdict'] == 'inconclusive'
    common = compare([[100.] * 20, [120.] * 20], [[80.] * 20, [96.] * 20])
    assert common['engineering_assessment']['speedup'] == 1.25 and common['verdict'] == 'inconclusive'
    worsening = compare([[100.] * 20] * 2, [[80.] * 20, [104.] * 20])
    assert worsening['engineering_assessment']['verdict'] == 'rejected'
    assert worsening['engineering_assessment']['speedup'] == pytest.approx(100 / 104)


def test_real_regression_still_rejected_and_small_gain_not_promoted():
    assert compare([[100.] * 20], [[110.] * 20])['verdict'] == 'rejected'
    assert compare([[100.] * 20], [[98.] * 20])['engineering_assessment']['verdict'] == 'rejected'


def test_new_end_to_end_schema_and_immutable_replay(tmp_path):
    request, config = new_campaign(tmp_path, samples={'candidate': [80.] * 16 + [140.] * 4})
    out = tmp_path / 'result.json'; result = finalize_timing(request, out)
    assert result['verdict'] == 'accepted' and result['schema_version'] == 2
    assert not result['replication_recommended']
    assert result['cases'][0]['candidate']['windows'][0]['retained_count'] == 16
    assert verify_timing(out)['valid']
    validate_schema(PACKAGE, 'request', json.loads(request.read_text()))
    validate_schema(PACKAGE, 'result', result)
    jsonschema.validate(json.loads(Path(config['declaration']['path']).read_text()),
                        json.loads((PACKAGE / 'schemas/unified-timing-declaration-v3.schema.json').read_text()))
    result['cases'][0]['candidate']['windows'][0]['raw_values_us'][0] = 1
    write(out, result)
    with pytest.raises(ContractError, match='原始证据'):
        verify_timing(out)


def test_retest_is_bound_budgeted_and_cannot_replace_first(tmp_path):
    request, config = new_campaign(tmp_path)
    replicate(request, config, 'candidate', 80.5)
    result = evaluate_request(request)
    assert result['verdict'] == 'accepted'
    assert result['cases'][0]['candidate']['median_stability']['status'] == 'stable_evidence'
    assert len(result['cases'][0]['candidate']['windows']) == 2
    replicate(request, config, 'candidate', 80, suffix='excess')
    with pytest.raises(ContractError, match='复验次数'):
        evaluate_request(request)


def test_duplicate_capture_cannot_create_stability_evidence(tmp_path):
    request, _ = new_campaign(tmp_path)
    req = json.loads(request.read_text()); req['replications']['candidate'] = req['candidate_captures']; write(request, req)
    with pytest.raises(ContractError, match='独立采集|重复窗口'):
        evaluate_request(request)


def test_protocol_mixing_and_undeclared_upgrades_are_refused(tmp_path):
    request, _ = new_campaign(tmp_path)
    req = json.loads(request.read_text()); req.pop('replications'); req.pop('stability_protocol');req['schema_version'] = 1;write(request, req)
    with pytest.raises(ContractError, match='不能混用旧判定'):
        evaluate_request(request)


def test_quality_review_never_creates_extra_retry_budget(tmp_path):
    request, _ = new_campaign(tmp_path, max_retests=0, samples={'candidate': [80.] * 15 + [140.] * 5})
    result = evaluate_request(request)
    assert result['timing_quality'] == 'review_required' and result['verdict'] == 'inconclusive'
    assert not result['replication_recommended']
