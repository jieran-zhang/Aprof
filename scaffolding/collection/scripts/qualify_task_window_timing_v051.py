#!/usr/bin/env python3
"""Once-only Task Duration method qualification; never publish a skill release."""
from __future__ import annotations

import argparse
import contextlib
from copy import deepcopy
from datetime import datetime
import importlib
import importlib.util
import json
import os
import re
from pathlib import Path
import shlex
import shutil
import sqlite3
import statistics
import sys
import time

from run_aprof_job import run as job_run
from run_shared_timing_confirmation import (BASE_ENVIRONMENT, ROOT, RELEASE, binding, locks,
    native_messages, production_oracle, save_new, timeline_protocol)
from replay_timing_diagnosis import Evidence, digest, read, require
from qualify_shared_timing_v051 import protocol_commands, source_files
from diagnose_task_duration import oracle, execution_interval

PROTOCOL = 'shared_buffer_msprof_task_window_v4'
PRIOR_PROTOCOL = 'shared_buffer_msprof_task_window_v2'
HISTORICAL_PROTOCOL = 'shared_buffer_msprof_task_window_v1'
TARGET_MS = 10
PLANNED_OUTPUT_NAME = 'production-task-window-confirmation-v4-local'
PRE_CHANGE_SCAFFOLDING = ROOT.parent / ('validation-graph-base-0.5.1-20261014/'
    'task-window-v2-10ms-design/pre-change-scaffolding/index.json')
PRE_CHANGE_SCAFFOLDING_SHA256 = 'sha256:639432f96785d3848ef6efe8547260a0b28de32850d7a17534c6115c3183c378'
PRE_CHANGE_PACKAGE = ROOT.parent / ('validation-graph-base-0.5.1-20261014/'
    'task-window-v2-10ms-design/pre-change/index.json')
PRE_CHANGE_PACKAGE_SHA256 = 'sha256:acefc7f3e51336db89cb4f94f39e2e7b860a05cf9ec0f3a6bd2bacba697959df'
PURPOSE = 'preregistered_task_window_native_method_qualification'
PREDECESSOR = ROOT.parent / 'validation-graph-base-0.5.1-20261014/production-confirmation-duration-v2'
HISTORY = ROOT / 'scaffolding/curation/graph-base-0.5.1-task-window-method-history.json'
COST_EVIDENCE = ROOT / 'scaffolding/curation/graph-base-0.5.1-profile-storage-cost-evidence.json'
COST_SUMMARY = ROOT.parent / 'validation-graph-base-0.5.1-20261014/inventory-proof-cost-v2/cost-summary.json'
COST_SUMMARY_SHA256 = 'sha256:7e6cc70a3b3241f4fddf58a5f78f976ff0e0c1d98129719c07c19b187429d397'
OFFLINE_COST_ROOT = ROOT.parent / 'validation-graph-base-0.5.1-20261014/evidence'
OFFLINE_COST_STUDIES = {
    'inventory': ('parallel-inventory-cost-v1',
                  'b622c69517ea2baf7374620123641a2472238837c60ea65bf5d4c4bea5a93d8d',
                  '7a4ae50ae33b5cea6664368f77f97568c9b2902b532fe93d69c4d798cb3e9a40',
                  'offline_parallel_inventory_cost_only', 'retain_complete_parallel_inventory_cost_candidate'),
    'registration': ('parallel-registration-cost-v1',
                     '412c0f5341ba338f1bbd023adec3901e0904c4bd1b8d67300ab905ab0c437742',
                     '12d59229e116225ecdd3c31db5294dccff82ea3cd54c92bdfa58c03fa7e08658',
                     'offline_parallel_registration_cost_only', 'retain_complete_parallel_registration_cost_candidate'),
    'width8_rejected': ('parallel-io-width-cost-v1',
                        '9427604ec595f303fc02cb542d5615bfe3c7476655fc07813b698f6e9e9afdd6',
                        'fce4356e70a2670af6d838a0e81e17c41ff05db47fee15da80bb260f3d4efde2',
                        'offline_parallel_width_cost_only', 'retain_complete_width8_cost_candidate'),
    'serial_cas_rejected': ('task-window-v3-cas-cost-v1',
                            'c71838e1a2256fc32221764020a9bafaeb5ac7a663bcde8cd1a7e040181fff6a',
                            'a2c3beb5a88ca560c0f45530cab097702e3a9a6de8f33ced39eef10f35499ee0',
                            'offline_serial_cas_persistence_cost_only',
                            'retain_complete_serial_cas_cost_candidate'),
}
WIDTH4_RESTORATION = OFFLINE_COST_ROOT / 'parallel-io-width-cost-v1/restored-width4.json'
WIDTH4_RESTORATION_SHA256 = 'sha256:0b0d011fa3bf5870adb5a298b8c044c1cfa742644ab901e85b01eff7525aaaa8'
FAILED_ATTEMPT_LEAF = ROOT.parent / ('validation-graph-base-0.5.1-20261014/'
    'measurement-task-window-v1-failure-evidence-20261014/task-window-failure-leaf.json')
FAILED_ATTEMPT_SHA256 = 'sha256:de4df5f6c552567e0d1c2a26cd632fa665c904f38295a423863d7b9c1006e2b0'
V2_FAILURE_DIR = ROOT.parent / ('validation-graph-base-0.5.1-20261014/'
    'evidence/task-window-v2-failure-preparation')
V2_FAILURE_LEAF = V2_FAILURE_DIR / 'task-window-v2-failure-leaf.json'
V2_ARCHIVE_SHA256 = 'sha256:f4977712ca84a90dbbed35128e73e42507e21be2237205507343fc617f633099'
V2_REPLAY_SHA256 = 'sha256:c8c985064982e00ccd6b3db38a29ea422dfb378eccaad524d608c2a9bb1a1538'
COLLECTOR = RELEASE / 'skills/ascendc-aprof-profiling/scripts/device_task_window_timing.py'
NATIVE_SOURCES = ROOT.parent / 'prospective-native-task-20261014'
from probe_native_task_profile import source_identity, clean_parent_environment
from task_profile_native import HEADER
OBSERVATIONS = {'exp': [(1, ['unprofiled', 'profiled']), (9, ['profiled', 'unprofiled'])],
                'sigmoid': [(1, ['profiled', 'unprofiled']), (4, ['unprofiled', 'profiled'])]}
BUDGETS = {'confirmation': 3600, 'observation': 1200, 'campaign': 12600}


def task_modules():
    sys.path.insert(0, str(COLLECTOR.parent)); sys.path.insert(0, str(RELEASE / 'runtime/src'))
    collector = importlib.import_module('device_task_window_timing')
    from aprof_runtime.task_window_measurement_admission import replay_task_window_measurement_admission
    from aprof_runtime.task_window_timing import partition_window_tasks
    from aprof_runtime.measurement_admission import _phase_controls
    return collector, replay_task_window_measurement_admission, partition_window_tasks, _phase_controls


