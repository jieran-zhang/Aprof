#!/usr/bin/env python3
"""Qualify a separately frozen CPU-affinity recovery after unpinned A/A fails."""
from __future__ import annotations

import concurrent.futures
import json
import statistics

from collect_level1_traces import Campaign, ROOT
from run_aprof_job import dump
from aprof_runtime.traces import register_json_artifact, verify_trace


def compare_control(idle, loaded):
    controls = {row['case_id']: row for row in idle['per_case']}
    rows = []
    for row in loaded['per_case']:
        ref = controls.get(row['case_id'])
        if ref is None:
            continue
        # Both roles execute the identical binary. Use both role medians and
        # independently reject role bias, rather than choosing a faster role.
        a = statistics.median(ref['baseline_samples_ns'] + ref['candidate_samples_ns'])
        b = statistics.median(row['baseline_samples_ns'] + row['candidate_samples_ns'])
        shift = abs(b / a - 1)
        baseline_shift = abs(statistics.median(row['baseline_samples_ns']) / statistics.median(ref['baseline_samples_ns']) - 1)
        candidate_shift = abs(statistics.median(row['candidate_samples_ns']) / statistics.median(ref['candidate_samples_ns']) - 1)
        idle_bias = abs(ref['speedup'] - 1)
        loaded_bias = abs(row['speedup'] - 1)
        rows.append({'case_id': row['case_id'], 'idle_median_ns': a, 'loaded_median_ns': b,
            'relative_shift': shift, 'baseline_role_shift': baseline_shift, 'candidate_role_shift': candidate_shift,
            'idle_role_bias': idle_bias, 'loaded_role_bias': loaded_bias,
            'passed': max(shift, baseline_shift, candidate_shift, idle_bias, loaded_bias) <= .02})
    return {'passed': bool(idle['stable'] and loaded['stable'] and len(rows) == 4 and all(x['passed'] for x in rows)),
        'idle_stable': idle['stable'], 'loaded_stable': loaded['stable'], 'cases': rows}


def run():
    c = Campaign(); op = 'exp'; root = c.run / 'calibration/affinity-v1'
    verify_trace(c.task(op) / 'trace_events.jsonl', c.store(op))
    prior = json.loads((c.run / 'calibration/selection-unpinned.json').read_text())
    if prior['accepted']:
        raise ValueError('recovery requires an evidenced unpinned calibration failure')
    devices = {'local': [0, 2, 4, 6], 'decode': [2, 4, 6, 8]}
    affinities = {host: {str(d): [8 + 4*d] for d in values} for host, values in devices.items()}
    protocol = {'schema_version': '1.0.0', 'name': 'affinity-v1', 'widths': [8, 4, 2, 1],
        'devices': devices, 'cpu_affinity_by_host': affinities,
        'cases': [1, 8, 14, 20], 'pairs': 30, 'warmup': 10, 'repeat': 100,
        'max_cv': .05, 'max_idle_shift': .02, 'max_same_binary_role_bias': .02,
        'median_definition': 'both-role pooled median plus independently checked baseline and candidate role medians',
        'control_policy': 'one idle device per host; fresh idle controls before every loaded width',
        'reason': 'Remove uncontrolled CPU migration/placement from complete-operator event intervals; retain all prior failed measurements.'}
    path = root / 'protocol.json'
    if path.exists() and json.loads(path.read_text()) != protocol:
        raise ValueError('affinity protocol is immutable')
    dump(path, protocol)
    with c.store(op) as store:
        ref = register_json_artifact(store, protocol)
        c.writer(op, store).append('next_step_decided', {'action': 'freeze_affinity_calibration_protocol',
            'reason': protocol['reason'], 'evidence_refs': [ref]}, event_id='affinity-calibration-protocol')

    def measure(host, device, phase, count=1):
        out = root / phase / host / f'device-{device:02d}'
        env = {}
        if count > 1:
            env = {'APROF_CALIBRATION_BARRIER': str(root / phase / 'barrier'),
                'APROF_CALIBRATION_PARTICIPANT': f'{host}-{device}', 'APROF_CALIBRATION_COUNT': str(count)}
        cpus = ','.join(map(str, affinities[host][str(device)]))
        argv = ['/usr/bin/taskset', '--cpu-list', cpus, '/usr/local/python3.11.15/bin/python3',
            ROOT / 'scaffolding/collection/scripts/cannbench_device_timing.py', 'measure', '--baseline', c.task(op)/'baseline',
            '--candidate', c.task(op)/'baseline', '--cases', '1,8,14,20', '--device', '0',
            '--output', out, '--input-root', c.prepared(op), '--pairs', '30', '--warmup', '10',
            '--repeat', '100', '--external-lock']
        result = c.job(op, f'calibration/affinity-v1-{phase}-{host}-{device}', argv,
            host=host, device=device, timeout=1800, environment=env)
        c.record(op, result, stage='concurrency_calibration')
        report = out / 'measurement_report.json'
        print(phase, host, device, result['status'], flush=True)
        return json.loads(report.read_text()) if report.exists() else {'stable': False, 'per_case': []}

    for width in protocol['widths']:
        selected = {host: values[:max(1, width//2)] for host, values in devices.items()}
        if width == 1:
            selected['decode'] = []
        def idle_host(host):
            return {device: measure(host, device, f'idle-{width}') for device in selected[host]}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            idle = dict(zip(selected, pool.map(idle_host, selected)))
        participants = [(h, d) for h, values in selected.items() for d in values]
        outcomes = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=width) as pool:
            futures = {pool.submit(measure, h, d, f'loaded-{width}', width): (h,d) for h,d in participants}
            for future in concurrent.futures.as_completed(futures):
                host, device = futures[future]
                outcome = {'host': host, 'physical_device': device,
                    **compare_control(idle[host][device], future.result())}
                outcomes.append(outcome)
                print('qualified', width, host, device, outcome['passed'], flush=True)
        accepted = all(row['passed'] for row in outcomes)
        report_path = root / f'calibration-{width}.json'
        dump(report_path, {'schema_version': '1.0.0', 'width': width, 'accepted': accepted, 'outcomes': outcomes})
        if accepted:
            selection = {'schema_version': '1.0.0', 'accepted': True, 'max_device_jobs': width,
                'physical_devices_by_host': selected, 'cpu_affinity_by_host': affinities,
                'calibration_ref': str(report_path), 'protocol_ref': str(path), 'protocol': protocol}
            dump(c.run / 'calibration/selection.json', selection)
            return selection
    selection = {'schema_version': '1.0.0', 'accepted': False, 'max_device_jobs': 0,
        'protocol_ref': str(path), 'reason': 'Unpinned and CPU-affinity recovery topologies failed the predeclared A/A qualification.'}
    dump(c.run / 'calibration/selection.json', selection)
    return selection


if __name__ == '__main__':
    print(json.dumps(run(), allow_nan=False))
