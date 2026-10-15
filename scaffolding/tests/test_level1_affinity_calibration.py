import copy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scaffolding/collection/scripts'))
from calibrate_level1_affinity import compare_control


def report():
    return {'stable': True, 'per_case': [
        {'case_id': case, 'baseline_samples_ns': [100.0] * 30,
         'candidate_samples_ns': [100.0] * 30, 'speedup': 1.0}
        for case in [1, 8, 14, 20]]}


def test_single_bad_case_missing_case_and_role_bias_fail_calibration():
    idle = report()
    assert compare_control(idle, report())['passed']
    loaded = report(); loaded['stable'] = False
    assert not compare_control(idle, loaded)['passed']


def test_opposite_role_shifts_cannot_cancel_in_the_pooled_median():
    idle, loaded = report(), report()
    idle['per_case'][0]['candidate_samples_ns'] = [101.9] * 30
    idle['per_case'][0]['speedup'] = 100 / 101.9
    loaded['per_case'][0]['baseline_samples_ns'] = [103.8] * 30
    loaded['per_case'][0]['candidate_samples_ns'] = [101.9] * 30
    loaded['per_case'][0]['speedup'] = 103.8 / 101.9
    result = compare_control(idle, loaded)
    assert result['cases'][0]['relative_shift'] < .02
    assert result['cases'][0]['baseline_role_shift'] > .02
    assert not result['passed']
    loaded = report(); loaded['per_case'].pop()
    assert not compare_control(idle, loaded)['passed']
    loaded = report(); loaded['per_case'][0]['speedup'] = 1.03
    assert not compare_control(idle, loaded)['passed']
    loaded = copy.deepcopy(idle)
    loaded['per_case'][0]['baseline_samples_ns'] = [104.] * 30
    loaded['per_case'][0]['candidate_samples_ns'] = [104.] * 30
    assert not compare_control(idle, loaded)['passed']
