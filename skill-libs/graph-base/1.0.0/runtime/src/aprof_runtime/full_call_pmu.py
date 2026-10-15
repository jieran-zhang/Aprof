"""Full ordered-callback PMU replay. No collector, gate math, or publication grant."""
from decimal import Decimal, InvalidOperation
import json
import csv
import io
import re
import math
from pathlib import PurePosixPath
import shlex
import statistics
import struct
import configparser

from .errors import ContractError
from .jsonio import to_primitive
from .measurement_admission import _number as number, _require as require
from .profile_evidence import _load, _object, MIN_CAPTURES, MIN_WARMUPS, MAX_PROFILE_CV
from .task_timing import _tasks
from .task_window_timing import case_task_config
from .task_window_measurement_admission import PROFILE_DEPENDENCY_PATHS as TASK_DEPENDENCIES, SUMMARY_PYTHON, replay_task_budget, replay_collection_unit

PROTOCOL = 'full_call_pmu_v1'
KIND = 'full_call_pmu_mechanism'
TOOL = '/usr/local/Ascend/cann-9.0.0/tools/profiler/bin/msprof'
NPU_SMI = '/usr/local/sbin/npu-smi'
_ANALYSIS = '/usr/local/Ascend/cann-9.0.0/tools/profiler/profiler_tool/analysis/'
PROFILE_DEPENDENCY_PATHS = (*TASK_DEPENDENCIES, NPU_SMI, *(_ANALYSIS + name for name in (
    'msconfig/msprof_export_data_config.py', 'msconfig/prof_header_mapping.json',
    'msconfig/filename_introduction_config.py', 'common_func/msvp_common.py',
    'common_func/platform/ai_core_metrics_manager.py',
    'profiling_bean/struct_info/lpm_info_bean.py', 'msparser/lpm_info/lpm_info_parser.py',
    'msparser/data_struct_size_constant.py', 'common_func/info_conf_reader.py',
    'profiling_bean/basic_info/host_start.py', 'mscalculate/stars/ffts_pmu_calculator.py')))
FLAGS = ('--task-time=l1', '--ai-core=on', '--aic-mode=task-based',
         '--aic-metrics=PipeUtilization', '--ascendcl=off', '--runtime-api=off',
         '--ge-api=off', '--aicpu=off', '--type=text', '--python-path=' + SUMMARY_PYTHON)
ROLES = ('baseline', 'candidate')

PMU_FIELDS = {'aicore_time(us)': 'us', 'aiv_time(us)': 'us', 'icache_miss_rate': 'ratio',
              **{name+'_time(us)': 'us' for name in ('vec','mac','scalar','mte1','mte2','mte3','fixpipe')},
              **{name+'_ratio': 'ratio' for name in ('vec','mac','scalar','mte1','mte2','mte3','fixpipe')}}
# CANN 9 whole-app PipeUtilization exports core-specific column names.
for _core, _pipes in {'aic': ('mac', 'scalar', 'mte1', 'mte2', 'fixpipe'),
                      'aiv': ('vec', 'scalar', 'mte2', 'mte3')}.items():
    PMU_FIELDS[_core + '_icache_miss_rate'] = 'ratio'
    for _pipe in _pipes:
        PMU_FIELDS[_core + '_' + _pipe + '_time(us)'] = 'us'
        PMU_FIELDS[_core + '_' + _pipe + '_ratio'] = 'ratio'


def _capture_statistics(values):
    # Match the frozen profile_evidence sample-CV definition exactly.
    cv = None
    if len(values) >= 2:
        mean = statistics.fmean(values)
        dev = statistics.stdev(values)
        cv = dev / abs(mean) if mean else (0.0 if not dev else None)
    return dict(status='known' if cv is not None else 'unknown', capture_values=values,
        median=statistics.median(values), cv=cv,
        stable=len(values)>=MIN_CAPTURES and cv is not None and cv<=MAX_PROFILE_CV)