def release_inventory():
    spec = importlib.util.spec_from_file_location('task_qualification_release', RELEASE / 'tools/release.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.inventory(RELEASE)


def check_controls(controls):
    for phase in ('aa_before', 'formal', 'aa_after'):
        require(controls[phase]['role_bias'] <= .02 and all(controls[phase][role + '_cv'] <= .05
                for role in ('baseline', 'candidate')), 'same-source Task A/A controls failed')
    require(all(value <= .02 for value in controls['drift'].values()), 'Task A/A drift failed')


def failed_attempt_ref():
    reference = binding(FAILED_ATTEMPT_LEAF)
    require(reference == {'path': str(FAILED_ATTEMPT_LEAF), 'sha256': FAILED_ATTEMPT_SHA256},
            'prior Task-window failure leaf changed')
    return reference


def failed_attempt_v2_ref():
    reference = binding(V2_FAILURE_LEAF)
    leaf = read(V2_FAILURE_LEAF)
    require(leaf['purpose'] == 'historical_failed_task_window_v2_10ms'
            and leaf['accepted'] is False and leaf['eligible_for_publication'] is False
            and leaf['archive_index_ref']['sha256'] == V2_ARCHIVE_SHA256
            and leaf['replay_result_ref']['sha256'] == V2_REPLAY_SHA256,
            'actual failed v2 attempt leaf changed')
    return reference


def replay_failed_attempt_v2(reference):
    require(reference == failed_attempt_v2_ref(), 'failed v2 leaf reference differs')
    source = V2_FAILURE_DIR / 'replay_task_window_v2_failure.py'
    require(read(V2_FAILURE_LEAF)['leaf_source_ref'] == binding(source),
            'failed v2 leaf source differs')
    spec = importlib.util.spec_from_file_location('frozen_failed_task_window_v2', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.replay_task_window_v2_failure(reference)
    require(result['valid'] is True and result['accepted'] is False
            and result['eligible_for_publication'] is False
            and result['complete_method_qualification'] is False
            and result['measurement_admission_replayed'] is False,
            'failed v2 attempt acquired acceptance')
    return result


def design_source_ref():
    reference = binding(PRE_CHANGE_SCAFFOLDING)
    require(reference == {'path': str(PRE_CHANGE_SCAFFOLDING),
                          'sha256': PRE_CHANGE_SCAFFOLDING_SHA256},
            'Task-window 10 ms pre-change source archive changed')
    index = read(PRE_CHANGE_SCAFFOLDING)
    expected = {str(Path(__file__).resolve()),
                str(ROOT / 'scaffolding/tools/verify_task_window_publication.py')}
    require(index['schema_version'] == 1
            and index['purpose'] == 'pre_change_scaffolding_task_window_v2_10ms'
            and set(index['files']) == expected,
            'Task-window pre-change source scope differs')
    for original, item in index['files'].items():
        require(item['sha256'] == binding(item['archive_path'])['sha256']
                and item['bytes'] == Path(item['archive_path']).stat().st_size,
                'Task-window pre-change source bytes differ')
    return reference


def design_package_ref():
    reference = binding(PRE_CHANGE_PACKAGE)
    require(reference == {'path': str(PRE_CHANGE_PACKAGE), 'sha256': PRE_CHANGE_PACKAGE_SHA256},
            'Task-window pre-change package archive index changed')
    index = read(PRE_CHANGE_PACKAGE)
    original, archived = Path(index['original_root']), Path(index['archived_root'])
    require(index['schema_version'] == 1 and index['not_a_release'] is True
            and index['eligible_for_publication'] is False
            and index['purpose'] == 'preserve_complete_pre_change_package_for_inventory_cost_v2_and_task_window_v1_history'
            and original == RELEASE and archived == PRE_CHANGE_PACKAGE.parent / 'payload/graph-base/0.5.1'
            and index['file_count'] == len(index['files']) == 213,
            'Task-window pre-change package scope differs')
    for path, item in index['files'].items():
        require(Path(path).is_relative_to(original)
                and Path(item['path']) == archived / Path(path).relative_to(original)
                and item['sha256'] == binding(item['path'])['sha256']
                and item['bytes'] == Path(item['path']).stat().st_size,
                'Task-window pre-change package bytes differ')
    return reference


def cost_summary_ref():
    reference = binding(COST_SUMMARY)
    require(reference == {'path': str(COST_SUMMARY), 'sha256': COST_SUMMARY_SHA256},
            'Task-window fixed 10 ms cost summary changed')
    return reference


def verify_cost_summary():
    """Check the fixed offline design evidence; it grants no measurement acceptance."""
    summary = read(cost_summary_ref()['path'])
    require(summary['schema_version'] == 1
            and summary['purpose'] == 'immutable_inventory_cost_and_fixed_10ms_planning_summary'
            and summary['eligible_for_publication'] is False
            and summary['formal_acceptance'] is False
            and summary['new_package_archive_ref'] == design_package_ref(),
            'Task-window cost summary authority/source differs')
    decision = summary['fixed_10ms_distinct_protocol']
    require(decision['protocol'] == PRIOR_PROTOCOL and decision['target_nanoseconds'] == TARGET_MS * 1_000_000
            and decision['prior_target_nanoseconds'] == 50_000_000
            and decision['formal_acceptance'] is False
            and decision['status'] == 'selected_by_root_for_new_preregistration_not_accepted',
            'Task-window target was not the frozen cost-driven design choice')
    references = summary['references']
    require(set(references) == {'amendment.json', 'anchor.json', 'campaign-execution/execution.json',
            'campaign-job.json', 'cost.py', 'plan.json', 'preflight-validation.json', 'result.json'},
            'Task-window cost source roster differs')
    for reference in references.values():
        require(binding(reference['path']) == reference, 'Task-window cost source bytes differ')
    plan, result = read(references['plan.json']['path']), read(references['result.json']['path'])
    archive = read(PRE_CHANGE_PACKAGE)
    archived_files = {str(Path(original).relative_to(RELEASE)): item['sha256']
                      for original, item in archive['files'].items()}
    require(archive['source_plan'] == references['plan.json']
            and plan['packages']['new']['files'] == archived_files
            and plan['order'] == ['old', 'new', 'new', 'old']
            and result['complete'] is True and result['eligible_for_publication'] is False
            and summary['measured']['complete'] is True
            and summary['measured']['outputs_equivalent_except_registered_collector_hash'] is True,
            'Task-window cost plan or old package snapshot differs')
    spec = importlib.util.spec_from_file_location('frozen_task_window_inventory_cost', references['cost.py']['path'])
    cost = importlib.util.module_from_spec(spec); spec.loader.exec_module(cost)
    require(cost.compare_packages(plan['packages']['old']['files'], plan['packages']['new']['files'])
            == plan['allowed_package_differences'], 'Task-window cost package changed beyond collector')
    rows, normalized = summary['measured']['slots'], []
    require(len(rows) == len(result['slots']) == 4, 'Task-window cost four-slot roster differs')
    for index, (row, actual) in enumerate(zip(rows, result['slots'], strict=True)):
        require(row['slot'] == index and row['mode'] == actual['mode'] == plan['order'][index]
                and row['result_ref'] == actual['result'] and row['execution_ref'] == actual['execution'],
                'Task-window cost slot binding differs')
        require(binding(actual['execution']['path']) == actual['execution']
                and binding(actual['result']['path']) == actual['result']
                and binding(row['outputs_ref']['path']) == row['outputs_ref'],
                'Task-window cost slot artifact bytes differ')
        execution = read(actual['execution']['path'])
        slot = read(actual['result']['path'])
        output = read(row['outputs_ref']['path'])
        require(execution['status'] == slot['status'] == 'passed' and execution['exit_code'] == 0
                and slot['outputs'] == row['outputs_ref']
                and row['phases'] == [{key: phase[key] for key in ('name', 'status', 'seconds', 'calls', 'bytes_read')}
                                      for phase in slot['phases']]
                and row['hash_bytes_read'] == slot['file_hash_bytes_read']
                and row['hash_calls'] == slot['file_hash_calls']
                and abs(row['measured_seconds'] - slot['measured_seconds']) < 1e-6,
                'Task-window cost measurements differ from actual slot receipts')
        normalized.append(cost.equivalent_outputs(output, row['mode'], plan))
    require(all(item == normalized[0] for item in normalized[1:]),
            'Task-window cost snapshots differ beyond the frozen collector hash')
    return cost_summary_ref()


def offline_cost_studies_ref():
    """Bind completed planning studies; none is a measurement admission."""
    refs = {}
    for label, (folder, summary_hash, archive_hash, summary_purpose, archive_purpose) in OFFLINE_COST_STUDIES.items():
        base = OFFLINE_COST_ROOT / folder
        summary_path, archive_path = base / 'cost-summary.json', base / 'candidate-source-archive/index.json'
        summary_ref = {'path': str(summary_path), 'sha256': 'sha256:' + summary_hash}
        archive_ref = {'path': str(archive_path), 'sha256': 'sha256:' + archive_hash}
        require(binding(summary_path) == summary_ref and binding(archive_path) == archive_ref,
                'offline cost study bytes changed: ' + label)
        summary, archive = read(summary_path), read(archive_path)
        require(summary['schema_version'] == archive['schema_version'] == 1
                and summary['purpose'] == summary_purpose and archive['purpose'] == archive_purpose
                and summary['complete'] is True and summary['accepted'] is False
                and summary['eligible_for_publication'] is False
                and (label != 'serial_cas_rejected' or summary['decision'] ==
                     'reject_serial_cas_verification_cost_and_stage_complete_parallel_verification')
                and archive['not_a_release'] is True and archive['eligible_for_publication'] is False
                and summary['source_archive_ref'] == archive_ref
                and archive['plan_ref'] == summary['plan_ref']
                and archive['original_root'] == str(RELEASE)
                and archive['archive_root'] == str(base / 'candidate-source-archive/payload/graph-base/0.5.1')
                and len(archive['files']) == 213,
                'offline cost study scope or authority changed: ' + label)
        plan = read(summary['plan_ref']['path'])
        result = read(summary['result_ref']['path'])
        execution = read(summary['execution_ref']['path'])
        require(binding(summary['plan_ref']['path']) == summary['plan_ref']
                and binding(summary['result_ref']['path']) == summary['result_ref']
                and binding(summary['execution_ref']['path']) == summary['execution_ref']
                and execution['status'] == 'passed' and execution['exit_code'] == 0
                and result['complete'] is True and result['formal_acceptance'] is False
                and result['eligible_for_publication'] is False
                and len(summary['slot_refs']) == len(result['slots']) == 8
                and set(archive['files']) == set(plan['packages']['new']['files'])
                and all(item == {'original_path': str(RELEASE / relative),
                                 'path': str(Path(archive['archive_root']) / relative),
                                 'sha256': plan['packages']['new']['files'][relative]}
                        for relative, item in archive['files'].items()),
                'offline cost study package snapshot changed: ' + label)
        refs[label] = {'summary_ref': summary_ref, 'source_archive_ref': archive_ref}
    width = read(WIDTH4_RESTORATION)
    restoration_ref = {'path': str(WIDTH4_RESTORATION), 'sha256': WIDTH4_RESTORATION_SHA256}
    restored_source = read(refs['inventory']['source_archive_ref']['path'])
    require(binding(WIDTH4_RESTORATION) == restoration_ref
            and read(refs['width8_rejected']['summary_ref']['path'])['decision'] == 'reject_width8_and_restore_width4'
            and width['status'] == 'passed' and width['eligible_for_publication'] is False
            and width['summary_ref'] == refs['width8_rejected']['summary_ref']
            and width['archive_ref'] == refs['width8_rejected']['source_archive_ref']
            and width['restored_exact_package_inventory'] is True and width['restored_file_count'] == 213
            and width['old_package_root'] == restored_source['archive_root']
            and set(width['changed_files']) == {
                'runtime/src/aprof_runtime/store.py',
                'skills/ascendc-aprof-profiling/scripts/device_task_window_timing.py'}
            and all(item == {'path': str(RELEASE / relative),
                             'sha256': restored_source['files'][relative]['sha256']}
                    for relative, item in width['changed_files'].items()),
            'rejected width8 study or exact width4 restoration changed')
    refs['width4_restoration_ref'] = restoration_ref
    return refs


def bind_offline_cost_studies(files, refs):
    """Freeze each source snapshot and the studies' direct receipts."""
    require(refs == offline_cost_studies_ref(), 'offline cost studies were not preregistered')
    for label in OFFLINE_COST_STUDIES:
        summary_ref, archive_ref = refs[label]['summary_ref'], refs[label]['source_archive_ref']
        summary, archive = read(summary_ref['path']), read(archive_ref['path'])
        for reference in (summary_ref, archive_ref, summary['plan_ref'], summary['result_ref'],
                          summary['execution_ref'], *[value for slot in summary['slot_refs'] for value in slot.values()]):
            files[reference['path']] = reference['sha256']
        plan = read(summary['plan_ref']['path'])
        for key in ('script', 'preparation_ref'):
            reference = plan[key]
            files[reference['path']] = reference['sha256']
        root = Path(archive['archive_root'])
        entries = list(root.rglob('*'))
        require(root.is_dir() and not root.is_symlink()
                and all(not path.is_symlink() and (path.is_file() or path.is_dir()) for path in entries)
                and {path.relative_to(root).as_posix() for path in entries if path.is_file()}
                == set(archive['files']), 'offline cost archive file roster changed: ' + label)
        for item in archive['files'].values():
            files[item['path']] = item['sha256']
    restoration = refs['width4_restoration_ref']
    files[restoration['path']] = restoration['sha256']


def require_target_choice():
    from aprof_runtime.task_window_timing import choose_task_repeat
    sample = {'kind': 'pilot_sample', 'role': 'baseline', 'implementation': 'baseline',
              'calls': 100, 'task_duration_total_ns_decimal': '1000000'}
    choice = choose_task_repeat({'mode': 'pilot', 'metric': 'msprof.op_summary.Task_Duration',
        'repeat': 100, 'pilot_samples_task_total_ns_decimal': ['1000000'] * 3,
        'groups': [dict(sample) for _ in range(3)]})
    require(choice['target_ms'] == TARGET_MS and choice['repeat'] == 1000,
            'Task-window runtime calibration target differs from fixed 10 ms')


def config_for(output, operator, profiler):
    config = deepcopy(read(PREDECESSOR / operator / 'config.json'))
    require(config['expected_case_ids'] == list(range(1, 21))
            and config['build']['binary'] == str(PREDECESSOR / operator / 'source/build' / operator), 'original full-case binary required')
    config.update(run_id=output.name, session_id=output.name + '-' + operator,
                  task_profile={'profiler': str(profiler),
                                'scratch_root': str(Path('/tmp') / f'aprof-task-{output.name}-{operator}'),
                                'role_kernel_names': {
                      role: [operator + '_kernel'] for role in ('baseline', 'candidate')}})
    source, _ = source_identity(NATIVE_SOURCES, operator)
    config['build']['source_dir'] = str(source)
    config['build']['binary'] = str(source / 'build' / operator)
    config['build']['receipt_files'] += [str(NATIVE_SOURCES / operator / name)
        for name in ('source-review.json', 'build-receipt.json')]
    for case in config['cases']:
        case['command'][0] = config['build']['binary']
    return config


def local_confirmation_dir(output, operator):
    """Frozen native work directory; source data stays local during the timed job."""
    require(operator in ('exp', 'sigmoid'), 'unknown local confirmation operator')
    return Path('/tmp') / f'aprof-task-window-{Path(output).name}-{operator}-work'


def prepare(output, history):
    output = Path(output).resolve()
    require(output.name == PLANNED_OUTPUT_NAME and not output.exists(),
            'v4 local qualification requires its fresh, distinct output directory; no resume')
    history = Path(history).resolve(strict=True)
    history_value = read(history)
    require(history == HISTORY and history_value['purpose'] == 'retained_history_for_task_window_method_qualification'
            and history_value['protocol'] == HISTORICAL_PROTOCOL, 'local Task qualification history differs')
    history = binding(history); profiler = Path(shutil.which('msprof')).resolve(strict=True)
    cost_evidence = read(COST_EVIDENCE)
    require(cost_evidence['schema_version'] == 1
            and cost_evidence['purpose'] == 'offline_profile_storage_cost_evidence'
            and cost_evidence['eligible_for_publication'] is False, 'storage cost evidence is not offline-only')
    from replay_task_window_failure import replay_task_window_failure
    failure = replay_task_window_failure(failed_attempt_ref())
    require(failure['valid'] is True and failure['accepted'] is False
            and failure['eligible_for_publication'] is False
            and failure['complete_method_qualification'] is False
            and failure['measurement_admission_replayed'] is False,
            'prior failed Task-window attempt did not replay as historical failure')
    replay_failed_attempt_v2(failed_attempt_v2_ref())
    source_ref, package_ref, cost_ref = design_source_ref(), design_package_ref(), verify_cost_summary()
    offline_cost_refs = offline_cost_studies_ref()
    output.mkdir(parents=True); save_new(output / 'prepare-started.json', {'at': time.time(), 'history': history})
    old_plan = read(PREDECESSOR / 'plan.json')
    old = old_plan['frozen_files'] | read(PREDECESSOR / 'freeze.json')['frozen_files']
    original = {}; configs = {}
    for op in ('exp', 'sigmoid'):
        config = config_for(output, op, profiler); configs[op] = str(output / op / 'config.json')
        require(not Path(config['task_profile']['scratch_root']).exists(),
                'local scratch must be created only by the collector')
        require(not local_confirmation_dir(output, op).exists(),
                'local work must be created only by the collector')
        _, native_files = source_identity(NATIVE_SOURCES, op)
        original.update(native_files)
        old_config = read(PREDECESSOR / op / 'config.json')
        source = Path(old_config['build']['source_dir'])
        original_source = Path(old_plan['operators'][op]['original_source'])
        paths = [Path(old_config['build']['binary']), *[source / name for name in source_files(source)],
                 *[original_source / name for name in source_files(original_source)],
                 *map(Path, old_config['build']['receipt_files']),
                 *[Path(p) for c in config['cases'] for p in c['prepared_files']]]
        for path in paths:
            require(str(path) in old, 'original source/input missing from old freeze: ' + str(path))
            original[str(path)] = 'sha256:' + old[str(path)].removeprefix('sha256:')
        save_new(Path(configs[op]), config)
    (output / 'commands.txt').write_text('\n'.join(protocol_commands()) + '\n')
    save_new(output / 'plan.json', {'schema_version': 1, 'purpose': PURPOSE, 'protocol': PROTOCOL,
        'historical_protocol': HISTORICAL_PROTOCOL, 'calibration_target_ms': TARGET_MS,
        'created_at': time.time(), 'history': history, 'storage_cost_evidence': binding(COST_EVIDENCE),
        'failed_attempt_ref': failed_attempt_ref(),
        'failed_attempt_v2_ref': failed_attempt_v2_ref(),
        'pre_change_scaffolding_ref': source_ref, 'pre_change_package_ref': package_ref,
        'fixed_cost_summary_ref': cost_ref, 'offline_cost_studies': offline_cost_refs,
        'original_files': original, 'configs': configs,
        'native_source_root': str(NATIVE_SOURCES),
        'operators': deepcopy(old_plan['operators']), 'frozen_files': {p: h.removeprefix('sha256:') for p, h in original.items()},
        'interpreter': binding(Path(sys.executable).resolve(strict=True)),
        'observations': OBSERVATIONS, 'budgets': BUDGETS, 'profiler': binding(profiler),
        'commands': binding(output / 'commands.txt'), 'max_attempts': 1, 'resampling': 'none', 'publication_acceptance': False})
    return binding(output / 'plan.json')


def roster_slots(output, plan):
    slots = []
    for op in ('exp', 'sigmoid'):
        previous = None
        entries = [('confirmation', None, None), *[('observation', case, order) for case, order in OBSERVATIONS[op]]]
        for kind, case, order in entries:
            slot_id = op + '-confirmation' if kind == 'confirmation' else f'{op}-observation-{case:02d}'
            argv = [plan['interpreter']['path'], str(COLLECTOR), '--config', plan['configs'][op],
                    '--output', str(local_confirmation_dir(output, op)),
                    '--timeout-seconds', str(BUDGETS[kind])] if kind == 'confirmation' else [
                    plan['interpreter']['path'], str(Path(__file__).resolve()), 'observe', '--output', str(output), '--operator', op, '--case-id', str(case)]
            job = {'job_id': slot_id, 'argv': argv, 'cwd': str(output), 'output_dir': str(output / 'campaign' / slot_id / 'job'),
                   'timeout_seconds': BUDGETS[kind], 'environment': BASE_ENVIRONMENT}
            slots.append({'slot_id': slot_id, 'kind': kind, 'operator': op, 'case_id': case, 'order': order,
                          'output_dir': str(local_confirmation_dir(output, op)) if kind == 'confirmation' else str(output / 'observations' / slot_id),
                          'prerequisite_slot': previous, 'job': job}); previous = slot_id
    return slots


def freeze(output):
    output = Path(output).resolve(strict=True)
    require(output.name == PLANNED_OUTPUT_NAME and not (output / 'freeze.json').exists(),
            'v4 local qualification must be frozen once in its distinct output directory')
    plan = read(output / 'plan.json'); collector, _, _, _ = task_modules()
    require(collector.PROTOCOL == PROTOCOL, 'Task-window collector protocol differs')
    require_target_choice()
    require(digest(RELEASE / collector.HEADER_ASSET) == digest(HEADER), 'packaged native header differs')
    require(plan['operators'] == read(PREDECESSOR / 'plan.json')['operators'] and plan['budgets'] == BUDGETS
            and plan.get('historical_protocol') == HISTORICAL_PROTOCOL
            and plan['history'] == binding(HISTORY) and read(HISTORY)['protocol'] == HISTORICAL_PROTOCOL
            and plan.get('calibration_target_ms') == TARGET_MS
            and plan['native_source_root'] == str(NATIVE_SOURCES),
            'mechanical source mapping or budget differs')
    files = dict(plan['original_files']); files[plan['history']['path']] = plan['history']['sha256']
    require(plan['storage_cost_evidence'] == binding(COST_EVIDENCE), 'storage cost provenance changed')
    files[str(COST_EVIDENCE)] = plan['storage_cost_evidence']['sha256']
    require(plan.get('failed_attempt_ref') == failed_attempt_ref(), 'prior failure leaf reference differs')
    files[str(FAILED_ATTEMPT_LEAF)] = FAILED_ATTEMPT_SHA256
    v2_failure_ref = failed_attempt_v2_ref()
    require(plan.get('failed_attempt_v2_ref') == v2_failure_ref,
            'failed v2 attempt leaf was not preregistered')
    files[v2_failure_ref['path']] = v2_failure_ref['sha256']
    v2_leaf_source = read(V2_FAILURE_LEAF)['leaf_source_ref']
    require(v2_leaf_source == binding(V2_FAILURE_DIR / 'replay_task_window_v2_failure.py'),
            'failed v2 replay source differs')
    files[v2_leaf_source['path']] = v2_leaf_source['sha256']
    require(plan.get('pre_change_scaffolding_ref') == design_source_ref(),
            'Task-window pre-change design source differs')
    files[str(PRE_CHANGE_SCAFFOLDING)] = PRE_CHANGE_SCAFFOLDING_SHA256
    for item in read(PRE_CHANGE_SCAFFOLDING)['files'].values():
        files[item['archive_path']] = item['sha256']
    require(plan.get('pre_change_package_ref') == design_package_ref(),
            'Task-window pre-change package archive differs')
    files[str(PRE_CHANGE_PACKAGE)] = PRE_CHANGE_PACKAGE_SHA256
    for item in read(PRE_CHANGE_PACKAGE)['files'].values():
        files[item['path']] = item['sha256']
    require(plan.get('fixed_cost_summary_ref') == cost_summary_ref(),
            'Task-window fixed cost summary reference differs')
    files[str(COST_SUMMARY)] = COST_SUMMARY_SHA256
    bind_offline_cost_studies(files, plan.get('offline_cost_studies'))
    leaf_source = read(FAILED_ATTEMPT_LEAF)['leaf_source_ref']
    require(leaf_source == binding(Path(__file__).with_name('replay_task_window_failure.py')),
            'prior failure leaf replayer source differs')

    from replay_profile_storage_cost import Evidence as CostEvidence, resolve_fixed_cost_source
    cost_reader = CostEvidence()

    def bind_cost_references(value):
        if isinstance(value, dict):
            if set(value) == {'path', 'sha256'}:
                source = resolve_fixed_cost_source(value, cost_reader)
                require(cost_reader.hash(source) == value['sha256'], 'storage cost reference changed')
                files[str(source)] = value['sha256']
            else:
                for item in value.values(): bind_cost_references(item)
        elif isinstance(value, list):
            for item in value: bind_cost_references(item)

    bind_cost_references(read(COST_EVIDENCE))
    for op, path in plan['configs'].items():
        config = collector.config_value(read(path))
        require(config == config_for(output, op, Path(plan['profiler']['path'])), 'original case/config contract changed')
        require(not Path(config['task_profile']['scratch_root']).exists(),
                'local scratch exists before collector launch')
        require(not local_confirmation_dir(output, op).exists(),
                'local confirmation work exists before collector launch')
        actual = collector.inventory(config)['files']
        require(all(actual.get(p, h) == h for p, h in plan['original_files'].items()), 'original native/input identity changed')
        files.update(actual); files[path] = digest(path)
    sources = [RELEASE / name for name in collector.PRODUCER_FILES]
    sources += [Path(__file__), *[Path(__file__).with_name(name) for name in (
        'run_aprof_job.py', 'run_shared_timing_confirmation.py', 'replay_timing_diagnosis.py',
        'qualify_shared_timing_v051.py', 'diagnose_task_duration.py', 'replay_task_measurement_history.py',
        'measurement_source_archive.py', 'replay_measurement_transition.py', 'run_event_duration_study.py',
        'replay_task_cancellation.py', 'probe_native_task_profile.py', 'task_profile_native.py',
        'replay_task_sampling_window_history.py', 'replay_task_window_method_history.py',
        'replay_offline_task_export.py', 'replay_local_task_history_supplement.py',
        'replay_task_local_cancellation.py', 'diagnose_task_sampling_window.py',
        'diagnose_exp_case1_prewarm.py', 'qualify_task_timing_v051.py',
        'replay_profile_storage_cost.py', 'replay_task_window_failure.py',
        'archive_local_evidence.py')],
        ROOT / 'scaffolding/benchmarks/cannbench/harness/device_task_profile.h',
        ROOT / 'scaffolding/tools/verify_measurement_publication.py',
        ROOT / 'scaffolding/tools/verify_task_window_publication.py',
        ROOT / 'scaffolding/tools/release_skill_lib.py']
    files.update({str(p): digest(p) for p in sources})
    files[str(output / 'plan.json')] = digest(output / 'plan.json'); files[plan['commands']['path']] = plan['commands']['sha256']
    files[plan['interpreter']['path']] = plan['interpreter']['sha256']
    for path, expected in files.items(): require(digest(path) == expected, 'freeze identity changed: ' + path)
    save_new(output / 'candidate-inventory.json', {'schema_version': 1, 'root': str(RELEASE), 'files': release_inventory()})
    files[str(output / 'candidate-inventory.json')] = digest(output / 'candidate-inventory.json')
    save_new(output / 'freeze.json', {'schema_version': 1, 'created_at': time.time(), 'plan': binding(output / 'plan.json'),
        'candidate_inventory': binding(output / 'candidate-inventory.json'), 'frozen_files': files, 'configs': plan['configs']})
    save_new(output / 'roster.json', {'schema_version': 1, 'purpose': PURPOSE, 'created_at': time.time(),
        'qualification_dir': str(output), 'freeze': binding(output / 'freeze.json'), 'slots': roster_slots(output, plan),
        'max_attempts': 1, 'resampling': 'none', 'timeout_seconds': BUDGETS['campaign']})
    return {'freeze': binding(output / 'freeze.json'), 'roster': binding(output / 'roster.json')}


def load_plan(output):
    output = Path(output).resolve(strict=True)
    return output, read(output / 'plan.json')


def checked_plan(output, evidence=None):
    output = Path(output).resolve(strict=True); evidence = evidence or Evidence()
    plan = evidence.json(output / 'plan.json'); freeze = evidence.json(output / 'freeze.json')
    require(output.name == PLANNED_OUTPUT_NAME and plan['purpose'] == PURPOSE
            and plan['protocol'] == PROTOCOL and plan['budgets'] == BUDGETS
            and plan.get('historical_protocol') == HISTORICAL_PROTOCOL
            and plan['history'] == binding(HISTORY) and read(HISTORY)['protocol'] == HISTORICAL_PROTOCOL
            and plan.get('calibration_target_ms') == TARGET_MS
            and plan['observations'] == {op: [[case, order] for case, order in rows] for op, rows in OBSERVATIONS.items()}
            and plan['max_attempts'] == 1 and plan['resampling'] == 'none'
            and freeze['plan'] == binding(output / 'plan.json'), 'frozen Task plan differs')
    require(plan['storage_cost_evidence'] == binding(COST_EVIDENCE), 'storage cost provenance differs')
    require(plan.get('failed_attempt_ref') == failed_attempt_ref()
            and freeze['frozen_files'].get(str(FAILED_ATTEMPT_LEAF)) == FAILED_ATTEMPT_SHA256
            and freeze['frozen_files'].get(str(Path(__file__).with_name('replay_task_window_failure.py')))
            == read(FAILED_ATTEMPT_LEAF)['leaf_source_ref']['sha256'],
            'prior failed Task-window attempt is not frozen')
    v2_failure_ref = failed_attempt_v2_ref()
    v2_leaf_source = read(V2_FAILURE_LEAF)['leaf_source_ref']
    require(plan.get('failed_attempt_v2_ref') == v2_failure_ref
            and freeze['frozen_files'].get(v2_failure_ref['path']) == v2_failure_ref['sha256']
            and v2_leaf_source == binding(V2_FAILURE_DIR / 'replay_task_window_v2_failure.py')
            and freeze['frozen_files'].get(v2_leaf_source['path']) == v2_leaf_source['sha256'],
            'failed v2 attempt leaf/source is not frozen')
    require(plan.get('pre_change_scaffolding_ref') == design_source_ref()
            and freeze['frozen_files'].get(str(PRE_CHANGE_SCAFFOLDING)) == PRE_CHANGE_SCAFFOLDING_SHA256,
            'Task-window pre-change design source is not frozen')
    require(plan.get('pre_change_package_ref') == design_package_ref()
            and freeze['frozen_files'].get(str(PRE_CHANGE_PACKAGE)) == PRE_CHANGE_PACKAGE_SHA256,
            'Task-window pre-change package is not frozen')
    require(plan.get('fixed_cost_summary_ref') == cost_summary_ref()
            and freeze['frozen_files'].get(str(COST_SUMMARY)) == COST_SUMMARY_SHA256,
            'Task-window fixed cost design is not frozen')
    cost_refs = offline_cost_studies_ref()
    require(plan.get('offline_cost_studies') == cost_refs
            and freeze['frozen_files'].get(cost_refs['width4_restoration_ref']['path'])
            == cost_refs['width4_restoration_ref']['sha256']
            and all(freeze['frozen_files'].get(item[key]['path']) == item[key]['sha256']
                    for name, item in cost_refs.items() if name in OFFLINE_COST_STUDIES
                    for key in ('summary_ref', 'source_archive_ref')),
            'offline cost studies or width4 restoration are not frozen')
    require(plan['frozen_files'] == {p: h.removeprefix('sha256:') for p, h in plan['original_files'].items()}
            and freeze['configs'] == plan['configs'], 'native inventory/config aliases differ')
    for path, expected in freeze['frozen_files'].items(): evidence.bind(path, expected)
    candidate = evidence.json(output / 'candidate-inventory.json')
    require(freeze['candidate_inventory'] == binding(output / 'candidate-inventory.json')
            and candidate == {'schema_version': 1, 'root': str(RELEASE), 'files': release_inventory()}, 'candidate payload changed after freeze')
    return plan, freeze


def _full_admission_reader(reader, reference, config):
    from aprof_runtime.measurement_entry import replay_current_measurement_admission
    completion = json.loads(reader.verify_artifact(reference).read_text())
    proof = json.loads(reader.verify_artifact(completion['proof_ref']).read_text())
    require(completion['status'] == 'passed'
            and config['expected_case_ids'] == list(range(1, 21))
            and proof['source_hashes']['baseline'] == proof['source_hashes']['candidate'],
            'full identical-source A/A completion required')
    result = replay_current_measurement_admission(reader, reference, expected={
        **{key: config[key] for key in ('operator', 'run_id', 'session_id', 'candidate_id')},
        'source_hashes': proof['source_hashes'], 'measurement_report_ref': completion['measurement_report_ref']})
    require(result['valid'] and result['report']['stable'], 'full Task runtime admission failed')
    for case in result['report']['controls']:
        for controls in [case['overall'], *case['cycles']]: check_controls(controls)
    return result


def full_admission(output, operator, *, archived=None):
    from aprof_runtime.local_evidence import LocalEvidence
    config = read(output / operator / 'config.json'); folder = local_confirmation_dir(output, operator)
    if archived is not None:
        path = Path(archived['store'])
        with contextlib.closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as connection:
            from aprof_runtime.store import _ReadOnlyArtifacts, default_object_directory
            connection.execute('BEGIN')
            reader = _ReadOnlyArtifacts(connection, default_object_directory(path))
            return _full_admission_reader(reader, archived['completion_ref'], config)
    completion = read(folder / 'local-result.json')
    proof = read(folder / 'measurement-proof.json'); refs = read(folder / 'artifacts.json')
    require(completion['status'] == 'passed' and completion['proof_ref'] == digest(folder / 'measurement-proof.json')
            and refs == {'measurement_admission': digest(folder / 'local-result.json'),
                         'measurement_report': completion['measurement_report_ref']},
            'local measurement completion/proof binding differs')
    reader = LocalEvidence.from_index(folder / 'local-evidence-index.json')
    return _full_admission_reader(reader, refs['measurement_admission'], config)


def run(roster_path, anchor):
    clean_parent_environment()
    roster_path = Path(roster_path).resolve(strict=True); roster = read(roster_path)
    output = Path(roster['qualification_dir']); plan, _ = checked_plan(output); a = read(anchor)
    require(roster['slots'] == roster_slots(output, plan) and a == {'schema_version': 1, 'purpose': PURPOSE,
        'roster': binding(roster_path), 'max_attempts': 1, 'resampling': 'none', 'recorded_at_utc': a['recorded_at_utc']}
        and Path(anchor).resolve().parent == ROOT / 'scaffolding/curation'
        and roster['created_at'] <= datetime.fromisoformat(a['recorded_at_utc']).timestamp() <= time.time(), 'root roster anchor differs')
    campaign = output / 'campaign'; campaign.mkdir(exist_ok=False)
    save_new(campaign / 'started.json', {'at': time.time(), 'roster': binding(roster_path), 'anchor': binding(anchor)})
    terminals = {}
    with locks(['host-serial.lock', *[f'device-{i}.lock' for i in range(1, 16)]]):
        for slot in roster['slots']:
            folder = campaign / slot['slot_id']; folder.mkdir(); prior = slot['prerequisite_slot']
            terminal = {'slot_id': slot['slot_id'], 'kind': slot['kind'], 'operator': slot['operator'], 'status': 'not_run'}
            if prior and terminals[prior]['status'] != 'passed':
                terminal['prerequisite_ref'] = binding(campaign / prior / 'terminal.json')
            else:
                save_new(folder / 'started.json', {'at': time.time(), 'slot': slot})
                terminal.update(status='failed', started=binding(folder / 'started.json'))
                try:
                    execution = job_run(slot['job']); terminal['execution'] = binding(folder / 'job/execution.json')
                    require(execution['exit_code'] == 0 and execution['status'] == 'passed',
                            'qualification slot failed')
                    require(time.time() - read(folder / 'started.json')['at'] <= BUDGETS[slot['kind']],
                            'online qualification exceeded slot budget')
                    completion = (local_confirmation_dir(output, slot['operator']) / 'local-result.json'
                                  if slot['kind'] == 'confirmation'
                                  else Path(slot['output_dir']) / 'terminal.json')
                    online = read(completion)
                    execution_started = datetime.fromisoformat(execution['started_at']).timestamp()
                    execution_finished = datetime.fromisoformat(execution['finished_at']).timestamp()
                    require(read(folder / 'started.json')['at'] <= execution_started <= execution_finished <= time.time(),
                            'slot process outside its actual online interval')
                    online_started = (online['started_at'] if slot['kind'] == 'confirmation'
                                      else read(Path(slot['output_dir']) / 'started.json')['at'])
                    require(execution_started <= online_started <= online['finished_at'] <= execution_finished,
                            'online completion outside its actual slot process')
                    require((online['status'] == 'passed' if slot['kind'] == 'confirmation'
                             else online['complete'] is True), 'online verification did not complete')
                    if slot['kind'] == 'confirmation':
                        require(not (completion.parent / 'local-failure.json').exists()
                                and online['error'] is None
                                and 0 < online['elapsed_seconds'] <= online['timeout_seconds'] == BUDGETS[slot['kind']],
                                'online completion status, deadline, or finalization differs')
                    terminal.update(status='passed', online_completion=binding(completion))
                except Exception as error:
                    terminal['error'] = {'type': type(error).__name__, 'message': str(error)}
                    if (folder / 'job/execution.json').exists(): terminal['execution'] = binding(folder / 'job/execution.json')
            terminal['finished_at'] = time.time()
            if (terminal['status'] == 'passed'
                    and terminal['finished_at'] - read(folder / 'started.json')['at'] > BUDGETS[slot['kind']]):
                terminal.update(status='failed', error={'type': 'TimeoutError', 'message': 'online slot exceeded budget'})
            save_new(folder / 'terminal.json', terminal); terminals[slot['slot_id']] = terminal
            print(json.dumps({'slot': slot['slot_id'], 'status': terminal['status']}), flush=True)
    result = {'roster': binding(roster_path), 'slots': {name: binding(campaign / name / 'terminal.json') for name in terminals},
              'accepted': all(row['status'] == 'passed' for row in terminals.values()), 'authority': 'method_qualification_only_no_publication', 'resampling': 'none'}
    save_new(campaign / 'campaign.json', result); return result


def slot_report(output, slot):
    return output / 'campaign' / slot['slot_id'] / 'replay.json' if slot['kind'] == 'confirmation' else Path(slot['output_dir']) / 'observation-report.json'


def slot_replay_job(output, plan, slot, timeout):
    """Post-task independent audit only; never included in an online slot job."""
    require(0 < timeout <= BUDGETS[slot['kind']], 'invalid replay remaining budget')
    argv = [plan['interpreter']['path'], str(Path(__file__).resolve()), 'replay-slot',
            '--output', str(output), '--operator', slot['operator'], '--kind', slot['kind']]
    if slot['kind'] == 'observation': argv += ['--case-id', str(slot['case_id'])]
    return {'job_id': slot['slot_id'] + '-replay', 'argv': argv, 'cwd': str(output),
            'output_dir': str(output / 'campaign' / slot['slot_id'] / 'replay-job'),
            'timeout_seconds': timeout, 'environment': BASE_ENVIRONMENT}


def replay_slot(output, operator, kind, case_id):
    output = Path(output).resolve(strict=True)
    plan, _ = checked_plan(output)
    slots = [s for s in roster_slots(output, plan) if s['operator'] == operator and s['kind'] == kind and s['case_id'] == case_id]
    require(len(slots) == 1, 'replay slot outside frozen roster')
    slot = slots[0]
    result = full_admission(output, operator) if kind == 'confirmation' else replay_task_observation(
        Path(slot['output_dir']), qualification_dir=output, operator=operator, case_id=case_id)
    save_new(slot_report(output, slot), result)
    return {'slot': slot['slot_id'], 'replay': binding(slot_report(output, slot))}


def observation_repeat(directory, config, *, archived=None):
    qualification = directory.parents[2]
    if archived is None:
        folder = local_confirmation_dir(qualification, config['operator'])
        registration = read(folder / 'registration.json')
        calibration = read(folder / 'calibration.json')
        require(registration['calibration_ref'] == digest(folder / 'calibration.json'),
                'observation calibration differs')
    else:
        from aprof_runtime.store import _ReadOnlyArtifacts, default_object_directory
        path = Path(archived['store'])
        with contextlib.closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as connection:
            connection.execute('BEGIN')
            reader = _ReadOnlyArtifacts(connection, default_object_directory(path))
            completion = json.loads(reader.verify_artifact(archived['completion_ref']).read_text())
            proof = json.loads(reader.verify_artifact(completion['proof_ref']).read_text())
            registration = json.loads(reader.verify_artifact(proof['registration_ref']).read_text())
            calibration = json.loads(reader.verify_artifact(registration['calibration_ref']).read_text())
            require(proof['operator'] == config['operator'], 'archived observation operator differs')
    case_id = int(directory.parent.name.rsplit('-', 1)[1])
    rows = [item for item in calibration['cases'] if item['case_id'] == case_id]
    require(len(rows) == 1 and type(rows[0]['repeat']) is int
            and 100 <= rows[0]['repeat'] <= 100000 and rows[0]['repeat'] % 100 == 0
            and registration['repeat_by_case'][str(case_id)] == rows[0]['repeat'], 'frozen Task repeat differs')
    return rows[0]['repeat']


def observation_job(output, config, case, mode, *, archived=None):
    argv = [x.replace('{cycle_dir}', str(output)) for x in case['command']]
    env = dict(BASE_ENVIRONMENT, APROF_SHARED_TIMING='1', APROF_SHARED_CYCLE='0', APROF_SHARED_MODE='confirmation',
               APROF_SHARED_REPEAT=str(observation_repeat(output, config, archived=archived)),
               APROF_SHARED_COMMANDS=str(output.parents[2] / 'commands.txt'))
    if mode == 'profiled':
        env['APROF_TASK_PROFILE_DIR'] = str(observation_profile_path(output, config))
    return {'job_id': output.parent.name + '-' + mode, 'argv': argv, 'cwd': config['build']['source_dir'],
            'output_dir': str(output / 'job'), 'timeout_seconds': 600 if mode == 'profiled' else 120, 'environment': env}


def observation_export_job(directory, config, job, profile_root):
    collector, _, _, _ = task_modules()
    return dict(job, job_id=job['job_id'] + '-export', output_dir=str(directory / 'export-job'),
                timeout_seconds=300, argv=collector.export_argv(config, profile_root))


def profile_inventory(directory):
    files = {}
    for path in directory.rglob('*'):
        require(not path.is_symlink(), 'profile symlink rejected')
        if path.is_file(): files[str(path)] = digest(path)
    require(files, 'empty profile inventory')
    return files


def observation_profile_path(directory, config):
    return Path(config['task_profile']['scratch_root']) / 'observations' / directory.parent.name / 'profile'


def checked_scratch_root(config):
    scratch = Path(config['task_profile']['scratch_root'])
    require(scratch.is_absolute() and scratch.resolve() == scratch and not scratch.is_symlink()
            and scratch.is_dir() and scratch.stat().st_mode & 0o777 == 0o700,
            'collector scratch root is missing or replaced')
    return scratch


def relative_profile_inventory(directory):
    return {Path(path).relative_to(directory).as_posix(): expected
            for path, expected in profile_inventory(directory).items()}


def replay_profile_transfer(directory, config, receipt, online_finished, evidence):
    """Audit a separate trace collector copy after the online observation ended."""
    persisted = directory / 'profile'
    require(persisted.is_dir() and not persisted.is_symlink(), 'persisted observation profile missing')
    transfer_path = directory / 'profile-transfer.json'
    archive_path = directory / 'post-task-archive.json'
    transfer, archive = evidence.json(transfer_path), evidence.json(archive_path)
    relative = relative_profile_inventory(persisted)
    source = observation_profile_path(directory, config)
    original = {Path(path).relative_to(source).as_posix(): value
                for path, value in receipt['profile_files'].items()}
    require(set(transfer) == {'source_dir', 'destination_dir', 'started_at', 'finished_at',
                                  'source_inventory', 'persisted_inventory', 'source_after_inventory'}
            and transfer['source_dir'] == str(source)
            and transfer['destination_dir'] == str(persisted)
            and transfer['source_inventory'] == transfer['source_after_inventory'] ==
                transfer['persisted_inventory'] == relative == original
            and set(archive) == {'schema_version', 'owner', 'cost_scope', 'admission_authority',
                                 'online_terminal_ref', 'transfer_ref', 'started_at', 'finished_at',
                                 'elapsed_seconds'}
            and archive['schema_version'] == 1 and archive['owner'] == 'trace_collection'
            and archive['cost_scope'] == 'post_task_archive' and archive['admission_authority'] is False
            and archive['online_terminal_ref'] == binding(directory.parent / 'terminal.json')
            and archive['transfer_ref'] == binding(transfer_path)
            and online_finished <= archive['started_at'] <= transfer['started_at']
            <= transfer['finished_at'] <= archive['finished_at']
            and 0 < archive['elapsed_seconds'] <= 1200,
            'observation post-task profile archive differs')
    return persisted


def collection_log(name):
    return re.fullmatch(r'PROF_[^/]+/mindstudio_profiler_log/collection_(?:host|device_[0-9]+)\.log', name) is not None


def replay_captured_profile(directory, profile_root, receipt, evidence, *, online_root=None):
    online_root = online_root or profile_root
    captured, copies = receipt['capture_profile_files'], receipt['capture_log_copies']
    require(isinstance(captured, dict) and captured and isinstance(copies, dict)
            and set(copies) == {name for name in captured if collection_log(name)}, 'captured profile/log roster differs')
    require(not any(Path(name).name.startswith('op_summary') and name.endswith('.csv') for name in captured),
            'native capture unexpectedly contains an exported table')
    for relative, before_hash in captured.items():
        part = Path(relative)
        require(not part.is_absolute() and str(part) == relative and '..' not in part.parts, 'captured path escaped')
        path = profile_root / part
        require(str(online_root / part) in receipt['profile_files'], 'export removed captured file')
        if collection_log(relative):
            original = directory / 'capture-logs' / part
            require(copies[relative] == binding(original) and digest(original) == before_hash, 'original log copy differs')
            evidence.bind(original, before_hash)
            require(path.read_bytes().startswith(original.read_bytes()), 'export rewrote or truncated collection log')
        else:
            evidence.bind(path, before_hash)


def observation_mode(directory, config, case, mode, *, deadline=None):
    directory.mkdir(); job = observation_job(directory, config, case, mode)
    receipt = {'mode': mode, 'started_at': time.time(), 'argv': [x.replace('{cycle_dir}', str(directory)) for x in case['command']],
               'status': 'failed', 'verifications': {}}
    try:
        if mode == 'profiled':
            local_profile = observation_profile_path(directory, config)
            checked_scratch_root(config)
            require(local_profile.resolve() == local_profile and not local_profile.exists()
                    and not local_profile.is_symlink(), 'observation local profile path is not fresh')
            local_profile.mkdir(parents=True, exist_ok=False)
        execution = job_run(job); receipt['execution'] = binding(directory / 'job/execution.json')
        require(execution['exit_code'] == 0, 'observation capture failed')
        shutil.copyfile(directory / 'job/stdout.log', directory / 'stdout.log')
        messages = native_messages(directory / 'stdout.log'); repeat = observation_repeat(directory, config)
        timeline_protocol(messages, config, repeat)
        if mode == 'profiled':
            require(local_profile.is_dir() and not local_profile.is_symlink()
                    and local_profile.resolve() == local_profile, 'observation local profile is missing or replaced')
            require(not list(local_profile.rglob('op_summary*.csv')), 'native capture unexpectedly exported summaries')
            receipt['capture_profile_files'] = relative_profile_inventory(local_profile)
            receipt['capture_log_copies'] = {}
            for relative in receipt['capture_profile_files']:
                if collection_log(relative):
                    target = directory / 'capture-logs' / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(local_profile / relative, target)
                    receipt['capture_log_copies'][relative] = binding(target)
            roots = list(local_profile.glob('PROF_*')); require(len(roots) == 1, 'ambiguous profile root')
            export = observation_export_job(directory, config, job, roots[0])
            require(job_run(export)['exit_code'] == 0, 'observation export failed')
            tables = list(local_profile.rglob('op_summary*.csv')); require(len(tables) == 1, 'unique task table required')
            _, _, partition, controls = task_modules()
            receipt['profile_files'] = profile_inventory(local_profile); receipt['table'] = binding(tables[0])
            replay_captured_profile(directory, local_profile, receipt, Evidence())
        for role in ('baseline', 'candidate'): receipt['verifications'][role] = oracle(directory, role, case, config['build']['source_dir'])
        receipt['finished_at'] = time.time()
        for role in ('baseline', 'candidate'): production_oracle(directory, role, case, receipt, Evidence())
        if mode == 'profiled':
            result = partition(tables[0], messages, config=config, mode='confirmation', cycle=0, repeat=repeat,
                               role_kernel_names=config['task_profile']['role_kernel_names'])
            save_new(directory / 'partition.json', result); receipt['partition'] = binding(directory / 'partition.json')
            receipt['task_controls'] = controls(result['values_ns_per_call']); check_controls(receipt['task_controls'])
        receipt['status'] = 'passed'
    except BaseException as error:
        receipt['error'] = {'type': type(error).__name__, 'message': str(error)}
    finally:
        for role in ('baseline', 'candidate'):
            path = directory / f'{role}-verify-receipt.json'
            if path.exists(): receipt['verifications'][role] = read(path)
        if (directory / 'job/execution.json').exists(): receipt['execution'] = binding(directory / 'job/execution.json')
        receipt['finished_at'] = time.time(); save_new(directory / 'receipt.json', receipt)
    return receipt


def observe(output, operator, case_id):
    clean_parent_environment()
    output = Path(output).resolve(strict=True); plan, _ = checked_plan(output)
    order = dict(OBSERVATIONS[operator])[case_id]; folder = output / 'observations' / f'{operator}-observation-{case_id:02d}'
    folder.mkdir(parents=True, exist_ok=False); save_new(folder / 'started.json', {'at': time.time(), 'order': order})
    config = read(plan['configs'][operator]); case = next(c for c in config['cases'] if c['case_id'] == case_id)
    checked_scratch_root(config)
    deadline = time.monotonic() + BUDGETS['observation']
    modes = {}; failed = False
    with locks(['device-0.lock']):
        for mode in order:
            if failed:
                save_new(folder / (mode + '-not-run.json'), {'status': 'not_run', 'prerequisite': binding(folder / order[0] / 'receipt.json')})
                modes[mode] = {'status': 'not_run', 'receipt': binding(folder / (mode + '-not-run.json'))}
            else:
                result = observation_mode(folder / mode, config, case, mode, deadline=deadline); failed = result['status'] != 'passed'
                modes[mode] = {'status': result['status'], 'receipt': binding(folder / mode / 'receipt.json')}
    result = {'order': order, 'modes': modes, 'complete': not failed, 'finished_at': time.time(), 'publication_acceptance': False}
    save_new(folder / 'terminal.json', result)
    require(not failed, 'paired instrumentation observation failed; no retry')
    return result


def archive_observation(output, operator, case_id):
    """Trace collector action after the online observation terminal; never a roster slot."""
    output = Path(output).resolve(strict=True)
    plan, _ = checked_plan(output)
    require(case_id in dict(OBSERVATIONS[operator]), 'observation outside fixed matrix')
    folder = output / 'observations' / f'{operator}-observation-{case_id:02d}'
    terminal = read(folder / 'terminal.json')
    require(terminal['complete'] is True and terminal['finished_at'] <= time.time(),
            'post-task archive requires a completed observation')
    config = read(plan['configs'][operator]); directory = folder / 'profiled'
    online = read(directory / 'receipt.json')
    require(online['status'] == 'passed' and online['mode'] == 'profiled'
            and 'profile_transfer' not in online and not (directory / 'profile').exists(),
            'online observation cannot contain an earlier profile copy')
    source = observation_profile_path(directory, config)
    require(profile_inventory(source) == online['profile_files'], 'online profile changed before archive')
    started_at, started_monotonic = time.time(), time.monotonic()
    collector, _, _, _ = task_modules()
    transfer = collector.copy_profile_tree(source, directory / 'profile',
        relative_profile_inventory(source), deadline=started_monotonic + 1200)
    save_new(directory / 'profile-transfer.json', transfer)
    receipt = {'schema_version': 1, 'owner': 'trace_collection', 'cost_scope': 'post_task_archive',
               'admission_authority': False, 'online_terminal_ref': binding(folder / 'terminal.json'),
               'transfer_ref': binding(directory / 'profile-transfer.json'), 'started_at': started_at,
               'finished_at': time.time(), 'elapsed_seconds': time.monotonic() - started_monotonic}
    require(terminal['finished_at'] <= started_at and 0 < receipt['elapsed_seconds'] <= 1200,
            'post-task observation archive exceeded its separate budget')
    save_new(directory / 'post-task-archive.json', receipt)
    return binding(directory / 'post-task-archive.json')


def replay_task_observation(output, *, qualification_dir, operator, case_id, post_task=False,
                            archived_confirmation=None):
    output = Path(output).resolve(strict=True); qualification_dir = Path(qualification_dir).resolve(strict=True)
    evidence = Evidence(); plan, _ = checked_plan(qualification_dir, evidence)
    require(output == qualification_dir / 'observations' / f'{operator}-observation-{case_id:02d}', 'observation outside frozen slot')
    terminal = evidence.json(output / 'terminal.json'); started = evidence.json(output / 'started.json')
    require(0 <= terminal['finished_at'] - started['at'] <= BUDGETS['observation'], 'observation total budget exceeded')
    order = dict(OBSERVATIONS[operator])[case_id]
    require(terminal['order'] == started['order'] == order and terminal['complete'] and set(terminal['modes']) == set(order), 'observation incomplete/order differs')
    config = read(plan['configs'][operator]); case = next(c for c in config['cases'] if c['case_id'] == case_id)
    previous = started['at']; messages = {}; partition = None
    for mode in order:
        directory = output / mode; row = terminal['modes'][mode]; receipt = evidence.json(directory / 'receipt.json')
        require(row == {'status': 'passed', 'receipt': binding(directory / 'receipt.json')} and receipt['mode'] == mode
                and receipt['status'] == 'passed' and previous <= receipt['started_at'] <= receipt['finished_at'] <= terminal['finished_at'], 'mode terminal/order differs')
        require(receipt['argv'] == [x.replace('{cycle_dir}', str(directory)) for x in case['command']], 'native command differs')
        job = observation_job(directory, config, case, mode, archived=archived_confirmation)
        execution = evidence.json(directory / 'job/execution.json')
        require(receipt['execution'] == binding(directory / 'job/execution.json'), 'mode execution reference differs')
        end = execution_interval(execution, job, receipt['started_at'], receipt['finished_at'], evidence)
        require(digest(directory / 'stdout.log') == execution['stdout']['sha256'], 'native stdout differs')
        messages[mode] = native_messages(directory / 'stdout.log')
        repeat = observation_repeat(directory, config, archived=archived_confirmation)
        timeline_protocol(messages[mode], config, repeat)
        if (directory / 'export-job/execution.json').exists():
            require(mode == 'profiled', 'unprofiled export is invalid')
            profile_name = Path(receipt['table']['path']).parents[1].name
            require(profile_name.startswith('PROF_'), 'export profile identity differs')
            expected = observation_export_job(directory, config, job, observation_profile_path(directory, config) / profile_name)
            end = execution_interval(evidence.json(directory / 'export-job/execution.json'), expected, end, receipt['finished_at'], evidence)
        if mode == 'profiled':
            require((directory / 'export-job/execution.json').is_file(), 'required independent summary export missing')
            require('profile_transfer' not in receipt, 'profile copy is not an online observation step')
            if post_task:
                profile_root = replay_profile_transfer(directory, config, receipt, terminal['finished_at'], evidence)
            else:
                require(not (directory / 'profile-transfer.json').exists() and not (directory / 'profile').exists(),
                        'profile copy preceded the post-task archive')
                profile_root = observation_profile_path(directory, config)
        else:
            require('profile_transfer' not in receipt and not (directory / 'profile-transfer.json').exists()
                    and not (directory / 'profile').exists(), 'unprofiled observation has profiler artifacts')
        require(set(receipt['verifications']) == {'baseline', 'candidate'}, 'both original oracles required')
        for role in ('baseline', 'candidate'):
            verification = receipt['verifications'][role]
            require(verification == evidence.json(directory / f'{role}-verify-receipt.json') and verification['status'] == 'passed'
                    and end <= verification['started_at'] <= verification['finished_at'] <= receipt['finished_at']
                    and verification['finished_at'] - verification['started_at'] <= 120
                    and verification['output_after_sha256'] == verification['output_sha256'], 'oracle identity/time differs')
            production_oracle(directory, role, case, receipt, evidence); end = verification['finished_at']
        if mode == 'profiled':
            local_profile = observation_profile_path(directory, config)
            actual = profile_inventory(profile_root)
            require({str(local_profile / Path(path).relative_to(profile_root)): value
                     for path, value in actual.items()} == receipt['profile_files'],
                    'complete observation profile differs from online inventory')
            for path, expected in actual.items(): evidence.bind(path, expected)
            replay_captured_profile(directory, profile_root, receipt, evidence, online_root=local_profile)
            tables = list(profile_root.rglob('op_summary*.csv'))
            require(len(tables) == 1 and Path(receipt['table']['path']) ==
                    local_profile / tables[0].relative_to(profile_root)
                    and digest(tables[0]) == receipt['table']['sha256'], 'task table differs')
            _, _, parse, controls = task_modules()
            partition = parse(tables[0], messages[mode], config=config, mode='confirmation', cycle=0, repeat=repeat, role_kernel_names=config['task_profile']['role_kernel_names'])
            quality = controls(partition['values_ns_per_call']); check_controls(quality)
            require(evidence.json(directory / 'partition.json') == partition and binding(directory / 'partition.json') == receipt['partition']
                    and quality == receipt['task_controls'], 'Task partition/control summary differs')
        previous = receipt['finished_at']
    comparison = {}
    for mode in order:
        values = [message[role] for message in messages[mode] if message['kind'] == 'pair' for role in ('baseline', 'candidate')]
        comparison[mode] = {'event_ns_per_call': [v['elapsed_ns'] for v in values],
                           'host_ns_per_call': [(v['finished_monotonic_ns'] - v['started_monotonic_ns']) / repeat for v in values]}
    comparison['ratio_of_means_P_over_U'] = {key: statistics.fmean(comparison['profiled'][key]) / statistics.fmean(comparison['unprofiled'][key]) for key in ('event_ns_per_call', 'host_ns_per_call')}
    comparison['scope'] = 'Event/Host auxiliary only, no threshold; unprofiled Task Duration ground truth is unavailable.'
    return {'complete': True, 'order': order, 'repeat': repeat, 'task_partition': partition, 'task_controls': quality, 'comparison': comparison,
            'post_task_archive': post_task,
            'files': {p: v['sha256'] for p, v in evidence.files.items()}}


def replay_task_campaign(roster_path, *, qualification_dir, archived_confirmations=None):
    output = Path(qualification_dir).resolve(strict=True); roster_path = Path(roster_path).resolve(strict=True)
    archived_confirmations = archived_confirmations or {}
    require(set(archived_confirmations) <= {'exp', 'sigmoid'}, 'unknown post-task archive operator')
    evidence = Evidence(); plan, freeze = checked_plan(output, evidence); roster = evidence.json(roster_path)
    require(roster_path == output / 'roster.json' and roster['qualification_dir'] == str(output)
            and roster['freeze'] == binding(output / 'freeze.json') and roster['slots'] == roster_slots(output, plan)
            and roster['max_attempts'] == 1 and roster['resampling'] == 'none'
            and roster['timeout_seconds'] == BUDGETS['campaign'], 'campaign roster differs')
    directory = output / 'campaign'; started = evidence.json(directory / 'started.json'); campaign = evidence.json(directory / 'campaign.json')
    anchor = evidence.json(started['anchor']['path']); evidence.bind(started['anchor']['path'], started['anchor']['sha256'])
    require(started['roster'] == campaign['roster'] == binding(roster_path) and anchor == {
        'schema_version': 1, 'purpose': PURPOSE, 'roster': binding(roster_path), 'max_attempts': 1,
        'resampling': 'none', 'recorded_at_utc': anchor['recorded_at_utc']}
        and Path(started['anchor']['path']).parent == ROOT / 'scaffolding/curation'
        and freeze['created_at'] <= roster['created_at'] <= datetime.fromisoformat(anchor['recorded_at_utc']).timestamp() <= started['at'],
        'campaign was not independently anchored before execution')
    ids = [slot['slot_id'] for slot in roster['slots']]
    require(set(campaign['slots']) == set(ids) == {p.name for p in directory.iterdir() if p.is_dir()}
            and campaign['resampling'] == 'none', 'unknown or missing campaign slots')
    previous = started['at']; results = {}
    for slot in roster['slots']:
        path = directory / slot['slot_id']; terminal = evidence.json(path / 'terminal.json')
        require(campaign['slots'][slot['slot_id']] == binding(path / 'terminal.json') and all(terminal[k] == slot[k] for k in ('slot_id', 'kind', 'operator')),
                'slot terminal binding differs')
        result = {**{key: terminal[key] for key in ('status', 'kind', 'operator')}, 'terminal': binding(path / 'terminal.json')}
        prior = slot['prerequisite_slot']
        if terminal['status'] == 'not_run':
            require(prior and results[prior]['status'] != 'passed' and terminal['prerequisite_ref'] == binding(directory / prior / 'terminal.json')
                    and not (path / 'started.json').exists() and 'execution' not in terminal, 'not-run prerequisite differs')
        else:
            require(terminal['status'] in ('passed', 'failed') and (not prior or results[prior]['status'] == 'passed'), 'illegal attempted slot')
            entry = evidence.json(path / 'started.json')
            require(entry['slot'] == slot and terminal['started'] == binding(path / 'started.json')
                    and previous <= entry['at'] <= terminal['finished_at'], 'slot order/start differs')
            if 'execution' in terminal:
                execution = evidence.json(path / 'job/execution.json')
                require(terminal['execution'] == binding(path / 'job/execution.json') and execution['job'] == slot['job'], 'actual slot job differs')
                for key in ('stdout', 'stderr'): evidence.bind(execution[key]['path'], execution[key]['sha256'])
                require(entry['at'] <= datetime.fromisoformat(execution['started_at']).timestamp()
                        <= datetime.fromisoformat(execution['finished_at']).timestamp() <= terminal['finished_at'], 'slot execution outside interval')
                result['execution'] = execution
            if terminal['status'] == 'passed':
                require('replay_execution' not in terminal and 'replay' not in terminal,
                        'independent audit was charged to the online slot')
                require(terminal['finished_at'] - entry['at'] <= BUDGETS[slot['kind']],
                        'online qualification exceeded slot budget')
                execution_interval(result['execution'], slot['job'], entry['at'], terminal['finished_at'], evidence)
                online_path = (local_confirmation_dir(output, slot['operator']) / 'local-result.json'
                               if slot['kind'] == 'confirmation' else Path(slot['output_dir']) / 'terminal.json')
                archive = archived_confirmations.get(slot['operator']) if slot['kind'] == 'confirmation' else None
                if archive is None:
                    online = evidence.json(online_path)
                    online_ref = binding(online_path)
                else:
                    from aprof_runtime.store import _ReadOnlyArtifacts, default_object_directory
                    store_path = Path(archive['store'])
                    with contextlib.closing(sqlite3.connect(store_path.as_uri() + '?mode=ro', uri=True)) as connection:
                        connection.execute('BEGIN')
                        reader = _ReadOnlyArtifacts(connection, default_object_directory(store_path))
                        online = json.loads(reader.verify_artifact(archive['completion_ref']).read_text())
                    online_ref = {'path': str(online_path), 'sha256': archive['completion_ref']}
                require(terminal['online_completion'] == online_ref
                        and (online['status'] == 'passed' if slot['kind'] == 'confirmation'
                             else online['complete'] is True),
                        'online completion differs from the registered slot')
                outer_started = datetime.fromisoformat(result['execution']['started_at']).timestamp()
                outer_finished = datetime.fromisoformat(result['execution']['finished_at']).timestamp()
                online_started = (online['started_at'] if slot['kind'] == 'confirmation'
                                  else evidence.json(Path(slot['output_dir']) / 'started.json')['at'])
                require(outer_started <= online_started <= online['finished_at'] <= outer_finished,
                        'online completion outside its actual slot process')
                if archive is not None:
                    require(terminal['finished_at'] <= archive['started_at'],
                            'post-task archive preceded the finished online slot')
                if slot['kind'] == 'observation' and archived_confirmations:
                    archive_receipt = evidence.json(Path(slot['output_dir']) / 'profiled/post-task-archive.json')
                    require(terminal['finished_at'] <= archive_receipt['started_at'],
                            'observation archive preceded the finished online slot')
                result_key = 'admission' if slot['kind'] == 'confirmation' else 'observation'
                result[result_key] = full_admission(output, slot['operator'], archived=archive) if slot['kind'] == 'confirmation' else replay_task_observation(
                    output / 'observations' / slot['slot_id'], qualification_dir=output, operator=slot['operator'],
                    case_id=slot['case_id'], post_task=bool(archived_confirmations),
                    archived_confirmation=archived_confirmations.get(slot['operator']))
        require(previous <= terminal['finished_at'], 'terminal time reversed')
        previous = terminal['finished_at']; results[slot['slot_id']] = result
    require(previous - started['at'] <= BUDGETS['campaign'], 'campaign total budget exceeded')
    accepted = all(row['status'] == 'passed' for row in results.values())
    require(campaign['accepted'] == accepted, 'campaign aggregate differs')
    return {'complete': True, 'accepted': accepted, 'authority': 'method_qualification_only_no_publication',
            'protocol': PROTOCOL, 'slots': results, 'files': {p: v['sha256'] for p, v in evidence.files.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'freeze', 'run', 'observe', 'replay-slot', 'archive-observation'))
    parser.add_argument('--output', type=Path); parser.add_argument('--history', type=Path)
    parser.add_argument('--roster', type=Path); parser.add_argument('--anchor', type=Path)
    parser.add_argument('--operator', choices=('exp', 'sigmoid')); parser.add_argument('--case-id', type=int)
    parser.add_argument('--kind', choices=('confirmation', 'observation'))
    args = parser.parse_args()
    result = {'prepare': lambda: prepare(args.output, args.history), 'freeze': lambda: freeze(args.output),
        'run': lambda: run(args.roster, args.anchor), 'observe': lambda: observe(args.output, args.operator, args.case_id),
        'replay-slot': lambda: replay_slot(args.output, args.operator, args.kind, args.case_id),
        'archive-observation': lambda: archive_observation(args.output, args.operator, args.case_id)}[args.action]()
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__': main()
