"""Unactivated full-callback baseline PMU capture/replay, using task-local files.

This is a separate evidence contract, never an old single-kernel profile. Every
ordered Task occurrence is retained. Missing PMU cells remain unknown; Task
Duration is never used as a replacement. Runtime/graph qualification is pending.
"""
from task_budget import collection_policy, collection_unit_deadline, CollectionBoundaryStop
from aprof_runtime.task_window_measurement_admission import replay_collection_unit
import json
import os
from pathlib import Path
import shlex
import time

from aprof_runtime.jsonio import file_hash
from aprof_runtime.profile_evidence import MIN_CAPTURES, MIN_WARMUPS, MAX_PROFILE_CV
from aprof_runtime.full_call_pmu import partition_call, _capture_statistics, _table, _reduce, slot_receipt_value
from aprof_runtime.task_window_measurement_admission import PROFILE_DEPENDENCY_PATHS as TASK_DEPENDENCIES, SUMMARY_PYTHON
from timing_admission import require, number
import local_controller_bridge as bridge

PROTOCOL = 'baseline_full_call_pmu_v1'
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
ENABLED_IN_1_0 = False
# CANN 9 PipeUtilization export fields; ordinary op_summary identity is not PMU.
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


def scope_from_plan(plan):
    selected = plan['cases'][plan['profile']['case_id'] - 1]
    metrics = plan['profile']['metrics']
    require(metrics and all(spec['file'] == 'op_summary*.csv'
        and spec['format'] == 'csv' and spec['field'] in PMU_FIELDS
        and spec['unit'] == PMU_FIELDS[spec['field']]
        and spec['row_aggregation'] == spec['aggregation'] == 'median'
        for spec in metrics.values()), 'PMU requires explicit PMU columns, not Task timing fields')
    return dict(protocol=PROTOCOL, case_id=selected['case_id'], device=plan['device'],
        role_kernel_names=selected['role_kernel_names'], launches_per_call=selected['launches_per_call'],
        metrics=metrics, warmups=MIN_WARMUPS, captures=MIN_CAPTURES, flags=list(FLAGS),
        occurrence_scope='all_ordered_tasks_in_one_complete_callback',
        within_kernel='median_of_all_occurrences', across_captures='median', maximum_cv=MAX_PROFILE_CV)


def capture_argv(command, raw):
    return [TOOL, '--output=' + str(raw), *FLAGS, '--application=' + shlex.join(command)]


def _read(local, reference):
    return json.loads(local.verify_artifact(reference).read_text())


def _setup(local, plan_ref, build_receipt_ref):
    from task_baseline_qualification import checked_plan, _task_config
    from task_baseline_build import checked_baseline_build
    plan = checked_plan(local, plan_ref)
    _, build = checked_baseline_build(local, plan_ref=plan_ref, build_receipt_ref=build_receipt_ref)
    require(plan['pmu_scope'] == scope_from_plan(plan), 'unregistered PMU occurrence scope')
    require(plan['producer_refs'].get(str(Path(__file__).resolve())) == file_hash(__file__), 'PMU producer not frozen')
    config = _task_config(local, plan, local.verify_artifact(build_receipt_ref), build)
    return plan, build, config['cases'][plan['pmu_scope']['case_id']-1]


def _commands(case, role, directory):
    expand = lambda values: [value.replace('{cycle_dir}', str(directory)) for value in values]
    command = expand(case['command']) + ['--aprof-mechanism-role', role]
    return command, expand(case['verify_commands'][role]), expand(case['output_files'][role])


def collect_baseline_pmu(local, *, plan_ref, build_receipt_ref, destination, deadline):
    """Ten warmups and five fresh whole-application captures per role; no CAS."""
    return _collect_pmu(local, plan_ref=plan_ref, build_receipt_ref=build_receipt_ref,
        destination=destination, deadline=deadline,
        setup=lambda: _setup(local, plan_ref, build_receipt_ref))