def partition_call(csv_text, *, scope, role):
    """Retain all repeated kernels and join PMU cells to exact Task row identity."""
    require(role in ROLES and scope['protocol'] in (PROTOCOL, 'baseline_full_call_pmu_v1'), 'unknown PMU callback scope')
    names = scope['role_kernel_names'][role]
    require(len(names) == scope['launches_per_call'][role], 'PMU callback count differs')
    rows, tasks, auxiliary = _tasks(csv_text, {'device': scope['device']}, scope['role_kernel_names'])
    require(not auxiliary and len(rows) == len(tasks) == len(names)
            and [task['op_name'] for task in tasks] == names,
            'PMU export is not the complete ordered callback')
    occurrences, grouped = [], {}
    for position, task in enumerate(tasks):
        cells = {}
        for metric, spec in scope['metrics'].items():
            raw = rows[task['csv_row_index']].get(spec['field'])
            try:
                value = Decimal(raw.strip())
                valid = value.is_finite() and value >= 0 and math.isfinite(float(value))
            except (AttributeError, InvalidOperation, ValueError, OverflowError):
                valid = False
            cells[metric] = ({'status': 'known', 'value_decimal': str(value)} if valid else
                             {'status': 'unknown', 'reason': 'absent_or_nonfinite_PMU_cell', 'raw': raw})
        item = dict(position=position, csv_row_index=task['csv_row_index'], kernel=task['op_name'],
            task_type=task['task_type'], device=task['device'], stream=task['stream'], task_id=task['task_id'],
            start_us_decimal=str(task['start_us']), task_duration_us_decimal=str(task['duration_us']), metrics=cells)
        occurrences.append(item)
        grouped.setdefault(item['kernel'], []).append(item)
    kernels = {}
    for name, items in grouped.items():
        metrics = {}
        for metric in scope['metrics']:
            values = [item['metrics'][metric] for item in items]
            metrics[metric] = ({'status': 'known', 'median_decimal': str(statistics.median(
                [Decimal(value['value_decimal']) for value in values]))}
                if all(value['status'] == 'known' for value in values) else {'status': 'unknown'})
        kernels[name] = dict(positions=[item['position'] for item in items], count=len(items), metrics=metrics)
    return dict(task_count=len(tasks), occurrences=occurrences, kernels=kernels,
                pmu_complete=all(cell['status']=='known' for item in occurrences for cell in item['metrics'].values()))


def _table(files):
    paths = [PurePosixPath(name) for name in files]
    require(paths and all(not p.is_absolute() and p.as_posix()==name and '..' not in p.parts
            and '.' not in p.parts for p,name in zip(paths,files)), 'unsafe PMU profile path')
    roots = {p.parts[0] for p in paths}
    require(len(roots)==1 and next(iter(roots)).startswith('PROF_'), 'PMU requires one full PROF tree')
    require(all(not any(parent.as_posix() in files for parent in p.parents if parent.as_posix()!='.')
                for p in paths), 'PMU files collide with ancestor paths')
    tables = [name for name in files if PurePosixPath(name).match('op_summary*.csv')]
    require(len(tables)==1, 'PMU requires exactly one complete op_summary CSV')
    return tables[0]


def capture_argv(command, raw):
    return [TOOL, '--output=' + str(raw), *FLAGS, '--application=' + shlex.join(command)]


def _keys(value, names, label):
    require(isinstance(value, dict) and set(value) == set(names.split()), label + ' fields differ')


def _native(reader, reference):
    # Only original oracle results may contain native JSON Infinity/NaN.
    return json.loads(reader.verify_artifact(reference).read_text(), object_pairs_hook=_object)


def _native_equal(a, b):
    return json.dumps(a, sort_keys=True, allow_nan=True) == json.dumps(b, sort_keys=True, allow_nan=True)


def _source(reader, reference):
    bundle = _load(reader, reference)
    _keys(bundle, 'schema_version files', 'source bundle')
    require(bundle['schema_version'] == '1.0.0' and isinstance(bundle['files'], dict)
            and bundle['files'], 'source bundle schema differs')
    for name, ref in bundle['files'].items():
        path = PurePosixPath(name)
        require(not path.is_absolute() and name != '.' and str(path) == name and '..' not in path.parts,
                'source bundle path differs')
        reader.verify_artifact(ref)


