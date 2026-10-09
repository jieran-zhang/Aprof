#!/usr/bin/env python3
"""Read-only audit of completed feedback control wrappers; prints JSON only.

--cases is the frozen ordered sentinel list, never inferred from observed rows.
Before-only is preliminary, before+reverse may authorize candidate measurement,
and before+reverse+after validates all supplied controls. This is not a runtime
gate verdict or proof of candidate correctness/performance. No raw samples are
removed, no retries are performed, and no files, locks or artifacts are written.
Only the four small archived JSON artifacts are hashed. Source/input/binary
hashes are compared as recorded bindings, without reading live large files.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
from cannbench_device_timing import summarize_multicase
from run_level1_serial import compare_controls

PROTOCOL = dict(pairs=30, warmup=10, repeat=100, precondition_samples=1,
                single_live_context=True, reuse_verifier=True, capture_replay=False,
                checkpoint_every_pair=False)
FILES = ('request.json', 'process/execution.json', 'measurement/raw_measurements.json',
         'measurement/measurement_report.json')


def read(path):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out: raise ValueError('duplicate JSON key: '+key)
            out[key] = value
        return out
    def reject(value): raise ValueError('nonfinite JSON: '+value)
    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs, parse_constant=reject)


def sha(path):
    return 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized_hash(value):
    if not isinstance(value, str): raise ValueError('missing recorded hash')
    value = value.removeprefix('sha256:')
    if not re.fullmatch('[0-9a-f]{64}', value): raise ValueError('invalid recorded hash')
    return value


def require(condition, message):
    if not condition: raise ValueError(message)


def timestamp(value):
    result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'timestamp must include timezone')
    return result


def control(path, cases, reverse):
    path = Path(path).resolve()
    completion = read(path/'completion.json')
    require(completion.get('status') == 'passed' and completion.get('error') is None,
            'wrapper did not finish successfully')
    require(timestamp(completion['started_at']) <= timestamp(completion['finished_at']), 'wrapper interval invalid')
    values = {}
    for name in FILES:
        require(sha(path/name) == completion['artifacts'].get(name), 'artifact hash mismatch: '+name)
        values[name] = read(path/name)
    request = values['request.json']; raw = values['measurement/raw_measurements.json']
    report = values['measurement/measurement_report.json']; process = values['process/execution.json']
    require(completion['request'] == request, 'completion/request mismatch')
    require(request['command'] == 'control', 'not an A/A control request')
    require(request['cases'] == cases, 'request differs from frozen ordered cases')
    require(type(request['reverse']) is bool and request['reverse'] is reverse, 'wrong startup orientation')
    require(request['protocol'] == PROTOCOL, 'request differs from frozen control protocol')
    require(set(request['trees']) == {'baseline', 'candidate'}, 'missing A/A source roles')
    baseline, candidate = (request['trees'][role] for role in ('baseline', 'candidate'))
    require(baseline == candidate, 'A/A source paths/inventories/binaries differ by role')
    require(bool(baseline['sources']), 'source inventory missing')
    for value in baseline['sources'].values(): normalized_hash(value)
    require(bool(request['inputs']['files']), 'prepared input inventory missing')
    for value in request['inputs']['files'].values(): normalized_hash(value)
    for key in ('controller_sha256', 'timing_producer_sha256', 'validator_sha256'):
        normalized_hash(request[key])
    binary = normalized_hash(baseline['executable_sha256'])
    require(all(normalized_hash(raw[role+'_executable_sha256']) == binary for role in ('baseline', 'candidate')),
            'raw executable hash differs from request')
    require(normalized_hash(raw['producer_sha256']) == normalized_hash(request['timing_producer_sha256']),
            'raw timing producer differs from request')
    require(raw.get('verification_protocol') == 'in_process_reuse_v1', 'raw verifier protocol mismatch')
    require(normalized_hash(raw['verifier_source_hash']) == normalized_hash(baseline['sources']['scripts/verify_result.py']),
            'raw verifier source differs from request')
    require(raw.get('operator') == baseline['operator'], 'raw operator differs from request')
    require(raw.get('host') == completion['host'] == process['host'], 'recorded hosts differ')
    require(raw.get('device') == process['logical_device'] == 0 and request['device'] == process['physical_device'] == completion['physical_device'],
            'recorded device bindings differ')
    require(process.get('status') == 'passed' and process.get('exit_status') == 0 and process.get('error') is None,
            'measurement process did not pass')
    require(timestamp(completion['started_at']) <= timestamp(process['started_at']) <= timestamp(process['finished_at']) <= timestamp(completion['finished_at']),
            'process interval outside wrapper interval')
    for field in ('pairs', 'warmup', 'repeat', 'precondition_samples', 'single_live_context', 'checkpoint_every_pair'):
        require(type(raw.get(field)) is type(PROTOCOL[field]) and raw[field] == PROTOCOL[field], 'raw protocol mismatch: '+field)
    require(raw.get('reverse_startup') is reverse, 'raw startup orientation differs from request')
    require(not any(key in raw for key in ('capture_replay', 'execution_mode', 'captured_operator_calls')),
            'unexpected graph capture/replay protocol')
    require(raw.get('timing_scope') == 'complete_operator_device_event_interval', 'raw timing scope mismatch')
    recomputed = summarize_multicase(raw, cases)
    require(recomputed == report, 'archived report differs from recomputation of complete raw evidence')
    self_check = compare_controls(report, report, cases)
    if not (report['stable'] and report['case_ids'] == cases and all(c['pair_count'] == 30 for c in report['per_case'])):
        self_check = dict(accepted=False, reason='unstable, incomplete or wrong-pair control: '+'; '.join(report['reasons']))
    rows = [{key: row[key] for key in ('case_id', 'pair_count', 'baseline_cv', 'candidate_cv',
             'baseline_median_ns', 'candidate_median_ns', 'speedup')} for row in report['per_case']]
    for row in rows: row['role_bias'] = abs(row['speedup'] - 1) if row['speedup'] is not None else None
    return dict(path=str(path), raw_path=str(path/'measurement/raw_measurements.json'),
                report_path=str(path/'measurement/measurement_report.json'), accepted=self_check['accepted'],
                error=None if self_check['accepted'] else self_check['reason'], per_case=rows,
                request=request, report=report, completion=completion)


def audit(before, cases, reverse=None, after=None):
    result = dict(audit_hardware_executed=False, writes_performed=False, expected_cases=cases,
                  accepted=False, error=None, ready_for_candidate=False, full_control_validation=False,
                  stage='before_only_preliminary' if reverse is None else 'before_reverse' if after is None else 'before_reverse_after',
                  controls={}, comparisons={}, errors=[],
                  scope='Recorded controls only; not a runtime gate or candidate verdict. Source/input/binary bytes are not reread.')
    if not cases or any(type(case) is not int or case < 1 for case in cases) or len(set(cases)) != len(cases):
        result['error'] = 'expected cases must be a nonempty unique ordered integer list'
        result['errors'].append(result['error']); return result
    if after is not None and reverse is None:
        result['error'] = 'after requires a reverse control'
        result['errors'].append(result['error']); return result
    supplied = [('before', before, False)]
    if reverse is not None: supplied.append(('reverse', reverse, True))
    if after is not None: supplied.append(('after', after, False))
    loaded = {}
    for label, path, orientation in supplied:
        try:
            row = control(path, cases, orientation); loaded[label] = row
            result['controls'][label] = {k:v for k,v in row.items() if k not in ('request', 'report', 'completion')}
            if not row['accepted']: result['errors'].append(label+': '+row['error'])
        except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
            message = label+': '+str(exc); result['errors'].append(message)
            result['controls'][label] = dict(path=str(Path(path).resolve()),
                raw_path=str(Path(path).resolve()/'measurement/raw_measurements.json'), accepted=False, error=message)
    labels = list(loaded)
    for i, left in enumerate(labels):
        for right in labels[i+1:]:
            a,b = loaded[left], loaded[right]
            req_a = {k:v for k,v in a['request'].items() if k != 'reverse'}
            req_b = {k:v for k,v in b['request'].items() if k != 'reverse'}
            if req_a != req_b: result['errors'].append(left+'/'+right+': source/input/protocol/producer request bindings changed')
            if (a['completion']['host'] != b['completion']['host'] or
                timestamp(a['completion']['finished_at']) > timestamp(b['completion']['started_at'])):
                result['errors'].append(left+'/'+right+': different hosts or overlapping/reversed control chronology')
            comparison = compare_controls(a['report'], b['report'], cases)
            result['comparisons'][left+'/'+right] = comparison
            if not comparison['accepted']: result['errors'].append(left+'/'+right+': '+comparison['reason'])
    result['accepted'] = not result['errors']
    result['ready_for_candidate'] = result['accepted'] and reverse is not None
    result['full_control_validation'] = result['accepted'] and reverse is not None and after is not None
    result['error'] = '; '.join(result['errors']) or None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', required=True, type=Path)
    parser.add_argument('--reverse', type=Path)
    parser.add_argument('--after', type=Path)
    parser.add_argument('--cases', required=True, help='Frozen ordered comma-separated case IDs')
    args = parser.parse_args()
    result = audit(args.before, [int(c) for c in args.cases.split(',')], args.reverse, args.after)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0 if result['accepted'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
