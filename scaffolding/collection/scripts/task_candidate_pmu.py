"""Unactivated candidate full-call PMU glue; task-local evidence, one deadline.

Prepare after the reviewed build and before formal Task collection. The existing
Task collector must receive the returned plan's exact config. Capture preserves
the complete callback, original oracle and finalized per-slot evidence. Runtime
replay owns mechanism mathematics; this module grants no publication authority.
"""
import json
from pathlib import Path
import time

from aprof_runtime.contracts import GateEvidence
from aprof_runtime.full_call_pmu import PROTOCOL, KIND, PROFILE_DEPENDENCY_PATHS, _scope, replay_full_call_mechanism
from aprof_runtime.jsonio import file_hash
from aprof_runtime.measurement_entry import replay_current_measurement_admission
import task_baseline_pmu as collector
import task_validation_controller as candidate
from timing_admission import require, number

bridge = candidate.bridge
ENABLED_IN_1_0 = False


def _read(local, reference):
    return json.loads(local.verify_artifact(reference).read_text())


def _candidate(local, plan_ref, build_receipt_ref):
    plan, proof, execution = candidate._checked_candidate_plan(local, plan_ref)
    _, build = candidate._checked_build(local, plan_ref, build_receipt_ref, plan, proof, execution)
    require(plan['producer_refs'].get(str(Path(__file__).resolve())) == file_hash(__file__)
        and plan['producer_refs'].get(str(Path(collector.__file__).resolve())) == file_hash(collector.__file__),
        'candidate PMU producers were not frozen in the candidate plan')
    wrapper = _read(local, build_receipt_ref)
    config = bridge.timing.config_value(candidate.baseline._task_config(local, plan,
        local.verify_artifact(wrapper['receipt_ref']), build))
    return plan, build, config, wrapper['receipt_ref']


def _selections(scope, selections):
    require(isinstance(selections, list) and selections, 'PMU hypothesis selections missing')
    seen = set()
    for choice in selections:
        require(isinstance(choice, dict) and set(choice) == {'name','kernel','unit','expected_direction'},
                'PMU selection fields differ')
        key = (choice['name'], choice['kernel'])
        require(key not in seen and choice['name'] in scope['metrics']
            and choice['unit'] == scope['metrics'][choice['name']]['unit']
            and choice['expected_direction'] in ('increase','decrease')
            and all('aprof_'+r+'_'+choice['kernel'] in scope['role_kernel_names'][r] for r in collector.ROLES),
            'PMU selected kernel/metric/direction differs from the complete Task scope')
        seen.add(key)


def prepare_candidate_pmu_plan(local, *, candidate_plan_ref, build_receipt_ref, selections, destination):
    """Freeze exact Task config and named-kernel directions before formal timing."""
    started = time.time()
    bridge.remaining(_read(local, candidate_plan_ref)['deadline_monotonic'])
    plan, build, config, _ = _candidate(local, candidate_plan_ref, build_receipt_ref)
    candidate._local(local, plan['deadline_monotonic'])
    require(build['finished_at'] <= started, 'PMU planning precedes the actual reviewed build')
    scope = _scope(config, plan['profile']['case_id'], plan['profile']['metrics'])
    _selections(scope, selections)
    require(set(plan['toolchain_refs']) == set(PROFILE_DEPENDENCY_PATHS), 'candidate PMU SDK closure differs')
    destination = Path(destination)
    require(destination.is_absolute() and destination.resolve() == destination and not destination.exists(),
            'PMU plan destination must be fresh and canonical')
    destination.mkdir(parents=True, mode=0o700)
    # The formal collector uses this serializer; canonical register_json bytes differ.
    bridge.timing.old.save(destination/'config.json', config)
    value = dict(schema_version=1, kind='full_call_pmu_plan', protocol=PROTOCOL,
        candidate_id=plan['candidate_id'], config_ref=local.register_artifact(destination/'config.json'),
        source_hashes=plan['source_hashes'], created_at=started, deadline_monotonic=plan['deadline_monotonic'],
        scope=scope, selections=selections, toolchain_refs=plan['toolchain_refs'],
        launch_ref=plan['launch_ref'], build_window_ref=build_receipt_ref)
    bridge.save(destination/'mechanism-plan.json', value)
    bridge.remaining(plan['deadline_monotonic'])
    return local.register_artifact(destination/'mechanism-plan.json')