def _collect_pmu(local, *, plan_ref, build_receipt_ref, destination, deadline, setup,
                 completion_ref=None, prepared_files=None):
    """Shared process loop; callers authenticate their distinct source contracts."""
    started, mono = time.time(), time.monotonic()
    bridge.remaining(deadline)
    plan, build, case = setup()
    require(deadline == build['deadline_monotonic'] and build['finished_at'] <= started,
            'PMU must inherit the original build deadline')
    scope = plan['pmu_scope']; destination = Path(destination)
    policy=collection_policy(plan); next_unit=None
    require(destination.is_absolute() and destination.resolve()==destination and not destination.exists(),
            'PMU destination must be fresh and canonical')
    require(bridge.timing.old.select_mount(Path('/proc/self/mountinfo').read_text(), destination)['filesystem_type']
            in bridge.timing.old.LOCAL_PROFILE_FILESYSTEMS, 'PMU evidence must remain task-local')
    destination.mkdir(parents=True, mode=0o700)
    report = dict(schema_version=1, protocol=scope['protocol'], plan_ref=plan_ref, build_receipt_ref=build_receipt_ref,
        scope=scope, directory=str(destination), started_at=started, started_monotonic=mono,
        deadline_monotonic=deadline, warmups=[], captures=[], status='failed', error=None,
        qualification_passed=False, admission_authority=False, archive_performed=False)
    if completion_ref is not None:
        report['measurement_admission_ref'] = completion_ref
    try:
        require(os.environ.get('ASCEND_RT_VISIBLE_DEVICES')==str(plan['physical_device']), 'PMU visible device differs')
        with bridge.timing.shared.device_lock(plan['physical_device'], bridge.remaining(deadline)):
            report['capabilities_ref'] = bridge.profile_capture.run([TOOL, '--help'], plan['assembly_dir'],
                destination/'capabilities', bridge.remaining(deadline), local, environment={})['log_hash']
            report['hardware_ref'] = bridge.profile_capture.run(
                [NPU_SMI,'info','-t','board','-i',str(plan['physical_device']),'-c','0'], plan['assembly_dir'],
                destination/'hardware', bridge.remaining(deadline), local, environment={})['log_hash']
            for role in ROLES:
                binding = dict(binary=build['binary']['path'], tool=TOOL, source_dir=plan['roles'][role]['path'],
                    expected=dict(binary_hash=build['binary']['sha256'], tool_hash=plan['toolchain_refs'][TOOL],
                                  source_hash=plan['source_hashes'][role]))
                for index in range(scope['warmups'] + scope['captures']):
                    warmup = index < scope['warmups']; slot = index if warmup else index-scope['warmups']
                    next_unit=dict(role=role,mode='warmup' if warmup else 'capture',index=slot)
                    unit_started=time.monotonic();unit_wall=time.time()
                    unit_deadline=collection_unit_deadline(deadline,policy,'pmu',now=unit_started)
                    directory = destination/role/('warmup' if warmup else 'capture')/str(slot)
                    directory.mkdir(parents=True)
                    unit_ref=None
                    if policy is not None:
                        unit=dict(schema_version=1,started_at=unit_wall,started_monotonic=unit_started,deadline_monotonic=unit_deadline)
                        bridge.save(directory/'collection-unit.json',unit)
                        unit_ref=local.register_artifact(directory/'collection-unit.json')
                    command, oracle, outputs = _commands(case, role, directory)
                    argv = command if warmup else capture_argv(command, directory/'profile')
                    record = bridge.profile_capture.run(argv, Path(plan['assembly_dir'])/'source', directory/'capture',
                        bridge.remaining(unit_deadline), local, binding, environment={})
                    item = dict(role=role, index=slot, directory=str(directory), execution_ref=record['log_hash'])
                    if unit_ref is not None: item['collection_unit_ref']=unit_ref
                    report['warmups' if warmup else 'captures'].append(item)
                    if not warmup:
                        files = bridge.timing.old.profile_files(directory/'profile', local)
                        item['profile_files_ref'] = local.register_json(files)
                        item['table_ref'] = files[_table(files)]
                        partition_call(local.verify_artifact(item['table_ref']).read_text(), scope=scope, role=role)
                        item['output_refs'] = {path:local.register_artifact(path) for path in outputs}
                        verification = bridge.profile_capture.run(oracle, Path(plan['assembly_dir'])/'source',
                            directory/'oracle', bridge.remaining(unit_deadline), local, binding, environment={})
                        item['oracle_execution_ref'] = verification['log_hash']
                        result = Path(oracle[oracle.index('--result')+1])
                        item['oracle_result_ref'] = local.register_artifact(result)
                        require(_read(local,item['oracle_result_ref']).get('passed') is True, 'PMU complete output oracle failed')
                        after_outputs={path:local.register_artifact(path) for path in outputs}
                        require(after_outputs==item['output_refs'], 'oracle changed PMU output')
                        planned=plan['cases'][scope['case_id']-1]
                        prepared=prepared_files if prepared_files is not None else {
                            planned['metadata_path']:planned['metadata_ref'],**planned['input_files']}
                        sealed=slot_receipt_value(local,item,plan_ref=plan_ref,completion_ref=completion_ref,scope=scope,
                            prepared_files=prepared,outputs_before_oracle=item['output_refs'],
                            outputs_after_oracle=after_outputs,finalized_at=time.time())
                        bridge.save(directory/'slot-receipt.json',sealed)
                        item['slot_receipt_ref']=local.register_artifact(directory/'slot-receipt.json')
                    checkpoint=destination/('completed-'+role+'-'+('warmup' if warmup else 'capture')+'-'+str(slot)+'.json')
                    bridge.save(checkpoint,report);local.register_artifact(checkpoint)
                    local.write_index(directory/'completed-local-index.json')
                    bridge.remaining(unit_deadline)
                    next_unit=None
        setup()
        report['status']='collected'
    except BaseException as error:
        report['error']={'type':type(error).__name__,'message':str(error)}
        if isinstance(error,CollectionBoundaryStop):
            stop=dict(kind='collection_budget_stop',policy=policy,deadline_monotonic=deadline,
                stopped_monotonic=time.monotonic(),next_unit=next_unit,complete=False,admission_authority=False)
            bridge.save(destination/'budget-stop.json',stop);local.register_artifact(destination/'budget-stop.json')
        raise
    finally:
        report.update(finished_at=time.time(), finished_monotonic=time.monotonic())
        bridge.save(destination/'pmu-report.json', report)
        reference=local.register_artifact(destination/'pmu-report.json')
        local.write_index(destination/'partial-local-index.json')
    bridge.remaining(deadline)
    return reference