def _scope(config, case_id, metrics):
    selected = case_task_config(config, case_id)
    require(isinstance(metrics, dict) and metrics, 'full-call PMU metrics missing')
    for name, spec in metrics.items():
        _keys(spec, 'unit file format field row_aggregation aggregation', 'metric')
        require(isinstance(name, str) and name and spec['file'] == 'op_summary*.csv'
            and spec['format'] == 'csv' and spec['field'] in PMU_FIELDS
            and spec['unit'] == PMU_FIELDS[spec['field']]
            and spec['row_aggregation'] == spec['aggregation'] == 'median',
            'PMU field/unit/reducer differs; Task or metadata is not PMU')
    return dict(protocol=PROTOCOL, case_id=case_id, device=config['device'],
        role_kernel_names=selected['task_profile']['role_kernel_names'],
        launches_per_call={r:selected['roles'][r]['launches_per_operator'] for r in ROLES},
        metrics=metrics, warmups=MIN_WARMUPS, captures=MIN_CAPTURES, flags=list(FLAGS),
        occurrence_scope='all_ordered_tasks_in_one_complete_callback',
        within_kernel='median_of_all_occurrences', across_captures='median', maximum_cv=MAX_PROFILE_CV)


def _execution(reader, reference, argv, cwd, identity, previous, finish, deadline, seen, *, timeout_cap=3600):
    require(reference not in seen, 'independent PMU executions cannot reuse a receipt')
    seen.add(reference)
    record = _load(reader, reference)
    require(record['argv'] == argv and record['cwd'] == cwd
        and type(record['exit_code']) is int and record['exit_code'] == 0 and record['error'] is None
        and record.get('environment') == {} and type(record.get('pid')) is int and record['pid'] > 0
        and previous <= number(record['started_at']) < number(record['ended_at']) <= finish
        and 0 < number(record['timeout_seconds']) <= number(timeout_cap)
        and record['ended_at'] - record['started_at'] <= record['timeout_seconds']
        and record['started_at'] + record['timeout_seconds'] <= deadline + .01,
        'PMU actual command/exit/chronology/deadline differs')
    if identity is not None:
        require(record.get('identity_checks') == {'before':identity, 'after':identity},
                'PMU source/binary/tool identity differs')
    for key in ('stdout_hash', 'stderr_hash'):
        reader.verify_artifact(record[key])
    return record


def _reduce(partitions, scope):
    metrics = {}
    for role, captures in partitions.items():
        metrics[role] = {}
        for kernel in captures[0]['kernels']:
            metrics[role][kernel] = {}
            for metric in scope['metrics']:
                cells = [p['kernels'][kernel]['metrics'][metric] for p in captures]
                metrics[role][kernel][metric] = ({'status':'unknown'}
                    if any(c['status'] == 'unknown' for c in cells) else
                    _capture_statistics([float(Decimal(c['median_decimal'])) for c in cells]))
    return metrics



def slot_receipt_value(reader, item, *, plan_ref, completion_ref, scope, prepared_files,
                       outputs_before_oracle, outputs_after_oracle, finalized_at):
    """Pure value for an exclusive collector-finalized receipt after original oracle.

    The collector snapshots outputs before launching the oracle and again after
    it exits; this function never substitutes current bytes for that first read.
    """
    return dict(schema_version=1, kind='full_call_pmu_slot', protocol=scope['protocol'],
        plan_ref=plan_ref, measurement_admission_ref=completion_ref, scope=scope,
        role=item['role'], index=item['index'], directory=item['directory'],
        capture_execution_ref=item['execution_ref'], capture=_load(reader,item['execution_ref']),
        profile_files_ref=item['profile_files_ref'], profile_files=_load(reader,item['profile_files_ref']),
        table_ref=item['table_ref'], prepared_files=prepared_files,
        outputs_before_oracle=outputs_before_oracle, outputs_after_oracle=outputs_after_oracle,
        oracle_execution_ref=item['oracle_execution_ref'], oracle=_load(reader,item['oracle_execution_ref']),
        oracle_result_ref=item['oracle_result_ref'], finalized_at=finalized_at,
        **({'collection_unit_ref': item['collection_unit_ref']} if 'collection_unit_ref' in item else {}))



def _dispatcher_value(reader, reference):
    # Baseline dispatcher uses digests; whole-trial supervisor uses path/hash
    # pointers. Original absolute paths remain identity metadata after archive.
    if isinstance(reference, dict):
        _keys(reference,'path sha256','dispatcher pointer')
        path=PurePosixPath(reference['path'])
        require(path.is_absolute() and str(path)==reference['path'] and '..' not in path.parts,
                'dispatcher pointer path differs')
        reference=reference['sha256']
    require(isinstance(reference,str),'dispatcher artifact reference differs')
    return _load(reader,reference)

