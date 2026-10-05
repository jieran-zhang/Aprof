"""Synthetic CPU evidence and fake ACL only; no accelerator program is loaded."""
import copy
import csv
from decimal import Decimal
import difflib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import msprof_exploration_report as report
import cannbench_msprof_timing as timing
import shared_context_build as build_tool


def put(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False))
    return str(path)


def data(path, value=b'fixture'):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)
    return str(path)


def setup_inputs(root, ids=(1,), multi=False, kind='aa'):
    op = 'foreach_norm' if multi else 'exp'
    original = ROOT / 'benchmarks/cannbench/harness/shared_context/runner.cpp'
    runner_root = root / 'runner'
    data(runner_root / 'original-runner.cpp', original.read_bytes())
    data(runner_root / 'runner.cpp', timing.instrument(original.read_text(), 10).encode())
    data(runner_root / 'abi.h', original.with_name('abi.h').read_bytes())
    patch = ''.join(difflib.unified_diff(original.read_text().splitlines(True), timing.instrument(original.read_text(), 10).splitlines(True),
                                      fromfile='original-runner.cpp', tofile='runner.cpp'))
    data(runner_root / 'harness.patch', patch.encode())
    runner_binary = data(runner_root / 'runner', b'not executable: CPU evidence fixture')
    runner_path = put(runner_root / 'build.json', {'version': report.PRODUCER, 'repeat': 10, 'pairs': 30, 'warmup': 10,
                       'runner': runner_binary, 'runner_hash': report.sha(runner_binary),
                       'source_hash': report.sha(runner_root / 'runner.cpp'), 'original_hash': report.sha(original),
                       'abi_hash': report.sha(runner_root / 'abi.h')})
    build_root = root / 'roles'
    roles = {}
    for role in 'AB':
        source = root / ('baseline' if kind == 'aa' or role == 'A' else 'candidate')
        data(source / 'op_host' / (op + '.asc'), ('host ' + source.name).encode())
        data(source / 'op_kernel' / 'kernel.h', b'kernel')
        data(source / 'CMakeLists.txt', b'fixture cmake')
        source_hash = build_tool.source_hash(source)
        symbols = [role + '_partial', role + '_final'] if multi else [role + '_kernel']
        generated = data(build_root / role / 'op_host' / (op + '.asc'), ('adapter ' + role).encode())
        patch = data(build_root / (role + '.harness.patch'), b'patch')
        binary = data(build_root / 'build' / ('librole_' + role + '.so'), ('binary ' + role).encode())
        roles[role] = {'role': role, 'operator_name': op, 'source_dir': str(source), 'source_sha256': source_hash,
                       'kernel_symbols': ','.join(symbols), 'binary': binary, 'binary_sha256': report.sha(binary)[7:],
                       'adapter_sha256': report.sha(generated)[7:], 'patch_sha256': report.sha(patch)[7:],
                       'cmake_sha256': report.sha(source / 'CMakeLists.txt')[7:]}
    build = {'version': 'shared_context_build_v1', 'operator': op, 'roles': roles,
             'harness': {'abi.h': report.sha(build_tool.HARNESS / 'abi.h')[7:]}}
    build_path = put(build_root / 'build_manifest.json', build)
    cases = []
    for case in ids:
        directory = root / 'prepared' / str(case)
        inp = data(directory / 'input.bin')
        golden = data(directory / 'golden.bin')
        verifier = data(directory / 'verify_result.py', b'# never executed\n')
        metadata = {'case_id': case, 'dtype': 'float32', 'input': inp, 'golden': golden,
                    'output': str(directory / 'original.bin')}
        if multi:
            metadata.update(lengths=[17, 3], scalar=2)
        else:
            metadata.update(numel=17, base=-1, scale=1, shift=0)
        meta = put(directory / 'metadata.json', metadata)
        cases.append({'case_id': case, 'metadata': meta, 'verifier': verifier})
    request = {'version': report.PRODUCER, 'role_build': build_path, 'runner_build': runner_path, 'profiler_mode': report.MODE,
               'device': 0, 'cpu': 8, 'load_order': 'AB', 'first_order': 'AB', 'buffer_configs': 'normal,swapped', 'cases': cases}
    return request, build