def _execution(local, reference, argv, cwd, binding, previous, finish, deadline):
    record=_read(local,reference)
    require(record['argv']==argv and record['cwd']==str(cwd) and record['exit_code']==0
            and record['error'] is None and record['environment']=={}
            and previous<=number(record['started_at'])<=number(record['ended_at'])<=finish
            and 0<number(record['timeout_seconds'])<=deadline-number(record['started_at'])+.01
            and number(record['started_at'])+record['timeout_seconds']<=deadline+.01
            and number(record['ended_at'])-record['started_at']<=record['timeout_seconds'],
            'PMU actual command/exit/deadline differs')
    if binding is not None:
        require(record['identity_checks']=={'before':binding,'after':binding}, 'PMU source/binary/tool identity differs')
    for key in ('stdout_hash','stderr_hash'): local.verify_artifact(record[key])
    return record


def verify_baseline_pmu(local, *, plan_ref, build_receipt_ref, report_ref):
    """Independently read all raw CSVs/occurrences and original oracle evidence."""
    plan,build,case=_setup(local,plan_ref,build_receipt_ref)
    report=_read(local,report_ref); scope=plan['pmu_scope']; root=Path(report['directory'])
    start,finish=number(report['started_at']),number(report['finished_at'])
    begin,end,deadline=(number(report[k]) for k in ('started_monotonic','finished_monotonic','deadline_monotonic'))
    require(report['protocol']==PROTOCOL and report['plan_ref']==plan_ref and report['build_receipt_ref']==build_receipt_ref
        and report['scope']==scope and report['status']=='collected' and report['error'] is None
        and build['finished_at']<=start<=finish and begin<=end<=deadline<=begin+plan['budget_seconds']
        and deadline==build['deadline_monotonic']
        and report['qualification_passed'] is report['admission_authority'] is report['archive_performed'] is False,
        'PMU receipt scope/status/time differs')
    wall_deadline=start+deadline-begin
    policy=collection_policy(plan)
    capability=_execution(local,report['capabilities_ref'],[TOOL,'--help'],plan['assembly_dir'],None,start,finish,wall_deadline)
    help_text=local.verify_artifact(capability['stdout_hash']).read_text()
    require(all(flag.split('=')[0] in help_text for flag in FLAGS), 'installed profiler lacks frozen whole-app options')
    hardware=_execution(local,report['hardware_ref'],[NPU_SMI,'info','-t','board','-i',str(plan['physical_device']),'-c','0'],
        plan['assembly_dir'],None,capability['ended_at'],finish,wall_deadline)
    require('9392' in local.verify_artifact(hardware['stdout_hash']).read_text(), 'PMU hardware is not the frozen A3 device')
    require([(s['role'],s['index']) for s in report['warmups']]==[(r,i) for r in ROLES for i in range(MIN_WARMUPS)]
        and [(s['role'],s['index']) for s in report['captures']]==[(r,i) for r in ROLES for i in range(MIN_CAPTURES)],
        'PMU requires ten warmups and five independent captures per role')
    previous=hardware['ended_at']; partitions={r:[] for r in ROLES}
    for role in ROLES:
        expected=dict(binary_hash=build['binary']['sha256'],tool_hash=plan['toolchain_refs'][TOOL],source_hash=plan['source_hashes'][role])
        for kind in ('warmups','captures'):
            for item in [s for s in report[kind] if s['role']==role]:
                directory=root/role/('warmup' if kind=='warmups' else 'capture')/str(item['index'])
                require(item['directory']==str(directory), 'PMU slot escaped its fixed path')
                unit_wall_deadline=wall_deadline
                if policy is not None:
                    unit=replay_collection_unit(local,item['collection_unit_ref'],parent_deadline=deadline,policy=policy,kind='pmu')
                    unit_wall_deadline=min(wall_deadline,unit['wall_deadline'])
                    require(previous<=unit['started_at']<=finish and begin<=unit['started_monotonic']<=end, 'PMU unit boundary reordered')
                    previous=unit['started_at']
                else:
                    require('collection_unit_ref' not in item, 'unregistered PMU unit policy')
                command,oracle,outputs=_commands(case,role,directory)
                record=_execution(local,item['execution_ref'],command if kind=='warmups' else capture_argv(command,directory/'profile'),
                    Path(plan['assembly_dir'])/'source',expected,previous,finish,unit_wall_deadline)
                previous=record['ended_at']
                if kind=='warmups': continue
                sealed=_read(local,item['slot_receipt_ref'])
                planned=plan['cases'][scope['case_id']-1]
                prepared={planned['metadata_path']:planned['metadata_ref'],**planned['input_files']}
                expected_slot=slot_receipt_value(local,item,plan_ref=plan_ref,completion_ref=None,scope=scope,
                    prepared_files=prepared,outputs_before_oracle=item['output_refs'],
                    outputs_after_oracle=item['output_refs'],finalized_at=sealed.get('finalized_at'))
                require(sealed==expected_slot and sealed['oracle']['ended_at']<=number(sealed['finalized_at'])<=min(finish,unit_wall_deadline),
                    'PMU finalized slot differs from actual capture/raw/output/oracle scope')
                files=_read(local,item['profile_files_ref']); table=_table(files)
                require(item['table_ref']==files[table], 'PMU CSV differs from its full raw inventory')
                require({p.relative_to(directory/'profile').as_posix() for p in bridge.profile_capture.safe_files(directory/'profile')}
                        ==set(files), 'PMU raw profile roster differs')
                for name,reference in files.items():
                    require(file_hash(directory/'profile'/name)==reference, 'PMU raw file changed')
                    local.verify_artifact(reference)
                partitions[role].append(partition_call(local.verify_artifact(item['table_ref']).read_text(),scope=scope,role=role))
                require(set(item['output_refs'])==set(outputs), 'PMU omitted a complete output')
                for name,reference in item['output_refs'].items():
                    require(file_hash(name)==reference, 'PMU independent output changed');local.verify_artifact(reference)
                checked=_execution(local,item['oracle_execution_ref'],oracle,Path(plan['assembly_dir'])/'source',
                    expected,previous,finish,unit_wall_deadline)
                result=_read(local,item['oracle_result_ref'])
                require(result.get('passed') is True and result.get('case_id')==scope['case_id']
                    and file_hash(oracle[oracle.index('--result')+1])==item['oracle_result_ref']
                    and json.loads(local.verify_artifact(checked['stdout_hash']).read_text())==result,
                    'PMU original oracle/result differs')
                previous=sealed['finalized_at']
    complete=all(p['pmu_complete'] for values in partitions.values() for p in values)
    metrics=_reduce(partitions,scope)
    return dict(valid=True,pmu_complete=complete,partitions=partitions,metrics=metrics,
        qualification_passed=False,admission_authority=False,archive_performed=False,
        missing_join='runtime graph Context and evaluation entry integration')
