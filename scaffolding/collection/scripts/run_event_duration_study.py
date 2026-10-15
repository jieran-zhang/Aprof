#!/usr/bin/env python3
"""One preregistered 50 ms batch-duration study, never production admission.

Independent baseline-only calibration precedes fresh confirmation processes.
No retry, sample deletion, target search, or repeat adjustment is supported.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import selectors
import shutil
import statistics
import subprocess
import sys
import time

from diagnose_submission_stalls import oracle, source_files
from run_shared_timing_confirmation import BASE_ENVIRONMENT, binding, locks, save_new

ROOT = Path(__file__).resolve().parents[3]
HEADER = ROOT / 'scaffolding/benchmarks/cannbench/harness/device_duration_study.h'
ANCHOR = ROOT / 'scaffolding/curation/graph-base-0.5.1-event-duration-study-anchor.json'
PROTOCOL = 'shared_buffer_duration_study_v1'
PREFIX = 'APROF_SHARED_TIMING_JSON:'
ORDER = {'exp': [6, 9], 'sigmoid': [7, 4]}
PHASES = ('aa_before', 'formal', 'aa_after')
ROLES = ('baseline', 'candidate')
LOCKS = ['host-serial.lock', *[f'device-{i}.lock' for i in range(16)]]


def read(path):
    return json.loads(Path(path).read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def calibrated_repeat(values):
    require(len(values) == 3 and all(type(x) in (int, float) and math.isfinite(x) and x > 0 for x in values),
            'exactly three positive finite pilot intervals required')
    repeat = max(100, 100 * math.ceil(50.0 / statistics.median(values)))
    require(repeat <= 100000, 'calibrated repeat exceeds fixed cap; no clipping or retry')
    return repeat


def commands(mode):
    if mode == 'pilot':
        return ['prime 0 pilot', *[f'sample {i + 1} pilot {i}' for i in range(3)], 'finish 4']
    require(mode == 'confirmation', 'invalid study mode')
    rows = []
    for phase in PHASES:
        rows.append(f'prime {len(rows)} {phase}')
        for pair in range(5):
            rows.append(f'pair {len(rows)} {phase} {pair}')
    return [*rows, f'finish {len(rows)}']


def validate(messages, mode, cycle, repeat, operator):
    require(len(messages) == (6 if mode == 'pilot' else 20), 'native message count differs')
    first = messages[0]
    require(first['kind'] == 'ready' and first['operator'] == operator, 'native ready identity differs')
    common = ('operator', 'pid', 'device', 'context_address', 'stream_address', 'buffers', 'role_symbols')
    for message in messages:
        require(message['protocol'] == PROTOCOL and message['study_mode'] == mode
                and message['cycle_index'] == cycle and message['repeat'] == repeat
                and message['warmup'] == 10 and message['prime_repeat'] == 100
                and message['execution_mode'] == 'direct_enqueue' and message['device'] == 0
                and message['launches_per_operator'] == {'baseline': 1, 'candidate': 1}
                and all(message[k] == first[k] for k in common), 'native protocol/identity differs')
    require([m['command_index'] for m in messages[1:]] == list(range(len(messages) - 1)), 'native command order differs')
    for text, message in zip(commands(mode), messages[1:], strict=True):
        parts = text.split(); action = parts[0]
        require(message['kind'] == {'prime': 'prime', 'pair': 'pair', 'sample': 'pilot_sample', 'finish': 'complete'}[action],
                'native response kind differs')
        if action == 'finish':
            require(message['input_bytes_unchanged'] is True
                    and [v['role'] for v in message['untimed_verifications']] == list(ROLES), 'callback/input verification missing')
            require(message.get('pilot_samples' if mode == 'pilot' else 'pairs_per_phase') == (3 if mode == 'pilot' else 5),
                    'native final count differs')
            continue
        require(message['phase'] == parts[2], 'native phase differs')
        if action == 'prime':
            if mode == 'confirmation':
                order = list(ROLES if cycle % 2 == 0 else reversed(ROLES))
                require(message['prime_order'] == [*order, *reversed(order)], 'prime order differs')
            continue
        require(message['sample_index' if mode == 'pilot' else 'pair_index'] == int(parts[3]), 'sample index differs')
        selected = ('baseline',) if mode == 'pilot' else message['order']
        if mode == 'confirmation':
            require(list(selected) == list(ROLES if (cycle + int(parts[3])) % 2 == 0 else reversed(ROLES)), 'role order differs')
        for role in selected:
            sample = message[role]; value = sample['elapsed_ms']
            require(type(value) in (int, float) and math.isfinite(value) and value > 0
                    and sample['elapsed_ns'] == value * 1000000.0 / repeat
                    and sample['started_monotonic_ns'] <= sample['finished_monotonic_ns'], 'invalid complete-call interval')
            implementation = role if message['phase'] == 'formal' else 'baseline'
            require(sample['implementation'] == implementation and sample['launches_per_operator'] == 1,
                    'callback implementation differs')
        if mode == 'confirmation':
            require(message[selected[0]]['finished_monotonic_ns'] <= message[selected[1]]['started_monotonic_ns'],
                    'overlapping role intervals')


def controls(receipts):
    """Same all-sample CV, log role bias, and role-mean drift as the frozen bar."""
    values = {phase: {role: [] for role in ROLES} for phase in PHASES}
    for receipt in receipts:
        for message in receipt['messages']:
            if message['kind'] == 'pair':
                for role in ROLES:
                    values[message['phase']][role].append(message[role]['elapsed_ms'])
    result = {}
    for phase, by_role in values.items():
        a, b = [by_role[r] for r in ROLES]
        result[phase] = {'role_bias': abs(math.exp(statistics.fmean(math.log(y / x) for x, y in zip(a, b, strict=True))) - 1),
                         'baseline_cv': statistics.stdev(a) / statistics.fmean(a),
                         'candidate_cv': statistics.stdev(b) / statistics.fmean(b)}
    result['before_after_shift'] = {role: abs(statistics.fmean(values['aa_after'][role])
                                             / statistics.fmean(values['aa_before'][role]) - 1) for role in ROLES}
    result['passed'] = (all(row['role_bias'] <= .02 and row['baseline_cv'] <= .05 and row['candidate_cv'] <= .05
                            for phase, row in result.items() if phase in PHASES)
                        and all(v <= .02 for v in result['before_after_shift'].values()))
    result['minimum_observed_event_ms'] = min(x for v in values.values() for xs in v.values() for x in xs)
    return result


def prepare(output, predecessor):
    output.mkdir(exist_ok=False); cases = {}; files = {}
    for op, ids in ORDER.items():
        config = read(predecessor / op / 'config.json'); old_source = Path(config['build']['source_dir'])
        source = output / op / 'source'
        shutil.copytree(old_source, source, ignore=shutil.ignore_patterns('build', '__pycache__'))
        shutil.copyfile(HEADER, source / 'op_host/device_shared_timing.h')
        changed = [str(p.relative_to(source)) for p in source_files(source)
                   if binding(p)['sha256'] != binding(old_source / p.relative_to(source))['sha256']]
        require(changed == ['op_host/device_shared_timing.h'], 'only the study header may change')
        cases[op] = []
        for case_id in ids:
            case = next(c for c in config['cases'] if c['case_id'] == case_id)
            case['command'][0] = str(source / 'build' / op)
            for role in ROLES:
                case['verify_commands'][role] = [v.replace(str(old_source), str(source)) for v in case['verify_commands'][role]]
            cases[op].append(case)
            for path in case['prepared_files']:
                files[path] = binding(path)['sha256']
        for path in [*source_files(source), *source_files(old_source), predecessor / op / 'config.json']:
            files[str(path)] = binding(path)['sha256']
    producers = [Path(__file__), HEADER, *[Path(__file__).with_name(n) for n in
                 ('diagnose_submission_stalls.py', 'run_shared_timing_confirmation.py', 'replay_timing_diagnosis.py', 'run_aprof_job.py')]]
    for path in producers:
        files[str(path)] = binding(path)['sha256']
    save_new(output / 'preparation.json', {'created_at': time.time(), 'cases': cases, 'files': files,
                                          'predecessor': str(predecessor), 'source_intervention': 'copied header only'})


def build(output):
    prep = read(output / 'preparation.json')
    require(all(binding(p)['sha256'] == h for p, h in prep['files'].items()), 'preparation changed')
    save_new(output / 'build-started.json', {'started_at': time.time()}); rows = []
    try:
        for op in ORDER:
            source = output / op / 'source'
            for i, argv in enumerate((['cmake', '-S', str(source), '-B', str(source / 'build'), '-DCMAKE_BUILD_TYPE=Release'],
                                      ['cmake', '--build', str(source / 'build'), '-j2'])):
                began = time.time(); logpath = output / op / f'build-{i}.log'
                with logpath.open('xb') as log:
                    result = subprocess.run(argv, cwd=source, stdout=log, stderr=subprocess.STDOUT, timeout=600)
                rows.append({'argv': argv, 'started_at': began, 'finished_at': time.time(),
                             'exit_status': result.returncode, 'log': binding(logpath)})
                require(result.returncode == 0, 'study build failed')
        save_new(output / 'build-terminal.json', {'status': 'passed', 'commands': rows})
    except Exception as error:
        save_new(output / 'build-terminal.json', {'status': 'failed', 'commands': rows, 'error': str(error)})
        raise


def register(output):
    prep = read(output / 'preparation.json'); files = dict(prep['files'])
    # Offline review can harden the new Python runner after the native build.
    # Preserve the exact preparation producer; never permit native/input drift.
    producer = str(Path(__file__))
    if binding(producer)['sha256'] != files[producer]:
        snapshot = output / 'preparation-runner.py'
        require(binding(snapshot)['sha256'] == files[producer], 'preparation producer snapshot differs')
        files[str(snapshot)] = files[producer]
        files[producer] = binding(producer)['sha256']
    require(read(output / 'build-terminal.json')['status'] == 'passed', 'study build did not pass')
    history = [Path(prep['predecessor']) / 'campaign-replay.json', Path(prep['predecessor']) / 'confirmation-negative-summary.json']
    for name in ('submission-timing-diagnostics-20261014', 'submission-long-timeline-diagnostics-20261014'):
        history.extend(ROOT.parent / name / filename for filename in ('diagnostic-replay.json', 'mechanism-analysis.json'))
    for path in [output / 'preparation.json', output / 'build-started.json', output / 'build-terminal.json',
                 *[output / op / 'source/build' / op for op in ORDER], *history]:
        files[str(path)] = binding(path)['sha256']
    require(all(binding(p)['sha256'] == h for p, h in files.items()), 'registered study dependency changed')
    plan = {'schema_version': 1, 'purpose': 'independent_duration_method_study_only', 'created_at': time.time(),
            'cases': prep['cases'], 'order': ORDER, 'files': files, 'history': [binding(p) for p in history],
            'environment': BASE_ENVIRONMENT, 'cpu_affinity': sorted(os.sched_getaffinity(0)),
            'pilot': {'samples': 3, 'repeat': 100, 'role': 'baseline', 'separate_process_from_confirmation': True},
            'calibration': {'predicted_target_ms': 50, 'repeat_floor': 100, 'repeat_cap': 100000,
                            'formula': 'max(100, 100 * ceil(50 / median(three baseline pilot elapsed_ms)))',
                            'over_cap': 'fail_without_clipping', 'computations_per_case': 1,
                            'observed_duration_below_target': 'retain_and_report_without_repeat_adjustment_or_extra_failure'},
            'confirmation': {'cycles': 6, 'phases': list(PHASES), 'pairs_per_phase': 5,
                             'warmup_per_role': 10, 'prime_repeat': 100,
                             'cv_limit': .05, 'role_bias_limit': .02, 'role_mean_drift_limit': .02},
            'stop': 'first execution, correctness, identity or control failure stops that operator; other operator independent',
            'resampling': 'none', 'attempts_per_slot': 1,
            'budget': {'pilot_outer_seconds': 1200, 'confirmation_outer_seconds': 2400,
                       'native_process_seconds': 180, 'oracle_seconds': 180},
            'metric': 'mean duration of complete direct-enqueued calls in a sustained batch, not isolated-call latency',
            'accepted': False}
    save_new(output / 'plan.json', plan)
    for stage in ('pilot', 'confirm'):
        save_new(output / f'{stage}-job.json', {'job_id': f'event-duration-{stage}', 'argv': [sys.executable, str(Path(__file__)),
                 stage, '--output', str(output), '--anchor', str(ANCHOR)], 'cwd': str(ROOT),
                 'output_dir': str(output / f'{stage}-job'), 'environment': BASE_ENVIRONMENT,
                 'timeout_seconds': plan['budget']['pilot_outer_seconds' if stage == 'pilot' else 'confirmation_outer_seconds']})


def verify_plan(output, anchor, *, source_archive_refs=None):
    registered = read(anchor)
    require(registered['purpose'] == 'preregistered_fixed_50ms_duration_study'
            and registered['plan'] == binding(output / 'plan.json'), 'root anchor does not bind study plan')
    for stage in ('pilot', 'confirm'):
        require(registered[stage + '_job'] == binding(output / f'{stage}-job.json'), 'root anchor does not bind bounded job')
    plan = read(output / 'plan.json')
    if source_archive_refs is None:
        require(all(binding(p)['sha256'] == h for p, h in plan['files'].items()), 'registered dependency changed')
        require(sorted(os.sched_getaffinity(0)) == plan['cpu_affinity'], 'inherited affinity changed')
    else:
        # Only offline replay supplies archives. Collection always checks live bytes.
        from measurement_source_archive import HistoricalEvidence
        evidence = HistoricalEvidence(source_archive_refs)
        for path, expected in plan['files'].items():
            evidence.bind(path, expected)
    return plan


def native(plan, output, op, case, mode, cycle, repeat):
    directory = output / op / f'case-{case["case_id"]:02d}' / (mode if mode == 'pilot' else f'cycle-{cycle}')
    directory.mkdir(parents=True, exist_ok=False)
    argv = [v.replace('{cycle_dir}', str(directory)) for v in case['command']]
    env = {k: v for k, v in os.environ.items() if not k.startswith('APROF_')}
    env.update(plan['environment'], APROF_SHARED_CYCLE=str(cycle), APROF_DURATION_MODE=mode, APROF_DURATION_REPEAT=str(repeat))
    source = output / op / 'source'
    receipt = {'started_at': time.time(), 'argv': argv, 'cycle': cycle, 'repeat': repeat, 'mode': mode,
               'operator': op, 'case_id': case['case_id'], 'messages': [], 'commands': [], 'accepted': False}
    save_new(directory / 'started.json', {'started_at': receipt['started_at'], 'argv': argv})
    transcript = bytearray(); pending = bytearray()
    with (directory / 'stderr.log').open('xb') as stderr:
        child = subprocess.Popen(argv, cwd=source, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr)
        selector = selectors.DefaultSelector(); selector.register(child.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + plan['budget']['native_process_seconds']
        def ack():
            while True:
                while b'\n' in pending:
                    line, _, rest = pending.partition(b'\n'); pending[:] = rest
                    if line.startswith(PREFIX.encode()):
                        return json.loads(line[len(PREFIX):])
                require(time.monotonic() < deadline, 'native study lifetime budget exceeded')
                if not selector.select(min(1, max(0, deadline - time.monotonic()))):
                    continue
                chunk = os.read(child.stdout.fileno(), 65536)
                require(bool(chunk), 'native study exited before ACK')
                transcript.extend(chunk); pending.extend(chunk)
                require(len(transcript) <= 16 * 1024 * 1024, 'native stdout exceeds RAM bound')
        try:
            receipt['messages'].append(ack())
            for text in commands(mode):
                began = time.monotonic_ns(); child.stdin.write((text + '\n').encode()); child.stdin.flush()
                receipt['messages'].append(ack())
                receipt['commands'].append({'text': text, 'request_monotonic_ns': began, 'response_monotonic_ns': time.monotonic_ns()})
            child.stdin.close(); child.wait(timeout=max(.01, deadline - time.monotonic()))
            transcript.extend(child.stdout.read()); receipt['exit_status'] = child.returncode
            receipt['native_finished_at'] = time.time()
            require(child.returncode == 0, 'native study process failed')
            validate(receipt['messages'], mode, cycle, repeat, op)
            receipt['verifications'] = oracle({'case': case, 'source_dir': str(source)}, directory)
            receipt['status'] = 'complete_research_only'
        except Exception as error:
            receipt.update(status='failed', error=str(error))
            if child.poll() is None:
                child.kill(); child.wait(timeout=20)
            receipt['exit_status'] = child.returncode
            raise
        finally:
            selector.close(); receipt['finished_at'] = time.time()
            (directory / 'stdout.log').write_bytes(transcript)
            receipt['stdout'] = binding(directory / 'stdout.log'); receipt['stderr'] = binding(directory / 'stderr.log')
            save_new(directory / 'receipt.json', receipt)
    return receipt, directory / 'receipt.json'


def pilot(output, anchor):
    plan = verify_plan(output, anchor); save_new(output / 'pilot-started.json', {'started_at': time.time(), 'anchor': binding(anchor)})
    rows = {}; repeats = {}
    with locks(LOCKS):
        for op in ORDER:
            failed = False
            for case in plan['cases'][op]:
                key = f'{op}-{case["case_id"]}'
                if failed:
                    rows[key] = {'status': 'not_run', 'reason': 'prior operator pilot failed'}; continue
                try:
                    receipt, path = native(plan, output, op, case, 'pilot', 0, 100)
                    values = [m['baseline']['elapsed_ms'] for m in receipt['messages'] if m['kind'] == 'pilot_sample']
                    repeat = calibrated_repeat(values)
                    rows[key] = {'status': 'complete', 'receipt': binding(path), 'values_ms': values, 'repeat': repeat}
                    repeats[key] = repeat
                except Exception as error:
                    path = output / op / f'case-{case["case_id"]:02d}/pilot/receipt.json'
                    rows[key] = {'status': 'failed', 'error': str(error), 'receipt': binding(path) if path.exists() else None}; failed = True
    save_new(output / 'pilot-terminal.json', {'plan': binding(output / 'plan.json'), 'finished_at': time.time(), 'rows': rows, 'accepted': False})
    save_new(output / 'repeat-freeze.json', {'created_at': time.time(), 'plan': binding(output / 'plan.json'),
             'pilot': binding(output / 'pilot-terminal.json'), 'repeats': repeats, 'accepted': False})


def replay_pilot(output):
    frozen = read(output / 'repeat-freeze.json'); terminal = read(output / 'pilot-terminal.json'); plan = read(output / 'plan.json')
    require(frozen['pilot'] == binding(output / 'pilot-terminal.json') and frozen['plan'] == binding(output / 'plan.json'), 'pilot binding changed')
    repeats = {}
    require(set(terminal['rows']) == {f'{op}-{case_id}' for op, ids in ORDER.items() for case_id in ids}, 'pilot slots differ')
    for key, row in terminal['rows'].items():
        if row['status'] != 'complete':
            continue
        receipt = replay_receipt(row['receipt'], plan=plan, output=output)
        require(receipt['mode'] == 'pilot' and key == f'{receipt["operator"]}-{receipt["case_id"]}'
                and receipt['cycle'] == 0 and receipt['repeat'] == 100, 'pilot slot identity differs')
        values = [m['baseline']['elapsed_ms'] for m in receipt['messages'] if m['kind'] == 'pilot_sample']
        require(row['values_ms'] == values and row['repeat'] == calibrated_repeat(values), 'pilot calibration changed')
        repeats[key] = row['repeat']
    require(repeats == frozen['repeats'], 'frozen repeat table differs from native pilot')
    return frozen


def confirm(output, anchor):
    plan = verify_plan(output, anchor); frozen = replay_pilot(output)
    save_new(output / 'confirmation-started.json', {'started_at': time.time(), 'anchor': binding(anchor),
                                                   'repeat_freeze': binding(output / 'repeat-freeze.json')})
    rows = {}
    with locks(LOCKS):
        for op in ORDER:
            failed = any(f'{op}-{c["case_id"]}' not in frozen['repeats'] for c in plan['cases'][op])
            for case in plan['cases'][op]:
                key = f'{op}-{case["case_id"]}'
                if failed:
                    rows[key] = {'status': 'not_run', 'reason': 'prior operator failure'}; continue
                receipts = []; references = []; repeat = frozen['repeats'][key]
                row = {'status': 'running', 'repeat': repeat, 'cycles': references}
                try:
                    for cycle in range(6):
                        receipt, path = native(plan, output, op, case, 'confirmation', cycle, repeat)
                        receipts.append(receipt); quality = controls([receipt])
                        references.append({'receipt': binding(path), 'controls': quality})
                        require(quality['passed'], 'fixed per-cycle measurement control failed')
                    row['overall'] = controls(receipts)
                    require(row['overall']['passed'], 'fixed overall measurement control failed')
                    row['status'] = 'complete_research_controls_passed'
                except Exception as error:
                    row.update(status='failed', error=str(error)); failed = True
                    path = output / op / f'case-{case["case_id"]:02d}/cycle-{len(receipts)}/receipt.json'
                    if path.exists() and not any(r['receipt']['path'] == str(path) for r in references):
                        row['failed_execution_receipt'] = binding(path)
                save_new(output / op / f'case-{case["case_id"]:02d}/confirmation-terminal.json', row)
                rows[key] = row
    save_new(output / 'confirmation-terminal.json', {'finished_at': time.time(), 'rows': rows, 'accepted': False,
             'research_controls_passed': all(r['status'] == 'complete_research_controls_passed' for r in rows.values())})


def replay_receipt(reference, *, plan, output):
    require(binding(reference['path']) == reference, 'native receipt changed'); receipt = read(reference['path'])
    op = receipt['operator']; case = next(c for c in plan['cases'][op] if c['case_id'] == receipt['case_id'])
    directory = output / op / f'case-{case["case_id"]:02d}' / ('pilot' if receipt['mode'] == 'pilot' else f'cycle-{receipt["cycle"]}')
    require(reference['path'] == str(directory / 'receipt.json')
            and receipt['argv'] == [v.replace('{cycle_dir}', str(directory)) for v in case['command']],
            'native command or case directory differs')
    require(set(receipt['verifications']) == set(ROLES), 'both independent callback oracles required')
    for key in ('stdout', 'stderr'):
        require(binding(receipt[key]['path']) == receipt[key], 'native transcript changed')
    messages = [json.loads(line[len(PREFIX):]) for line in Path(receipt['stdout']['path']).read_text().splitlines() if line.startswith(PREFIX)]
    require(messages == receipt['messages'], 'native stdout differs from receipt')
    require(receipt['exit_status'] == 0, 'native execution failed')
    validate(messages, receipt['mode'], receipt['cycle'], receipt['repeat'], receipt['operator'])
    for role, row in receipt['verifications'].items():
        require(row['exit_status'] == 0 and row['argv'] == [v.replace('{cycle_dir}', str(directory)) for v in case['verify_commands'][role]],
                'oracle execution or case command differs')
        for key in ('output', 'log', 'result'):
            require(binding(row[key]['path']) == row[key], 'oracle artifact changed')
        require(row['output']['path'] == str(directory / f'{role}.bin')
                and row['log']['path'] == str(directory / f'{role}-verify.log')
                and row['result']['path'] == str(directory / f'{role}-result.json'), 'oracle artifacts outside callback directory')
        result = read(row['result']['path']); printed = []
        for line in Path(row['log']['path']).read_text().splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and 'passed' in value:
                printed.append(value)
        require(printed == [result] and result['passed'] is True and result['case_id'] == case['case_id'], 'oracle result/stdout/case differs')
    return receipt


def replay(output, anchor, *, source_archive_refs=None):
    plan = verify_plan(output, anchor, source_archive_refs=source_archive_refs); frozen = replay_pilot(output)
    terminal = read(output / 'confirmation-terminal.json')
    require(set(terminal['rows']) == {f'{op}-{case_id}' for op, ids in ORDER.items() for case_id in ids}, 'confirmation slots differ')
    for key, row in terminal['rows'].items():
        receipts = []
        for index, cycle in enumerate(row.get('cycles', [])):
            receipt = replay_receipt(cycle['receipt'], plan=plan, output=output); receipts.append(receipt)
            require(receipt['mode'] == 'confirmation' and receipt['cycle'] == index
                    and receipt['repeat'] == frozen['repeats'][key]
                    and key == f'{receipt["operator"]}-{receipt["case_id"]}'
                    and receipt['started_at'] > frozen['created_at'], 'confirmation slot identity or lifecycle differs')
            require(controls([receipt]) == cycle['controls'], 'cycle control summary differs')
        if row['status'] == 'complete_research_controls_passed':
            require(len(receipts) == 6 and all(controls([r])['passed'] for r in receipts)
                    and controls(receipts) == row['overall'] and row['overall']['passed'], 'overall or individual-cycle controls differ')
    return {'valid': True, 'accepted': False, 'plan': binding(output / 'plan.json'),
            'pilot': binding(output / 'pilot-terminal.json'), 'repeat_freeze': binding(output / 'repeat-freeze.json'),
            'confirmation': binding(output / 'confirmation-terminal.json'),
            'research_controls_passed': all(row['status'] == 'complete_research_controls_passed' for row in terminal['rows'].values()),
            'limitation': 'Four diagnostic cases only. This study never qualifies production or changes past failures.'}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare', 'build', 'register', 'pilot', 'confirm', 'replay'])
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--predecessor', type=Path); parser.add_argument('--anchor', type=Path)
    args = parser.parse_args(); output = args.output.resolve()
    if args.action == 'prepare':
        prepare(output, args.predecessor.resolve(strict=True))
    elif args.action in ('build', 'register'):
        globals()[args.action](output)
    else:
        require(args.anchor is not None, 'root preregistration anchor required')
        if args.action == 'replay':
            print(json.dumps(replay(output, args.anchor), indent=2))
        else:
            globals()[args.action](output, args.anchor)


if __name__ == '__main__':
    main()
