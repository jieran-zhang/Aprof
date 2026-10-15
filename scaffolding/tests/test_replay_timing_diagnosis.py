import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'collection/scripts/replay_timing_diagnosis.py'
SPEC = importlib.util.spec_from_file_location('replay_diagnosis', SCRIPT)
replay = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(replay)


def command():
    ready = dict(pid=1, context='0x11', stream='0x12', device=0, operator='exp', repeat=100, affinity=[0])
    sample = dict(ready, type='sample', slot=0, sequence=4, cpu=0, cpu_before=0, cpu_after=0,
                  started_monotonic_ns=102, enqueue_begin_monotonic_ns=103, enqueue_end_monotonic_ns=104,
                  synchronized_monotonic_ns=105, monotonic_ns=106, event_ns_per_operator=100.)
    return ready, dict(sample=sample, request_monotonic_ns=101, response_monotonic_ns=107)


@pytest.mark.parametrize('field,value', [('slot', 1), ('pid', 2), ('sequence', 5),
                                         ('enqueue_end_monotonic_ns', 108), ('event_ns_per_operator', float('nan'))])
def test_reject_physical_identity_sequence_and_chronology_tampering(field, value):
    ready, receipt = command()
    assert replay.verify_sample(receipt, ready, 'sample', 0, 4, 100) == 107
    receipt['sample'][field] = value
    with pytest.raises(ValueError):
        replay.verify_sample(receipt, ready, 'sample', 0, 4, 100)


def test_historical_rows_are_excluded_but_failed_fresh_cycle_is_not_averaged_away():
    conditions = {'shared': ['shared'], 'split': ['map_AB', 'map_BA'],
                  'residency': ['solo_before', 'secondary_idle', 'dual_active_serial', 'solo_after']}
    raws = []
    for op in ('exp', 'sigmoid'):
        for cycle in range(6):
            for mode in conditions:
                for logging in replay.FACTORS:
                    raw = dict(cell=dict(operator=op, cycle=cycle, mode=mode, logging=logging), records=[],
                               logging_reference_payload={'records': [{'event_ns_per_operator': -1e99}]})
                    for condition in conditions[mode]:
                        for _ in range(5):
                            roles = {role: {'sample': {'event_ns_per_operator': 100., 'slot': index}}
                                     for index, role in enumerate(replay.ROLES)}
                            if mode == 'shared' and cycle == 0:
                                roles['B']['sample']['event_ns_per_operator'] = 110.
                            raw['records'].append(dict(condition=condition, cycle=cycle, roles=roles))
                    raws.append(raw)
    result = replay.recompute_controls(raws, {'conditions': conditions})
    shared = [r for r in result['rows'] if r['mode'] == 'shared']
    assert all(r['passed'] for r in shared if r['cycle'] is None)
    assert not any(r['passed'] for r in shared if r['cycle'] == 0)
    assert not result['all_controls_passed']
    changed = copy.deepcopy(raws)
    changed[0]['logging_reference_payload'] = {'arbitrary_historical_failure': True}
    assert replay.recompute_controls(changed, {'conditions': conditions}) == result


def test_native_oracle_success_flag_cannot_override_metrics_or_stdout(tmp_path):
    output = tmp_path / 'output.bin'; output.write_bytes(bytes(8))
    metadata = dict(case_id=1, shape=[4], dtype='float16', numel=4, input='frozen-input', output=str(output))
    (tmp_path / 'metadata.json').write_text(json.dumps(metadata))
    source = tmp_path / 'source'; (source / 'scripts').mkdir(parents=True)
    execution = dict(argv=[sys.executable, str(source / 'scripts/verify_result.py'), '--metadata', str(tmp_path / 'metadata.json')],
                     started_at=10., finished_at=11., exit_status=0, output_hash=replay.digest(output))
    (tmp_path / 'execution.json').write_text(json.dumps(execution))
    result = dict(case_id=1, shape=[4], dtype='float16', numel=4, attrs={}, mere=0., mare=0., threshold=2**-10,
                  special_values_match=True, passed=True)
    plan = {'host_tools': {'python': {'path': sys.executable, 'sha256': replay.digest(sys.executable)}}}
    def save(value, printed=None):
        (tmp_path / 'result.json').write_text(json.dumps(value))
        (tmp_path / 'stdout.log').write_text(json.dumps(value if printed is None else printed) + '\n')
    save(result)
    replay.verify_oracle(tmp_path, metadata, {'source_dir': str(source)}, plan, replay.Evidence(), earliest=9., latest=12.)
    failed = dict(result, mere=1.)
    save(failed)
    with pytest.raises(ValueError, match='numerical correctness'):
        replay.verify_oracle(tmp_path, metadata, {'source_dir': str(source)}, plan, replay.Evidence())
    save(result, printed=failed)
    with pytest.raises(ValueError, match='actual verifier stdout'):
        replay.verify_oracle(tmp_path, metadata, {'source_dir': str(source)}, plan, replay.Evidence())
