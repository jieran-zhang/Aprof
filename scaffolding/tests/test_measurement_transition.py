"""A new method must retain its preregistered calibration and control policy."""
import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'collection/scripts'))
from replay_measurement_transition import replay_transition
from replay_timing_diagnosis import digest


@pytest.mark.parametrize(('section', 'key', 'value', 'error'), [
    ('calibration', 'target_ms', 100, 'calibration policy'),
    ('calibration', 'over_cap', 'clip', 'calibration policy'),
    ('unchanged_controls', 'cv', .1, 'control thresholds'),
    ('unchanged_controls', 'scope', 'pooled_only', 'control thresholds'),
])
def test_changed_calibration_or_controls_rejected_before_hardware_replay(tmp_path, section, key, value, error):
    plan = {'schema_version': 1, 'purpose': 'prospective_calibrated_shared_buffer_v2',
        'protocol': 'shared_buffer_acl_event_v2',
        'calibration': {'pilot_processes_per_case': 1, 'pilot_baseline_samples': 3, 'pilot_repeat': 100,
            'target_ms': 50, 'repeat_floor': 100, 'repeat_cap': 100000,
            'formula': 'max(100,100*ceil(50/median(pilot_elapsed_ms)))',
            'over_cap': 'fail_without_clipping', 'recalibration': 'none'},
        'unchanged_controls': {'cv': .05, 'role_bias': .02, 'before_after_shift': .02,
            'cycles': 6, 'pairs_per_phase_per_cycle': 5, 'scope': 'each_cycle_and_all_cycles'}}
    changed = copy.deepcopy(plan)
    changed[section][key] = value
    path = tmp_path / 'transition.json'
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match=error):
        replay_transition({'path': str(path), 'sha256': digest(path)})