def _original_window(reader, plan, evidence, completion, config, identity, *, budget_binding=None):
    require(plan['launch_ref'] == evidence.artifacts.get('task_launch')
        and plan['build_window_ref'] == evidence.artifacts.get('build_window'),
        'PMU must bind the original dispatcher and actual build windows')
    launch=_load(reader,plan['launch_ref'])
    _keys(launch,'attempt_ref started_at started_monotonic deadline_monotonic issued_monotonic child_timeout_seconds','dispatcher launch')
    attempt=_dispatcher_value(reader,launch['attempt_ref']); origin=_dispatcher_value(reader,attempt['plan_ref'])
    job=_dispatcher_value(reader,origin['job_ref'])
    total=3600
    if budget_binding is not None:
        require(budget_binding['launch_ref']==plan['launch_ref'], 'PMU budget replaced the Task original launch')
        total=replay_task_budget(reader,budget_binding,expected=config)['budget_seconds']
    require(number(attempt['budget_seconds'])==total and origin['run_id']==config['run_id']
        and number(job['timeout_seconds'])==total and number(attempt['created_at'])<=number(launch['started_at'])
        and number(launch['deadline_monotonic'])==number(launch['started_monotonic'])+total
        and launch['started_monotonic']<=number(launch['issued_monotonic'])<launch['deadline_monotonic']
        and number(launch['child_timeout_seconds'])==launch['deadline_monotonic']-launch['issued_monotonic']
        and plan['deadline_monotonic']==launch['deadline_monotonic'],
        'PMU reset the original registered dispatcher deadline')
    build=_load(reader,plan['build_window_ref'])
    require(build.get('kind') in ('reviewed_candidate_build','original_baseline_build')
        and build['deadline_monotonic']==launch['deadline_monotonic']
        and launch['started_at']<=number(build['started_at'])<=number(build['finished_at'])<=completion['started_at']
        and launch['started_monotonic']<=number(build['started_monotonic'])<=number(build['finished_monotonic'])<=launch['deadline_monotonic'],
        'build did not use the original task budget before formal measurement')
    receipt_ref=build.get('receipt_ref',plan['build_window_ref'])
    require(receipt_ref in identity['build']['receipt_refs'].values(),'build window is not the Task registered build')
    receipt=_load(reader,receipt_ref)
    require(receipt.get('status')=='passed' and receipt.get('error') is None
        and receipt['binary']['sha256']==identity['build']['binary_ref'], 'actual build failed or changed binary')
    build_plan=_load(reader,build['plan_ref'])
    require(build_plan['source_hashes']==plan['source_hashes']
        and build_plan.get('deadline_monotonic',launch['deadline_monotonic'])==launch['deadline_monotonic'], 'build plan reset deadline or source')
    wall_deadline=number(launch['started_at'])+attempt['budget_seconds']
    require(launch['started_at']<=plan['created_at']<=completion['started_at']<completion['finished_at']<=wall_deadline,
        'Task completion is outside original task window')
    return launch,wall_deadline,receipt_ref