def _checked_plan(local, plan_ref):
    value = _read(local, plan_ref)
    require(set(value) == {'schema_version','kind','protocol','candidate_id','config_ref','source_hashes',
        'created_at','deadline_monotonic','scope','selections','toolchain_refs','launch_ref','build_window_ref'},
        'candidate PMU plan fields differ')
    wrapper = _read(local, value['build_window_ref'])
    plan, build, config, receipt_ref = _candidate(local, wrapper['plan_ref'], value['build_window_ref'])
    scope = _scope(config, plan['profile']['case_id'], plan['profile']['metrics'])
    require(value['schema_version'] == 1 and value['kind'] == 'full_call_pmu_plan' and value['protocol'] == PROTOCOL
        and value['candidate_id'] == plan['candidate_id'] and value['source_hashes'] == plan['source_hashes']
        and value['deadline_monotonic'] == plan['deadline_monotonic'] and value['launch_ref'] == plan['launch_ref']
        and value['scope'] == scope and _read(local, value['config_ref']) == config
        and value['toolchain_refs'] == plan['toolchain_refs']
        and set(value['toolchain_refs']) == set(PROFILE_DEPENDENCY_PATHS)
        and build['finished_at'] <= number(value['created_at']),
        'candidate PMU plan differs from reviewed build/config/source/deadline')
    _selections(scope, value['selections'])
    return value, plan, build, config, receipt_ref


def _task(local, plan, config, completion_ref):
    completion = _read(local, completion_ref)
    expected = {key:config[key] for key in ('operator','run_id','session_id','candidate_id')}
    expected['source_hashes'] = plan['source_hashes']
    result = replay_current_measurement_admission(local, completion_ref, expected=expected)
    require(result['valid'] is True and result['config_ref'] == plan['config_ref']
        and plan['created_at'] <= completion['started_at'] < completion['finished_at'],
        'candidate PMU was not preregistered for the actual formal Task')
    registration = _read(local, result['registration_ref'])
    return completion, registration


def collect_candidate_pmu(local, *, plan_ref, completion_ref, destination, deadline):
    """Reuse the complete 10+5 collector; no new build, raw copy or deadline."""
    bridge.remaining(deadline)
    value, original, build, config, receipt_ref = _checked_plan(local, plan_ref)
    require(deadline == value['deadline_monotonic'], 'candidate PMU reset the original deadline')
    completion, registration = _task(local, value, config, completion_ref)
    require(completion['finished_at'] <= time.time(), 'formal Task has not completed')
    case_id = value['scope']['case_id']
    bound = registration['identity']['cases'][str(case_id)]
    require(registration['identity']['source_hashes'] == value['source_hashes']
        and registration['identity']['build']['binary_ref'] == build['binary']['sha256']
        and receipt_ref in registration['identity']['build']['receipt_refs'].values(),
        'candidate PMU source/build differs from the formal Task')
    for group in ('prepared_files','verifier_files'):
        for ref in bound[group].values(): local.verify_artifact(ref)
    def setup():
        checked, current, built, current_config, native = _checked_plan(local, plan_ref)
        require(checked == value and native == receipt_ref, 'candidate PMU plan changed during capture')
        return {**current, 'pmu_scope':value['scope']}, built, next(
            c for c in current_config['cases'] if c['case_id'] == case_id)
    capture_ref = collector._collect_pmu(local, plan_ref=plan_ref, build_receipt_ref=receipt_ref,
        destination=destination, deadline=deadline, setup=setup, completion_ref=completion_ref,
        prepared_files=bound['prepared_files'])
    report = dict(schema_version='1.0.0', kind=KIND, protocol=PROTOCOL,
        candidate_id=value['candidate_id'], hypothesis_basis='heuristic', plan_ref=plan_ref,
        measurement_admission_ref=completion_ref, capture_report_ref=capture_ref)
    path = Path(destination)/'mechanism-report.json'
    bridge.save(path, report)
    report_ref = local.register_artifact(path)
    result = verify_candidate_pmu(local, plan_ref=plan_ref, completion_ref=completion_ref, report_ref=report_ref)
    bridge.remaining(deadline)
    return dict(mechanism_report_ref=report_ref, capture_report_ref=capture_ref, replay=result,
        artifacts=dict(mechanism_report=report_ref, mechanism_plan=plan_ref, measurement_admission=completion_ref,
            measurement_report=completion['measurement_report_ref'], task_launch=value['launch_ref'],
            build_window=value['build_window_ref']), admission_authority=False, archive_performed=False)


def verify_candidate_pmu(local, *, plan_ref, completion_ref, report_ref):
    """Real runtime replay; unknown frequency stays unknown, including after capture."""
    value, _, _, _, _ = _checked_plan(local, plan_ref)
    report = _read(local, report_ref)
    require(report['plan_ref'] == plan_ref and report['measurement_admission_ref'] == completion_ref,
            'candidate PMU report changed its actual Task/plan')
    completion = _read(local, completion_ref)
    evidence = GateEvidence.from_dict(dict(candidate_id=value['candidate_id'],
        **{key:'not_run' for key in ('static_review','build','accuracy','runtime','semantic','scope','portability')}, artifacts={
        'mechanism_report':report_ref, 'mechanism_plan':plan_ref, 'measurement_admission':completion_ref,
        'measurement_report':completion['measurement_report_ref'], 'task_launch':value['launch_ref'],
        'build_window':value['build_window_ref']}))
    return replay_full_call_mechanism(local, report, evidence=evidence, source_hashes=value['source_hashes'])