def make_session(root, request, build, number=0, ratio=1.0, task_variation=False, name=None, multi=False):
    directory = root / (name or f'session-{number + 1:02d}')
    directory.mkdir(parents=True)
    put(directory / 'request.json', request)
    original_request = put(root / 'requests' / (directory.name + '.json'), request)
    bindings = {path: report.sha(path) for path in [original_request, request['role_build'], request['runner_build'],
                timing.__file__, report.load(request['runner_build'])['runner']]}
    cases = []
    tsv = []
    for spec in request['cases']:
        meta = report.load(spec['metadata'])
        for path in [spec['metadata'], spec['verifier'], meta['input'], meta['golden']]:
            bindings[path] = report.sha(path)
        case = str(spec['case_id'])
        launches = 4 if multi else 1
        cases.append({'case_id': case, 'launches_per_call': {'A': launches, 'B': launches}})
        command = timing.command_from_metadata(build['roles']['A']['source_dir'], meta, 0, directory / 'unused.bin')[1:]
        tsv.append('\t'.join([case, *command]))
    put(directory / 'bindings.json', bindings)
    put(directory / 'cases.json', cases)
    (directory / 'cases.tsv').write_text('\n'.join(tsv) + '\n')
    records = []
    csv_records = []
    start_time = 1000.0 + number * 1000
    timestamp = Decimal('1234567890123456.001')

    def emit(kind, **fields):
        row = {'session_id': directory.name, 'type': kind, **fields}
        if kind != 'session_end':
            row['timing_protocol'] = report.PRODUCER
        records.append(row)

    def launches(case, role, calls, pair=None, config=None):
        nonlocal timestamp
        symbols = build['roles'][role]['kernel_symbols'].split(',')
        count = 4 if multi else 1
        for _ in range(calls):
            for symbol in symbols * (count // len(symbols)):
                value = ratio(case, config, pair) if callable(ratio) and pair is not None else (ratio if not callable(ratio) else 1)
                duration = 5.0 * (value if role == 'A' else 1)
                if task_variation and pair is not None:
                    duration *= (1.1 if pair % 2 else .9)
                csv_records.append({'Op Name': symbol, 'Task Type': 'AI_VECTOR_CORE', 'Task Start Time(us)': str(timestamp),
                                    'Task Duration(us)': repr(duration), 'Stream ID': '7', 'Task ID': str(len(csv_records)), 'Device_id': '0'})
                timestamp += Decimal('20')

    emit('process_start', pid=number + 300, host='fixture-host', started_at=start_time - .5)
    emit('session_start', pid=number + 300, host='fixture-host', started_at=start_time,
         load_order=request['load_order'], first_order=request['first_order'], context_id='0xc', stream_id='0xs', device=0, vector_cores=48)
    for role in request['load_order']:
        identity = build['roles'][role]
        emit('module', role=role, path=identity['binary'], source_sha256=identity['source_sha256'], kernel_symbols=identity['kernel_symbols'],
             operator_name=build['operator'], entry_address='0xentry' + role)
    time_index = 0
    validations = []
    for case_index, case in enumerate(cases):
        case_id = case['case_id']
        for config in request['buffer_configs'].split(','):
            common = {'case_id': case_id, 'buffer_config': config}
            emit('case_start', **common, case_index=case_index, warmup_per_role=10, pairs=30, repeat=10)
            for role in 'AB':
                other = 'B' if role == 'A' else 'A'
                buffers = []
                for index, kind in enumerate(('input', 'tiling', 'output', 'workspace')):
                    physical = other if config == 'swapped' and kind in ('output', 'workspace') else role
                    buffers.append({'index': index, 'kind': kind, 'bytes': 64, 'address': '0x' + case_id + physical + str(index)})
                emit('resources', **common, role=role, allocation_order='AB', input_policy='separate_identical_files', buffers=buffers)
            for _ in range(10):
                for role in 'AB':
                    launches(case_id, role, 1)
            emit('warmup_complete', **common, calls_per_role=10)
            for pair in range(30):
                order = request['first_order'] if pair % 2 == 0 else request['first_order'][::-1]
                for position, role in enumerate(order):
                    time_index += 1
                    started = start_time + time_index * .01
                    emit('sample', **common, sample_id=f'{directory.name}/{case_id}/{config}/{pair}/{role}', pair_id=pair, role=role,
                         order=order, position=position, started_at=started, ended_at=started + .001,
                         raw_duration=1.0, raw_unit='ms', to_ns=1000000, repeat=10, ns_per_call=100000,
                         launches_per_call=case['launches_per_call'][role], context_id='0xc', stream_id='0xs')
                    launches(case_id, role, 10, pair, config)
            for role in 'AB':
                stem = f'{case_id}_{config}_{role}'
                output = data(directory / 'native' / (stem + '.bin'), b'correct output')
                emit('output', **common, role=role, path=output, validation_scope='final_call_of_final_formal_sample',
                     validation_status='pending_external_oracle', complete_calls_since_prepare=310)
                validations.append({**common, 'role': role, 'passed': True, 'output_hash': report.sha(output)})
                spec = next(row for row in request['cases'] if str(row['case_id']) == case_id)
                meta = report.load(spec['metadata']); meta['output'] = output
                vdir = directory / 'verification' / stem
                mpath = put(vdir / 'metadata.json', meta)
                put(vdir / 'execution.json', {'argv': [sys.executable, spec['verifier'], '--metadata', mpath], 'exit_code': 0,
                                             'started_at': start_time + 101, 'ended_at': start_time + 102, 'mode': 'unchanged_import_safe_main'})
                data(vdir / 'stdout.log', b'correctness passed')
    emit('session_end', exit_code=0, ended_at=start_time + 90, context_destroyed=True, stream_destroyed=True)
    journal = directory / 'native/journal.jsonl'
    journal.write_text(''.join(json.dumps(row) + '\n' for row in records))
    raw = directory / 'raw'; raw.mkdir()
    with (raw / 'op_summary.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(csv_records[0]))
        writer.writeheader(); writer.writerows(csv_records)
    put(directory / 'validation.json', {'scope': 'final_call_of_final_sample_per_case_config_role', 'outputs': validations})
    runner = report.load(request['runner_build'])
    argv = ['taskset', '-c', str(request['cpu']), *timing.profiler_arguments(report.MODE, raw), runner['runner'],
            '--role-a', build['roles']['A']['binary'], '--role-b', build['roles']['B']['binary'],
            '--cases', str(directory / 'cases.tsv'), '--output-dir', str(directory / 'native'), '--session-id', directory.name,
            '--load-order', request['load_order'], '--first-order', request['first_order'], '--buffer-configs', request['buffer_configs'], '--device', '0']
    put(directory / 'msprof.execution.json', {'argv': argv, 'cwd': None, 'exit_code': 0, 'error': None, 'host': 'fixture-host',
                                             'physical_device': '0', 'logical_device': 0, 'started_at': start_time - 1, 'ended_at': start_time + 100})
    for name in ('msprof.stdout.log', 'msprof.stderr.log'):
        data(directory / name)
    for name in ('health-before.json', 'health-after.json'):
        put(directory / name, {'exit_status': 0, 'no_device_processes': True})
    parsed = timing.parse_profile(raw, journal, build, cases, 10)
    put(directory / 'samples.json', parsed)
    put(directory / 'completion.json', {'version': report.PRODUCER, 'status': 'passed', 'error': None, 'formal_admission': 'not_evaluated'})
    return directory


def make_cohort(tmp_path, ids=(1, 8), ratios=None, kind='aa'):
    request, build = setup_inputs(tmp_path, ids=ids, kind=kind)
    directories = []
    plan = {'protocol': report.PROTOCOL, 'analysis_version': report.ANALYSIS, 'comparison_kind': kind,
            'case_ids': list(ids), 'calibration_scope': {'epoch': 'epoch-1', 'CANN': 'fixture'}, 'schedule': []}
    for number, design in enumerate(report.DESIGN):
        req = copy.deepcopy(request)
        req.update(zip(('load_order', 'first_order', 'buffer_configs'), design))
        name = f'session-{number + 1:02d}'
        plan['schedule'].append({'name': name, 'request': req})
        ratio = ratios[number] if ratios else 1
        directories.append(make_session(tmp_path, req, build, number, ratio, name=name))
    return directories, plan


def edit_json(path, change):
    value = report.load(path)
    change(value)
    put(path, value)


def edit_journal(directory, change):
    path = directory / 'native/journal.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    change(rows)
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


def test_plan_fixed_design_has_six_balanced_nonorthogonal_rows(tmp_path):
    request, _ = setup_inputs(tmp_path)
    plan = {'protocol': report.PROTOCOL, 'analysis_version': report.ANALYSIS, 'comparison_kind': 'aa', 'case_ids': [1],
            'calibration_scope': {'epoch': 'e'}, 'schedule': []}
    for number, row in enumerate(report.DESIGN):
        req = {**request, **dict(zip(('load_order', 'first_order', 'buffer_configs'), row))}
        plan['schedule'].append({'name': str(number), 'request': req})
    assert report.validate_plan(plan) == plan
    fit = report.additive_effects([0] * 6)
    assert fit['rank'] == 4 and fit['residual_df'] == 2
    assert all(sum(row[i] for row in fit['design_matrix']) == 0 for i in (1, 2, 3))
    plan['schedule'][2]['request']['first_order'] = 'AB'
    with pytest.raises(ValueError, match='design differs'):
        report.validate_plan(plan)


@pytest.mark.parametrize('multi', [False, True])
def test_read_only_replay_complete_calls_and_output_scope(tmp_path, multi):
    request, build = setup_inputs(tmp_path, multi=multi)
    directory = make_session(tmp_path, request, build, multi=multi)
    before = {str(p): (p.stat().st_mtime_ns, report.sha(p)) for p in tmp_path.rglob('*') if p.is_file()}
    verified = report.verify_observation(directory, request)
    after = {str(p): (p.stat().st_mtime_ns, report.sha(p)) for p in tmp_path.rglob('*') if p.is_file()}
    assert before == after
    assert verified['cells'][0]['roles']['A']['mean_us'] == (20 if multi else 5)
    assert verified['provenance']['oracle_reexecuted'] is False
    assert verified['provenance']['csv_stream_id'] == '7'
    assert report.load(directory / 'samples.json')['samples'][0]['core_us'] is None
    put(directory / 'derived-report.json', {'not_an_input': True})
    assert report.verify_observation(directory, request) == verified


def test_comparison_manifest_attests_separately_built_roles(tmp_path):
    control_request, control = setup_inputs(tmp_path / 'control')
    candidate_request, candidate = setup_inputs(tmp_path / 'candidate', kind='ab')
    composed = {'version': 'shared_context_build_v1', 'operator': 'exp',
                'roles': {'A': control['roles']['A'], 'B': candidate['roles']['B']}, 'harness': control['harness'],
                'component_builds': [{'path': r['role_build'], 'sha256': report.sha(r['role_build'])}
                                     for r in (control_request, candidate_request)]}
    composed_path = put(tmp_path / 'comparison' / 'roles.json', composed)
    request = {**control_request, 'role_build': composed_path}
    directory = make_session(tmp_path / 'measurement', request, composed)
    verified = report.verify_observation(directory, request)
    assert verified['source_hashes']['A'] != verified['source_hashes']['B']
    assert control_request['role_build'] in verified['artifacts']
    assert candidate_request['role_build'] in verified['artifacts']
    edit_json(candidate_request['role_build'], lambda value: value.update(operator='mish'))
    with pytest.raises(ValueError, match='hash differs'):
        report.verify_observation(directory, request)


def test_oracle_argv_contract_comes_from_real_reused_verifier(tmp_path):
    request, build = setup_inputs(tmp_path)
    verifier = Path(request['cases'][0]['verifier'])
    verifier.write_text('''import argparse
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--metadata', required=True)
    metadata = json.loads(Path(parser.parse_args().metadata).read_text())
    assert Path(metadata['output']).read_bytes() == b'correct output'
    print('CPU fixture oracle passed')

if __name__ == '__main__':
    main()
''')
    directory = make_session(tmp_path, request, build)
    execution_path = directory / 'verification/1_normal_A/execution.json'
    metadata_path = execution_path.with_name('metadata.json')
    # Run only this synthetic CPU oracle. The production report never imports
    # or executes an oracle while replaying collected evidence.
    checked = timing.ReusedVerifier(verifier).run(metadata_path)
    assert checked.returncode == 0 and checked.args[0] == sys.executable
    recorded = report.load(execution_path)
    assert recorded['argv'] == checked.args
    recorded['argv'] = checked.args
    put(execution_path, recorded)
    report.verify_observation(directory, request)
    recorded['argv'] = checked.args[1:]
    put(execution_path, recorded)
    with pytest.raises(ValueError, match='oracle execution evidence invalid'):
        report.verify_observation(directory, request)
    recorded['argv'] = ['/bin/false', *checked.args[1:]]
    put(execution_path, recorded)
    with pytest.raises(ValueError, match='oracle execution evidence invalid'):
        report.verify_observation(directory, request)


@pytest.mark.parametrize('corruption', ['whole_config', 'duplicate_module', 'foreign_session', 'context', 'position', 'repeat',
                                      'unit', 'output_calls', 'output_hash', 'oracle_exit', 'oracle_metadata', 'oracle_time',
                                      'resource_alias', 'resource_swap', 'native_exit', 'profiler_exit', 'input_hash', 'samples', 'csv_device'])
def test_invalid_evidence_never_produces_effects(tmp_path, corruption):
    request, build = setup_inputs(tmp_path)
    directory = make_session(tmp_path, request, build)
    if corruption == 'whole_config':
        edit_journal(directory, lambda rows: rows.__setitem__(slice(None), [r for r in rows if r.get('buffer_config') != 'swapped']))
    elif corruption == 'duplicate_module':
        edit_journal(directory, lambda rows: rows.insert(3, dict(rows[2])))
    elif corruption == 'foreign_session':
        edit_journal(directory, lambda rows: rows[10].update(session_id='foreign'))
    elif corruption in ('context', 'position', 'repeat', 'unit'):
        key, value = {'context': ('context_id', '0xother'), 'position': ('position', 9), 'repeat': ('repeat', 1), 'unit': ('to_ns', 1000)}[corruption]
        edit_journal(directory, lambda rows: next(r for r in rows if r['type'] == 'sample').update({key: value}))
    elif corruption == 'output_calls':
        edit_journal(directory, lambda rows: next(r for r in rows if r['type'] == 'output').update(complete_calls_since_prepare=3010))
    elif corruption == 'output_hash':
        data(directory / 'native/1_normal_A.bin', b'changed output')
    elif corruption in ('oracle_exit', 'oracle_metadata', 'oracle_time'):
        if corruption == 'oracle_metadata':
            edit_json(directory / 'verification/1_normal_A/metadata.json', lambda row: row.update(numel=999))
        else:
            edit_json(directory / 'verification/1_normal_A/execution.json', lambda row: row.update({'exit_code': 1} if corruption == 'oracle_exit' else {'started_at': 1000}))
    elif corruption in ('resource_alias', 'resource_swap'):
        def change(rows):
            resource = next(r for r in rows if r['type'] == 'resources' and r['buffer_config'] == 'swapped' and r['role'] == 'A')
            resource['buffers'][2]['address'] = resource['buffers'][0]['address'] if corruption == 'resource_alias' else '0xnot-swapped'
        edit_journal(directory, change)
    elif corruption == 'native_exit':
        edit_journal(directory, lambda rows: rows[-1].update(context_destroyed=False))
    elif corruption == 'profiler_exit':
        edit_json(directory / 'msprof.execution.json', lambda row: row.update(exit_code=1))
    elif corruption == 'input_hash':
        data(tmp_path / 'prepared/1/input.bin', b'changed')
    elif corruption == 'samples':
        edit_json(directory / 'samples.json', lambda row: row['samples'][0].update(task_us=9))
    else:
        path = directory / 'raw/op_summary.csv'
        path.write_text(path.read_text().replace(',0\n', ',1\n'))
    with pytest.raises(ValueError):
        report.verify_observation(directory, request)


def test_six_process_case_suite_and_order_buffer_effects(tmp_path):
    # Opposite case effects average within each process; the six process means
    # have known variation. They cannot become 180 pseudo-independent pairs.
    offsets = [-.01, -.005, 0, 0, .005, .01]
    ratios = [(lambda offset: lambda case, config, pair: math.exp(offset + (.2 if case == '1' else -.2)
               + (.02 if config == 'normal' else -.02) + (.003 if pair % 2 == 0 else -.003)))(x) for x in offsets]
    directories, plan = make_cohort(tmp_path, ratios=ratios)
    result = report.analyze_task_cohort(directories, plan)
    expected = report.effect([value + .02 for value in offsets])
    assert result['suite']['normal']['speedup'] == pytest.approx(math.exp(.02))
    assert result['suite']['normal']['ci95'] == pytest.approx(expected['ci95'])
    assert result['suite']['normal']['n_processes'] == 6
    assert result['suite']['normal']['df'] == 5
    assert not result['suite']['normal']['full_twenty_case_suite']
    assert result['results'][0]['buffer_contrast']['mean_log'] == pytest.approx(.04)
    assert result['results'][0]['additive_factors']['residual_df'] == 2
    assert result['formal_admission'] == 'not_evaluated'
    assert result['graph_policy_eligible'] is False and result['episode_ref'] is None
    assert all('aa_within_half_percent' not in row for row in result['results'])


def test_missing_entire_case_config_rejected_even_when_old_summarizer_accepts(tmp_path):
    directories, plan = make_cohort(tmp_path)
    path = directories[-1] / 'samples.json'
    edit_json(path, lambda value: value.update(samples=[row for row in value['samples'] if not (row['case_id'] == '8' and row['buffer_config'] == 'swapped')]))
    old = timing.summarize(directories)
    assert next(row for row in old['results'] if (row['case_id'], row['buffer_config'], row['metric']) == ('8', 'swapped', 'task_us'))['n_processes'] == 5
    with pytest.raises(ValueError, match='CSV/journal replay'):
        report.analyze_task_cohort(directories, plan)


def test_rejects_copied_native_process_identity_and_missing_process(tmp_path):
    directories, plan = make_cohort(tmp_path, ids=(1,))
    def duplicate(rows):
        rows[0].update(pid=300, started_at=999.5)
        rows[1].update(pid=300, started_at=1000)
    edit_journal(directories[1], duplicate)
    edit_json(directories[1] / 'msprof.execution.json', lambda row: row.update(started_at=999))
    with pytest.raises(ValueError, match='duplicate native process identity'):
        report.analyze_task_cohort(directories, plan)
    with pytest.raises(ValueError, match='exactly six observed'):
        report.analyze_task_cohort(directories[:-1], plan)


@pytest.mark.parametrize('lo,hi,status', [(-report.TOL, report.TOL, 'equivalent'),
                                        (-report.TOL - 1e-8, report.TOL, 'precision_insufficient'),
                                        (-.1, .1, 'precision_insufficient'), (.03, .04, 'observed_bias')])
def test_log_symmetric_two_percent_boundary(lo, hi, status):
    assert report.equivalence({'log_ci95': [lo, hi]}) == status


def test_additive_adjusted_two_level_contrasts_and_uncovered_interactions():
    x = report.additive_effects([0] * 6)['design_matrix']
    beta = [0.1, .02, -.03, .04]
    logs = [sum(a * b for a, b in zip(row, beta)) for row in x]
    fit = report.additive_effects(logs)
    assert fit['coefficients'] == pytest.approx(beta)
    assert [fit['contrasts'][key]['mean_log'] for key in ('load_order', 'first_order', 'config_execution_order')] == pytest.approx([.04, -.06, .08])
    assert fit['interaction_control'] == fit['independent_loading_control'] == 'not_covered'
    assert all(value['df'] == 2 for value in fit['contrasts'].values())
    residual = [.01, -.01, -.01, .01, 0, 0]  # Orthogonal to all four design columns.
    noisy = report.additive_effects([a + b for a, b in zip(logs, residual)])
    contrast = noisy['contrasts']['load_order']
    # SSE=.0004, residual variance=.0002, inverse Gram diagonal=.25;
    # the two-level contrast multiplies the coefficient standard error by 2.
    expected_se = math.sqrt(.0002)
    assert contrast['standard_error'] == pytest.approx(expected_se)
    assert contrast['log_ci95'] == pytest.approx([.04 - report.T2 * expected_se, .04 + report.T2 * expected_se])


def test_calibration_reuse_scope_and_caution_do_not_stop_analysis(tmp_path):
    directories, plan = make_cohort(tmp_path, ids=(1,))
    calibration = json.loads(json.dumps(report.analyze_task_cohort(directories, plan)))
    plan['comparison_kind'] = 'ab'
    measured = report.analyze_task_cohort(directories, plan, calibration)
    assert all(r['calibration_status'] == 'applicable' for r in measured['results'])
    assert all(r['coarse_observed_controls'] == 'within_limits' for r in measured['results'])
    assert all(r['measurement_quality'] == 'complete_with_caution' and not r['qualified_performance_eligible'] for r in measured['results'])
    plan['calibration_scope']['epoch'] = 'changed'
    changed = report.analyze_task_cohort(directories, plan, calibration)
    assert all(r['calibration_status'] == 'invalidated' for r in changed['results'])
    assert changed['evidence_status'] == 'verified_complete'


def test_scope_environment_pointer_is_verified_and_bound(tmp_path):
    directories, plan = make_cohort(tmp_path, ids=(1,))
    environment = put(tmp_path / 'environment.json', {'cann_version': 'fixture-v1'})
    plan['calibration_scope']['environment'] = {'path': environment, 'sha256': report.sha(environment)}
    result = report.analyze_task_cohort(directories, plan)
    assert result['calibration_scope_artifacts'] == {environment: report.sha(environment)}
    put(environment, {'cann_version': 'changed'})
    with pytest.raises(ValueError, match='dependency pointer hash differs'):
        report.analyze_task_cohort(directories, plan)


def test_small_change_requires_precision_and_high_cv_is_usable_observation(tmp_path):
    directories, plan = make_cohort(tmp_path, ids=(1,), ratios=[1.02] * 6)
    plan['comparison_kind'] = 'ab'
    result = report.analyze_task_cohort(directories, plan)
    assert all(row['claim_status'] == 'needs_precision' for row in result['results'])
    assert all(row['calibration_status'] == 'not_covered' for row in result['results'])
    request, build = setup_inputs(tmp_path / 'variable')
    directory = make_session(tmp_path / 'variable', request, build, task_variation=True)
    assert report.verify_observation(directory)['cells'][0]['roles']['A']['cv'] > .05


@pytest.mark.parametrize('path', ['runner/runner', 'runner/runner.cpp', 'runner/abi.h', 'runner/harness.patch',
                                'roles/build/librole_B.so', 'roles/A/op_host/exp.asc', 'roles/A.harness.patch',
                                'baseline/op_kernel/kernel.h', 'baseline/CMakeLists.txt'])
def test_changed_bound_build_dependency_is_rejected(tmp_path, path):
    request, build = setup_inputs(tmp_path)
    directory = make_session(tmp_path, request, build)
    data(tmp_path / path, b'changed dependency')
    with pytest.raises(ValueError):
        report.verify_observation(directory)


def test_no_relabeling_ab_as_same_source_aa(tmp_path):
    directories, plan = make_cohort(tmp_path, ids=(1,), kind='ab')
    plan['comparison_kind'] = 'aa'
    with pytest.raises(ValueError, match='A/A role source hashes differ'):
        report.analyze_task_cohort(directories, plan)


def test_json_duplicate_keys_and_nonfinite_rejected(tmp_path):
    for payload in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}'):
        path = tmp_path / 'bad.json'; path.write_text(payload)
        with pytest.raises(ValueError):
            report.load(path)


def test_generated_msprof_runner_with_fake_acl_has_310_calls(tmp_path):
    if not shutil.which('g++'):
        pytest.skip('g++ unavailable')
    # Import fixture constants only; do not invoke the native test module's
    # AdapterTests, which enumerate repository operators.
    spec = importlib.util.spec_from_file_location('fake_acl_fixtures', ROOT / 'tests/test_shared_context_native.py')
    fixtures = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixtures)
    data(tmp_path / 'acl/acl.h', fixtures.FAKE_ACL.encode())
    data(tmp_path / 'role.cpp', fixtures.FAKE_ROLE.encode())
    harness = ROOT / 'benchmarks/cannbench/harness/shared_context'
    generated = data(tmp_path / 'runner.cpp', timing.instrument((harness / 'runner.cpp').read_text(), 10).encode())
    subprocess.run(['g++', '-std=c++17', '-I' + str(tmp_path), '-I' + str(harness), generated, '-ldl', '-o', str(tmp_path / 'runner')], check=True, capture_output=True)
    for role in 'AB':
        subprocess.run(['g++', '-std=c++17', '-shared', '-fPIC', '-Wl,-Bsymbolic', '-I' + str(harness), '-DROLE="' + role + '"', str(tmp_path / 'role.cpp'), '-o', str(tmp_path / (role + '.so'))], check=True, capture_output=True)
    (tmp_path / 'cases.tsv').write_text('1\t--numel\t1\n')
    import os
    process = subprocess.run([str(tmp_path / 'runner'), '--role-a', str(tmp_path / 'A.so'), '--role-b', str(tmp_path / 'B.so'),
                              '--cases', str(tmp_path / 'cases.tsv'), '--output-dir', str(tmp_path / 'native'), '--session-id', 'fake',
                              '--load-order', 'BA', '--first-order', 'BA', '--buffer-configs', 'swapped,normal'],
                             env={**os.environ, 'FAKE_ACL_LOG': str(tmp_path / 'acl.log'), 'APROF_MSPROF_HOST_DELAY_A_US': '0', 'APROF_MSPROF_HOST_DELAY_B_US': '0'},
                             capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    assert (tmp_path / 'acl.log').read_text().splitlines() == ['init', 'context_create', 'stream_create', 'stream_destroy', 'context_destroy', 'finalize']
    records = [json.loads(line) for line in (tmp_path / 'native/journal.jsonl').read_text().splitlines()]
    samples = [row for row in records if row['type'] == 'sample']
    assert len(samples) == 120
    assert all(row['repeat'] == 10 and row['ns_per_call'] == pytest.approx(10000, rel=1e-6) for row in samples)
    for config in ('normal', 'swapped'):
        for role in 'AB':
            assert (tmp_path / 'native' / f'1_{config}_{role}.bin').read_text() == '310'
    resources = [row for row in records if row['type'] == 'resources']
    by_key = {(row['buffer_config'], row['role'], b['kind']): b['address'] for row in resources for b in row['buffers']}
    for role in 'AB':
        other = 'B' if role == 'A' else 'A'
        for kind in ('input', 'tiling'):
            assert by_key['normal', role, kind] == by_key['swapped', role, kind]
        for kind in ('output', 'workspace'):
            assert by_key['normal', role, kind] == by_key['swapped', other, kind]