def _lpm_frequency_basis(reader, files, scope, role):
    """Join genuine CANN 9 LPM frequency changes to each complete Task interval.

    Mirror the SDK LpmInfoDataBean and InfoConfReader clock conversion. Static
    info.json frequency is SDK metadata, never a sampled current value.
    The SDK uses this same LPM series for AIC and AIV PMU cycle conversion.
    """
    table = _table(files)
    root = PurePosixPath(table).parts[0] + '/device_' + str(scope['device']) + '/'
    raw = sorted(name for name in files if re.fullmatch(
        re.escape(root) + r'data/lpmInfoConv\.data\.\d+\.slice_\d+', name))
    if not raw:
        return None
    def one(pattern):
        matches = [name for name in files if re.fullmatch(re.escape(root) + pattern, name)]
        require(len(matches) <= 1, 'ambiguous raw LPM clock basis')
        return reader.verify_artifact(files[matches[0]]) if matches else None
    info, dev, host, start, end = [one(pattern) for pattern in (
        r'info\.json\.\d+', r'dev_start\.log\.\d+', r'host_start\.log\.\d+',
        r'start_info\.\d+', r'end_info\.\d+')]
    if any(path is None for path in (info, dev, host, start, end)):
        return None
    info = json.loads(info.read_text()); start = json.loads(start.read_text()); end = json.loads(end.read_text())
    devices = [item for item in info['DeviceInfo'] if str(item['id']) == str(scope['device'])]
    require(len(devices) == 1 and devices[0]['ctrl_cpu_endian_little'] == 1,
            'LPM device or byte order differs')
    device = devices[0]; hwts = Decimal(device['hwts_frequency'])
    require(hwts.is_finite() and hwts > 0, 'invalid LPM clock frequency')
    counts = re.findall(r'^cntvct:\s*(\d+)\s*$', dev.read_text(), re.MULTILINE)
    require(len(counts) == 1, 'invalid LPM device clock anchor')
    config = configparser.ConfigParser(); config.read_string(host.read_text())
    require(config.sections() == ['Device' + str(scope['device'])], 'LPM host clock device differs')
    host_values = config[config.sections()[0]]
    # Nonzero host correction requires a separate qualified conversion basis.
    if int(host_values.get('cntvct_diff', '0')) != 0:
        return None
    begin = Decimal(start['collectionTimeBegin']); finish = Decimal(end['collectionTimeEnd'])
    origin = begin + (Decimal(host_values['clock_monotonic_raw']) - Decimal(start['clockMonotonicRaw'])) / 1000
    require(all(x.is_finite() for x in (begin, finish, origin)) and 0 < begin <= finish,
            'invalid LPM capture window')
    events = {}; fmt = '<II' + 'QII' * 55; size = struct.calcsize(fmt)
    for name in raw:
        data = reader.verify_artifact(files[name]).read_bytes()
        require(data and len(data) % size == 0, 'truncated LPM binary')
        for offset in range(0, len(data), size):
            row = struct.unpack_from(fmt, data, offset); count, kind = row[:2]
            require(0 <= count <= 55 and kind in (0, 1, 2), 'invalid LPM record type/count')
            if kind != 0:
                continue
            for i in range(count):
                ticks, mhz, _ = row[2+3*i:5+3*i]
                require(ticks > 0 and mhz > 0 and (ticks not in events or events[ticks] == mhz),
                        'invalid or contradictory raw LPM frequency')
                events[ticks] = mhz
    if not events:
        return None
    changes = [(origin + (Decimal(ticks) - Decimal(counts[0])) / hwts, mhz)
               for ticks, mhz in sorted(events.items())]
    partition = partition_call(reader.verify_artifact(files[table]).read_text(), scope=scope, role=role)
    result = {}
    for task in partition['occurrences']:
        first = Decimal(task['start_us_decimal']); last = first + Decimal(task['task_duration_us_decimal'])
        require(begin <= first <= last <= finish, 'Task falls outside raw LPM collection window')
        previous = [mhz for at, mhz in changes if at <= first]
        if not previous:
            return None
        current = previous[-1]
        if any(mhz != current for at, mhz in changes if first < at <= last):
            return None
        kind = task['task_type']
        if kind not in ('AI_VECTOR_CORE', 'AI_CORE', 'MIX_AIC', 'MIX_AIV'):
            return None
        reported = float(device['aiv_frequency' if kind in ('AI_VECTOR_CORE', 'MIX_AIV') else 'aic_frequency'])
        require(math.isfinite(reported) and reported > 0, 'invalid SDK frequency metadata')
        value = dict(device=str(scope['device']), op_type=kind, frequencies=[float(current)],
                     sdk_reported_frequency=reported, basis='raw_lpm_current_frequency_v1')
        name = task['kernel']
        if name in result and result[name] != value:
            return None
        result[name] = value
    return result


def _frequency_basis(reader,files,scope,role):
    # Whole-app exports lacking the established raw field basis stay unknown.
    basics=[ref for name,ref in files.items() if re.fullmatch(r'OpBasicInfo(?:_\d+)?\.csv',PurePosixPath(name).name)]
    if not basics:return _lpm_frequency_basis(reader,files,scope,role)
    require(len(basics)==1,'ambiguous whole-call raw frequency basis')
    table=csv.DictReader(io.StringIO(reader.verify_artifact(basics[0]).read_text(encoding='utf-8-sig')))
    headers=table.fieldnames or [];rows=list(table)
    require(rows and len(headers)==len(set(headers)) and all(None not in row and None not in row.values() for row in rows),
        'malformed raw frequency table')
    if not {'Op Name','Device Id','Current Freq','Rated Freq'}<=set(headers):return None
    require([r['Op Name'] for r in rows]==scope['role_kernel_names'][role], 'frequency rows omit or reorder complete callback')
    result={}
    for row in rows:
        require(row['Device Id']==str(scope['device']),'raw frequency device differs')
        frequencies=[float(row[k]) for k in ('Current Freq','Rated Freq')]
        require(all(math.isfinite(x) and x>0 for x in frequencies),'invalid raw device frequency')
        value=dict(device=row['Device Id'],op_type=row.get('Op Type'),frequencies=frequencies)
        name=row['Op Name']
        require(name not in result or result[name]==value,'raw frequency differs across kernel occurrences')
        result[name]=value
    return result

def replay_full_call_mechanism(reader, report, *, evidence, source_hashes):
    """Read raw Task/PMU evidence. Outer controller still owns review/exit/budget joins."""
    try:
        return _replay(reader, report, evidence=evidence, source_hashes=source_hashes)
    except ContractError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, OSError, ArithmeticError) as exc:
        raise ContractError('full-call PMU: malformed or missing evidence: ' + str(exc)) from exc


def _replay(reader, report, *, evidence, source_hashes):
    from .measurement_entry import replay_current_measurement_admission
    _keys(report, 'schema_version kind protocol candidate_id hypothesis_basis plan_ref measurement_admission_ref capture_report_ref',
          'full-call mechanism')
    require(report['schema_version'] == '1.0.0' and report['kind'] == KIND and report['protocol'] == PROTOCOL
        and report['candidate_id'] == evidence.candidate_id
        and report['hypothesis_basis'] in ('user','heuristic','manual','measured'), 'full-call mechanism identity differs')
    require(source_hashes is not None, 'full-call PMU requires both authoritative source roles')
    sources = to_primitive(source_hashes)
    require(set(sources) == set(ROLES), 'PMU source role scope differs')
    for ref in sources.values():
        _source(reader, ref)
    require(report['measurement_admission_ref'] == evidence.artifacts.get('measurement_admission')
        and report['plan_ref'] == evidence.artifacts.get('mechanism_plan'),
        'PMU must bind the gate Task completion and frozen mechanism plan')
    task = replay_current_measurement_admission(reader, report['measurement_admission_ref'], expected={
        'candidate_id':evidence.candidate_id, 'source_hashes':sources,
        'measurement_report_ref':evidence.artifacts.get('measurement_report')})
    require(task['valid'] is True, 'Task completion replay failed')
    completion = _load(reader, report['measurement_admission_ref'])
    config = _load(reader, task['config_ref'])
    registration = _load(reader, task['registration_ref'])
    identity = registration['identity']
    plan = _load(reader, report['plan_ref'])
    _keys(plan, 'schema_version kind protocol candidate_id config_ref source_hashes created_at deadline_monotonic scope selections toolchain_refs launch_ref build_window_ref', 'PMU plan')
    require(plan['schema_version'] == 1 and plan['kind'] == 'full_call_pmu_plan' and plan['protocol'] == PROTOCOL
        and plan['candidate_id'] == evidence.candidate_id and plan['config_ref'] == task['config_ref']
        and plan['source_hashes'] == sources == identity['source_hashes']
        and number(plan['created_at']) <= completion['started_at'], 'PMU plan was not frozen for this Task/source')
    storage=_load(reader,registration['profile_storage_ref']) if 'profile_storage_ref' in registration else {}
    launch,original_wall_deadline,build_receipt_ref = _original_window(reader,plan,evidence,completion,config,identity,
        budget_binding=storage.get('budget_binding'))
    original_budget=launch['deadline_monotonic']-launch['started_monotonic']
    policy=(replay_task_budget(reader,storage['budget_binding'],expected=config)['collection_stop_policy']
            if 'budget_binding' in storage else None)
    scope = _scope(config, plan['scope']['case_id'], plan['scope']['metrics'])
    require(plan['scope'] == scope, 'PMU full callback scope differs from Task config')
    case = next(c for c in config['cases'] if c['case_id'] == scope['case_id'])
    bound = identity['cases'][str(scope['case_id'])]
    require(_load(reader, bound['workload_ref']) == case['workload'], 'PMU workload differs')
    for group in ('prepared_files','verifier_files'):
        for ref in bound[group].values(): reader.verify_artifact(ref)
    binary_ref = identity['build']['binary_ref']; reader.verify_artifact(binary_ref)
    tools = plan['toolchain_refs']
    require(set(tools) == set(PROFILE_DEPENDENCY_PATHS), 'PMU SDK dependency scope differs')
    require(all(tools[p] == ref for p, ref in registration['profile_dependency_refs'].items())
        and tools[NPU_SMI] == task['hardware']['npu_smi_ref'], 'PMU uses a different Task SDK/device tool')
    for ref in tools.values(): reader.verify_artifact(ref)
    selections = plan['selections']
    require(isinstance(selections, list) and selections, 'named-kernel hypothesis selection missing')
    selected = set()
    for choice in selections:
        _keys(choice, 'name kernel unit expected_direction', 'PMU selection')
        key = (choice['name'], choice['kernel'])
        require(key not in selected and choice['name'] in scope['metrics']
            and choice['unit'] == scope['metrics'][choice['name']]['unit']
            and choice['expected_direction'] in ('increase','decrease')
            and all('aprof_' + r + '_' + choice['kernel'] in scope['role_kernel_names'][r] for r in ROLES),
            'selected metric/kernel/unit/direction is unbound or duplicated')
        selected.add(key)
    capture = _load(reader, report['capture_report_ref'])
    _keys(capture, 'schema_version protocol plan_ref measurement_admission_ref build_receipt_ref scope directory started_at started_monotonic deadline_monotonic warmups captures status error qualification_passed admission_authority archive_performed capabilities_ref hardware_ref finished_at finished_monotonic', 'PMU capture report')
    start, finish = number(capture['started_at']), number(capture['finished_at'])
    begin, end, deadline = (number(capture[k]) for k in ('started_monotonic','finished_monotonic','deadline_monotonic'))
    require(capture['schema_version'] == 1 and capture['protocol'] == PROTOCOL
        and capture['plan_ref'] == report['plan_ref'] and capture['measurement_admission_ref'] == report['measurement_admission_ref']
        and capture['scope'] == scope and capture['status'] == 'collected' and capture['error'] is None
        and capture['qualification_passed'] is capture['admission_authority'] is capture['archive_performed'] is False
        and completion['finished_at'] <= start < finish and begin < end <= deadline == number(plan['deadline_monotonic'])
        and deadline <= begin + original_budget and finish - start <= deadline - begin
        and capture['build_receipt_ref'] == build_receipt_ref
        and finish <= original_wall_deadline,
        'PMU status, source build, formal/profile order, or deadline differs')
    reader.verify_artifact(capture['build_receipt_ref'])
    root = PurePosixPath(capture['directory'])
    require(root.is_absolute() and '..' not in root.parts and str(root) == capture['directory'], 'PMU directory differs')
    wall_deadline = min(start + deadline - begin,original_wall_deadline)
    seen, csv_refs = set(), set()
    assembly = str(PurePosixPath(config['build']['source_dir']).parent)
    capability = _execution(reader, capture['capabilities_ref'], [TOOL,'--help'], assembly, None, start, finish, wall_deadline, seen,
        timeout_cap=original_budget)
    help_text = reader.verify_artifact(capability['stdout_hash']).read_text()
    require(all(flag.split('=')[0] in help_text for flag in FLAGS), 'profiler lacks frozen whole-app flags')
    hardware = _execution(reader, capture['hardware_ref'], [NPU_SMI,'info','-t','board','-i',str(config['physical_device']),'-c','0'],
        assembly, None, capability['ended_at'], finish, wall_deadline, seen, timeout_cap=original_budget)
    require('9392' in reader.verify_artifact(hardware['stdout_hash']).read_text(), 'PMU device is not 910C/A3')
    require([(x['role'],x['index']) for x in capture['warmups']] == [(r,i) for r in ROLES for i in range(MIN_WARMUPS)]
        and [(x['role'],x['index']) for x in capture['captures']] == [(r,i) for r in ROLES for i in range(MIN_CAPTURES)],
        'PMU needs ten warmups and five independent whole-call captures per role')
    previous, partitions = hardware['ended_at'], {r:[] for r in ROLES}
    frequencies={r:[] for r in ROLES}
    for role in ROLES:
        expected = dict(binary_hash=binary_ref, tool_hash=tools[TOOL], source_hash=sources[role])
        for kind in ('warmups','captures'):
            for item in (x for x in capture[kind] if x['role'] == role):
                directory = root/role/('warmup' if kind == 'warmups' else 'capture')/str(item['index'])
                fields = 'role index directory execution_ref' + ('' if kind == 'warmups' else
                    ' profile_files_ref table_ref output_refs oracle_execution_ref oracle_result_ref slot_receipt_ref')
                if policy is not None: fields += ' collection_unit_ref'
                _keys(item, fields, 'PMU slot')
                require(item['directory'] == str(directory), 'PMU slot directory differs')
                slot_deadline, slot_cap = wall_deadline, original_budget
                if policy is not None:
                    unit = replay_collection_unit(reader,item['collection_unit_ref'],
                        parent_deadline=deadline,policy=policy,kind='pmu')
                    require(previous <= unit['started_at'] <= finish
                        and begin <= unit['started_monotonic'] <= end,
                        'PMU unit is outside the actual collection order')
                    previous = unit['started_at']
                    slot_deadline = min(wall_deadline,unit['wall_deadline'])
                    slot_cap = policy['pmu_unit_seconds']
                expand = lambda values: [v.replace('{cycle_dir}',str(directory)) for v in values]
                command = expand(case['command']) + ['--aprof-mechanism-role',role]
                require(command[0] == config['build']['binary'] and '--aprof-mechanism-role' not in case['command'],
                        'PMU needs exactly one complete role callback')
                record = _execution(reader, item['execution_ref'], command if kind == 'warmups' else capture_argv(command,directory/'profile'),
                    config['build']['source_dir'], expected, previous, min(finish,slot_deadline), slot_deadline, seen,
                    timeout_cap=slot_cap)
                previous = record['ended_at']
                if kind == 'warmups': continue
                sealed=_load(reader,item['slot_receipt_ref'])
                expected_slot=slot_receipt_value(reader,item,plan_ref=report['plan_ref'],
                    completion_ref=report['measurement_admission_ref'],scope=scope,
                    prepared_files=bound['prepared_files'],outputs_before_oracle=item['output_refs'],
                    outputs_after_oracle=item['output_refs'],finalized_at=sealed.get('finalized_at'))
                require(sealed==expected_slot,'aggregate PMU raw/output/oracle fields differ from finalized capture receipt')
                require(sealed['oracle']['ended_at']<=number(sealed['finalized_at'])<=min(finish,slot_deadline),
                    'capture was not finalized after actual oracle exit')
                files = _load(reader,item['profile_files_ref']); table = _table(files)
                frequencies[role].append(_frequency_basis(reader,files,scope,role))
                require(item['table_ref'] == files[table] and item['table_ref'] not in csv_refs,
                        'PMU CSV is missing from raw inventory or reuses an earlier capture')
                csv_refs.add(item['table_ref'])
                for ref in files.values(): reader.verify_artifact(ref)
                partitions[role].append(partition_call(reader.verify_artifact(item['table_ref']).read_text(),scope=scope,role=role))
                outputs, oracle = expand(case['output_files'][role]), expand(case['verify_commands'][role])
                require(set(item['output_refs']) == set(outputs), 'PMU output scope differs from complete Task oracle')
                for ref in item['output_refs'].values(): reader.verify_artifact(ref)
                checked = _execution(reader,item['oracle_execution_ref'],oracle,config['build']['source_dir'],
                    expected,previous,min(finish,slot_deadline),slot_deadline,seen,timeout_cap=slot_cap)
                result = _native(reader,item['oracle_result_ref'])
                require(result.get('passed') is True and result.get('case_id') == scope['case_id']
                    and _native_equal(json.loads(reader.verify_artifact(checked['stdout_hash']).read_text(),object_pairs_hook=_object), result),
                    'original complete-output oracle failed or stdout/result differs')
                previous = sealed['finalized_at']
    metrics = _reduce(partitions,scope)
    supported, unavailable = [], False
    for choice in selections:
        cells = [metrics[r]['aprof_'+r+'_'+choice['kernel']][choice['name']] for r in ROLES]
        if any(cell['status'] != 'known' or cell.get('stable') is not True for cell in cells):
            unavailable = True
            continue
        bases=[basis.get('aprof_'+role+'_'+choice['kernel']) if basis else None
               for role in ROLES for basis in frequencies[role]]
        if any(basis is None for basis in bases):
            unavailable=True
            continue
        require(all(basis==bases[0] for basis in bases),'raw device/frequency basis differs across selected captures')
        before, after = (c['median'] for c in cells)
        supported.append(after > before if choice['expected_direction'] == 'increase' else after < before)
    return dict(valid=True,alignment=True if any(supported) else (None if unavailable else False),
        metrics=metrics,partitions=partitions,frequency_basis=frequencies,scope=scope,admission_authority=False)
