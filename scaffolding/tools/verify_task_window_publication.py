#!/usr/bin/env python3
"""Independent publication gate for calibrated native Task Duration evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_measurement_publication as common

PROTOCOL = 'shared_buffer_msprof_task_window_v4'
HISTORICAL_PROTOCOL = 'shared_buffer_msprof_task_window_v1'
TARGET_MS = 10
OPERATORS, TIMELINES = common.OPERATORS, common.TIMELINES
require, load, reference, bound = common.require, common.load, common.reference, common.bound


def archived_confirmation(item, online_folder):
    """Verify the later trace collector handoff without giving it admission authority."""
    archive = load(reference(item['archive_receipt_ref']))
    require(set(archive) == {'schema_version', 'owner', 'cost_scope', 'admission_authority',
                            'local_index', 'completion_ref', 'store', 'artifact_refs',
                            'started_at', 'finished_at', 'elapsed_seconds'}
            and archive['schema_version'] == 1 and archive['owner'] == 'trace_collection'
            and archive['cost_scope'] == 'post_task_archive' and archive['admission_authority'] is False
            and archive['completion_ref'] == item['receipt_ref']
            and Path(archive['store']).resolve(strict=True) == Path(item['store_path']).resolve(strict=True)
            and archive['local_index']['path'] == str(online_folder / 'local-evidence-index.json')
            and 0 < archive['elapsed_seconds']
            and archive['started_at'] <= archive['finished_at'],
            'post-task confirmation archive differs')
    store = common.ReadonlyCAS(item['store_path'])
    try:
        index = store.load(archive['local_index']['sha256'])
        require(set(index) == {'schema_version', 'kind', 'directory', 'artifacts'}
                and index['schema_version'] == 1 and index['kind'] == 'local_evidence_index'
                and index['directory'] == str(online_folder / 'records')
                and isinstance(index['artifacts'], dict) and index['artifacts']
                and archive['artifact_refs'] == sorted(index['artifacts'])
                and archive['completion_ref'] in index['artifacts'],
                'archived local index scope differs')
        for artifact_ref in archive['artifact_refs']:
            store.verify_artifact(artifact_ref)
        completion = store.load(item['receipt_ref'])
        require(completion['kind'] == 'local_measurement_completion'
                and completion['protocol'] == PROTOCOL and completion['status'] == 'passed'
                and completion['finished_at'] <= archive['started_at'],
                'archived completion predates neither task nor trace collection')
        return archive, completion
    finally:
        store.close()


def runtime_replay(root, confirmations, *, qualification_dir, installed=False):
    if not installed:
        sys.path.insert(0, str(root / 'runtime/src'))
    import aprof_runtime.task_window_measurement_admission as module
    import aprof_runtime.measurement_entry as entry
    actual = Path(module.__file__).resolve()
    require(actual.is_relative_to(root) and module.PROTOCOL == PROTOCOL,
            'Task window runtime imported from another protocol/package')
    require(common.digest(actual) == common.digest(root / 'runtime/src/aprof_runtime/task_window_measurement_admission.py'),
            'installed Task window replay code differs')
    if installed:
        import importlib.metadata
        require(importlib.metadata.version('aprof-runtime') == '0.2.2', 'installed runtime version differs')
        for source in (root / 'runtime/src/aprof_runtime').glob('*.py'):
            require((actual.parent / source.name).is_file()
                    and common.digest(actual.parent / source.name) == common.digest(source),
                    'installed module differs: ' + source.name)
    require(set(confirmations) == set(OPERATORS), 'both operator confirmations are required')
    results = {}
    for operator in OPERATORS:
        item = confirmations[operator]
        online_folder = Path('/tmp') / f'aprof-task-window-{Path(qualification_dir).name}-{operator}-work'
        archive, completion = archived_confirmation(item, online_folder)
        store = common.ReadonlyCAS(item['store_path'])
        try:
            receipt = store.load(item['receipt_ref'])
            require(receipt.get('protocol') == PROTOCOL and receipt.get('kind') == 'local_measurement_completion',
                    'only completed local Task window evidence qualifies')
            result = entry.replay_current_measurement_admission(store, item['receipt_ref'],
                                                                     expected={'operator': operator})
            require(result.get('valid') is True and result['report']['stable'] is True,
                    'complete Task window replay did not validate')
            proof = store.load(receipt['proof_ref'])
            require(proof['source_hashes']['baseline'] == proof['source_hashes']['candidate'],
                    'method confirmation is not A/A')
            common.formal_aa_controls(result['report'])
            registration = store.load(proof['registration_ref'])
            results[operator] = {'replay': result, 'receipt': receipt, 'proof': proof,
                'post_task_archive': archive,
                'config': store.load(proof['config_ref']),
                'registration': registration, 'raw': store.load(proof['raw_ref']),
                'calibration': store.load(registration['calibration_ref'])}
        finally:
            store.close()
    return {'runtime_module': str(actual), 'runtime_module_sha256': common.digest(actual), 'operators': results}


def mechanical_sources(preparation, original_adapter, plan, frozen, results):
    """Bind both original→shared and shared→native-profile mechanical adapters."""
    from probe_native_task_profile import source_identity
    native_root = Path(plan['native_source_root'])
    require(native_root == preparation.NATIVE_SOURCES, 'native build root differs')
    for operator in OPERATORS:
        item = plan['operators'][operator]
        proof = load(item['source_review'])
        original, shared_source = Path(item['original_source']), Path(item['source'])
        require(set(proof['patches']) == {f'op_host/{operator}.asc', 'scripts/verify_result.py'},
                'original mechanical adaptation scope differs')
        for relative, adapter in ((f'op_host/{operator}.asc', original_adapter.adapt_host),
                                  ('scripts/verify_result.py', original_adapter.adapt_oracle)):
            require((shared_source / relative).read_text() == adapter((original / relative).read_text(), operator),
                    'original host/oracle changes exceed the mechanical adapter')
        require(set(proof['adapted_files']) - set(proof['original_files']) == {'op_host/device_shared_timing.h'}
                and all(proof['adapted_files'].get(name) == digest for name, digest in proof['original_files'].items()
                        if name not in proof['patches']), 'original kernel/tiling/source was modified')
        source, files = source_identity(native_root, operator)
        require(all(path in frozen['frozen_files']
                    and common.hex_digest(digest) == common.hex_digest(frozen['frozen_files'][path])
                    for path, digest in files.items()), 'native adapter/build evidence was not frozen')
        review = load(native_root / operator / 'source-review.json')
        build = load(native_root / operator / 'build-receipt.json')
        require(Path(review['original_source']) == shared_source
                and {p: common.hex_digest(h) for p, h in review['original_files'].items()}
                == {p: common.hex_digest(h) for p, h in proof['adapted_files'].items()},
                'native profiling adapter is not chained to original source adaptation')
        result, config = results[operator], results[operator]['config']
        require(config == load(frozen['configs'][operator])
                and config['build']['source_dir'] == str(source)
                and config['build']['binary'] == build['binary']['path'], 'timed native config/build differs')
        identity, inventory = result['registration']['identity'], result['registration']['inventory']
        role_files = {p: 'sha256:' + common.hex_digest(h) for p, h in proof['original_role_files'].items()}
        require(inventory['sources'] == {role: role_files for role in ('baseline', 'candidate')},
                'A/A original source bundles differ')
        require(inventory['build_sources'] == {p: 'sha256:' + common.hex_digest(h)
                for p, h in review['adapted_files'].items()}, 'compiled native source bundle differs')
        require(identity['build']['binary_ref'] == 'sha256:' + common.hex_digest(build['binary']['sha256']),
                'timed binary differs from actual native build')
        for case in config['cases']:
            required = next(c for c in item['cases'] if c['case_id'] == case['case_id'])
            require(case['prepared_files'] == [required['metadata'], required['input']]
                    and case['workload'] == required['workload'], 'prepared inputs/workload changed')
            metadata = load(required['metadata'])
            require(case['workload'] == original_adapter.workload_json(
                {k: v for k, v in metadata.items() if k not in {'input', 'output'}}),
                'workload differs from original metadata')
            bindings = identity['cases'][str(case['case_id'])]
            require(bindings['prepared_files'] == {p: 'sha256:' + common.hex_digest(plan['frozen_files'][p])
                    for p in case['prepared_files']}, 'CAS inputs differ from preregistration')
        require(result['calibration']['started_at'] >= frozen['created_at'] >= plan['created_at'],
                'pilot calibration predates preregistration')


def failed_attempt_history(reference):
    from replay_task_window_failure import replay_task_window_failure
    result = replay_task_window_failure(reference)
    require(result.get('valid') is True and result.get('accepted') is False
            and result.get('eligible_for_publication') is False
            and result.get('complete_method_qualification') is False
            and result.get('measurement_admission_replayed') is False,
            'prior failed Task-window attempt did not replay as historical failure')
    return result


def verify_in_process(root, report_path):
    audit_started = time.monotonic()
    root, report_path = Path(root).resolve(strict=True), Path(report_path).resolve(strict=True)
    report = load(report_path)
    fields = {'schema_version', 'protocol', 'qualification_dir', 'history_ref', 'confirmations',
              'observation_archive_refs', 'attempt_roster_ref', 'install_receipt_ref',
              'candidate_inventory_ref', 'old_release_baseline_ref'}
    require(isinstance(report, dict) and set(report) == fields and report['schema_version'] == 1,
            'invalid publication report schema')
    require(report['protocol'] == PROTOCOL, 'only calibrated Task window evidence qualifies')
    require(root.name == '0.5.1' and root.parent.name == 'graph-base', 'wrong release identity')
    require(tomllib.loads((root / 'runtime/pyproject.toml').read_text())['project']['version'] == '0.2.2',
            'runtime must be 0.2.2')
    old, current = common.protected_rules(root, common.REPO / 'skill-libs/graph-base/0.5.0')
    require(not common.release_tool(root).registry_errors(root), 'candidate registry/links are invalid')
    previous = load(reference(report['old_release_baseline_ref']))
    require(previous['baseline']['files'] == old['files']
            and common.hex_digest(previous['baseline']['manifest_sha256']) == common.BASELINE_MANIFEST,
            'old release fingerprint differs')
    inventory_path = reference(report['candidate_inventory_ref'])
    inventory = load(inventory_path)
    require(inventory == {'schema_version': 1, 'root': str(root), 'files': current}, 'candidate payload inventory differs')
    require(set(report['confirmations']) == set(OPERATORS)
            and set(report['observation_archive_refs']) == set(OPERATORS),
            'both complete confirmations and four observations are required')
    sys.path.insert(0, str(common.COLLECTION))
    import qualify_task_window_timing_v051 as preparation
    import qualify_shared_timing_v051 as original_adapter
    from replay_task_window_method_history import replay_task_window_method_history
    from replay_profile_storage_cost import replay_profile_storage_cost
    directory, _ = preparation.load_plan(report['qualification_dir'])
    plan, frozen = preparation.checked_plan(directory)
    preparation.task_modules()
    preparation.require_target_choice()
    require(reference(frozen['candidate_inventory']).resolve() == inventory_path.resolve()
            and plan['protocol'] == PROTOCOL and plan['history'] == report['history_ref']
            and plan.get('historical_protocol') == HISTORICAL_PROTOCOL
            and plan.get('calibration_target_ms') == TARGET_MS
            and plan.get('fixed_cost_summary_ref') == preparation.cost_summary_ref(),
            'qualification inventory/protocol/history differs')
    cost_design = preparation.verify_cost_summary()
    offline_cost_studies = preparation.offline_cost_studies_ref()
    require(plan.get('offline_cost_studies') == offline_cost_studies,
            'offline CAS design cost provenance differs from the frozen plan')
    failure = failed_attempt_history(plan['failed_attempt_ref'])
    failure_v2 = preparation.replay_failed_attempt_v2(plan['failed_attempt_v2_ref'])
    history = replay_task_window_method_history(report['history_ref'])
    require(history.get('valid') is True and history.get('eligible_for_publication') is False,
            'historical evidence was not preserved separately from new acceptance')
    storage_cost = replay_profile_storage_cost(plan['storage_cost_evidence'])
    require(storage_cost.get('valid') is True and storage_cost.get('eligible_for_publication') is False,
            'offline storage cost provenance did not replay')
    roster_path = reference(report['attempt_roster_ref'])
    archives = {}
    for operator in OPERATORS:
        archives[operator], _ = archived_confirmation(report['confirmations'][operator],
            preparation.local_confirmation_dir(directory, operator))
    campaign_started = time.monotonic()
    campaign = preparation.replay_task_campaign(roster_path, qualification_dir=directory,
                                                 archived_confirmations=archives)
    campaign_seconds = time.monotonic() - campaign_started
    require(campaign.get('complete') is True and campaign.get('accepted') is True
            and campaign.get('protocol') == PROTOCOL
            and campaign.get('authority') == 'method_qualification_only_no_publication',
            'campaign is incomplete or contains failed/skipped attempts')
    results = {}
    for operator in OPERATORS:
        item = report['confirmations'][operator]
        require(Path(item['store_path']).is_absolute()
                and not Path(item['store_path']).resolve().is_relative_to(preparation.local_confirmation_dir(directory, operator)),
                'confirmation archive cannot be the local optimization workspace')
        slot = campaign['slots'][operator + '-confirmation']
        admission = slot['admission']
        require(admission['completion_ref'] == item['receipt_ref'] and admission['protocol'] == PROTOCOL
                and admission['valid'] is True and admission['report']['stable'] is True,
                'confirmation differs from the freshly replayed campaign admission')
        common.formal_aa_controls(admission['report'])
        store = common.ReadonlyCAS(item['store_path'])
        try:
            receipt = store.load(item['receipt_ref']); proof = store.load(receipt['proof_ref'])
            registration = store.load(proof['registration_ref'])
            require(proof['source_hashes']['baseline'] == proof['source_hashes']['candidate']
                    and admission['receipt_ref'] == receipt['proof_ref']
                    and proof['config_ref'] == admission['config_ref']
                    and proof['registration_ref'] == admission['registration_ref'],
                    'confirmation metadata differs from campaign A/A replay')
            results[operator] = {'replay': admission, 'receipt': receipt, 'proof': proof,
                'config': store.load(proof['config_ref']), 'registration': registration,
                'raw': store.load(proof['raw_ref']),
                'calibration': store.load(registration['calibration_ref'])}
        finally:
            store.close()
        terminal = load(reference(slot['terminal']))
        require(terminal['status'] == 'passed'
                and reference(terminal['execution']).resolve() == reference(item['execution_ref']).resolve(),
                'confirmation execution is not the passed registered execution')
        require(terminal['online_completion'] == {'path': str(preparation.local_confirmation_dir(directory, operator) / 'local-result.json'),
                                                  'sha256': item['receipt_ref']},
                'confirmation completion differs from registered online terminal')
    mechanical_sources(preparation, original_adapter, plan, frozen, results)
    observations = {}
    for operator in OPERATORS:
        require(set(report['observation_archive_refs'][operator]) == {str(i) for i in TIMELINES[operator]},
                'observation case selection changed')
        for case_id in TIMELINES[operator]:
            archive_path = reference(report['observation_archive_refs'][operator][str(case_id)])
            slot_id = f'{operator}-observation-{case_id:02d}'
            require(archive_path == directory / 'observations' / slot_id / 'profiled/post-task-archive.json',
                    'observation archive is outside its fixed slot')
            slot = campaign['slots'][slot_id]
            result = slot['observation']
            require(slot['operator'] == operator and slot['kind'] == 'observation'
                    and slot['status'] == 'passed' and result.get('complete') is True
                    and result.get('post_task_archive') is True,
                    'observation differs from the unique freshly replayed campaign slot')
            terminal = load(reference(slot['terminal']))
            require(terminal['online_completion'] == bound(directory / 'observations' / slot_id / 'terminal.json'),
                    'observation online terminal differs')
            observations[f'{operator}:{case_id}'] = {'post_task_archive': bound(archive_path), 'replay': result}
    report['_report_path'] = report_path
    installed = common.independent_install(root, report, current, probe_script=Path(__file__).resolve())
    require(common.release_tool(root).inventory(root) == current, 'candidate changed during replay')
    preparation.checked_plan(directory)
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=common.REPO,
                          capture_output=True, text=True, check=True).stdout.strip()
    return {'accepted': True, 'purpose': 'measurement_method_only_no_optimization_promotion',
        'protocol': PROTOCOL, 'metric': 'msprof.op_summary.Task_Duration',
        'calibration_target_ms': TARGET_MS,
        'publication_report': bound(report_path), 'candidate_inventory': bound(inventory_path),
        'old_release_manifest_sha256': common.BASELINE_MANIFEST, 'plan': bound(directory / 'plan.json'),
        'freeze': bound(directory / 'freeze.json'), 'attempt_roster': bound(roster_path), 'retained_history': history,
        'storage_cost_evidence': storage_cost, 'prior_failed_attempt': failure,
        'prior_failed_attempt_v2': failure_v2,
        'pre_change_scaffolding': plan['pre_change_scaffolding_ref'],
        'pre_change_package': plan['pre_change_package_ref'], 'fixed_cost_design': cost_design,
        'offline_cost_studies': offline_cost_studies,
        'confirmations': {op: {'receipt_ref': report['confirmations'][op]['receipt_ref'],
            'store_path': report['confirmations'][op]['store_path'], 'report': results[op]['replay']['report'],
            'repeat_by_case': results[op]['replay']['repeat_by_case']} for op in OPERATORS},
        'observations': observations, 'independent_install': installed,
        'campaign_replay_seconds': campaign_seconds,
        'post_task_independent_audit_seconds': time.monotonic() - audit_started,
        'source_provenance': {'source_commit': head, 'source_state': 'working_tree_payload',
            'committed_payload_claimed': False, 'payload_inventory_sha256': common.canonical_digest(current),
            'qualification_producer_files': frozen['frozen_files']}}


def verify_task_window_publication(root: Path, report_path: Path) -> dict:
    result = subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--root', str(root),
                             '--report', str(report_path)], capture_output=True, text=True, timeout=1800)
    require(result.returncode == 0, result.stderr[-6000:] or 'independent Task window publication replay failed')
    value = json.loads(result.stdout)
    require(value.get('accepted') is True, 'independent Task window publication was not accepted')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--installed-probe', action='store_true')
    args = parser.parse_args()
    report = load(args.report)
    result = runtime_replay(args.root.resolve(), report['confirmations'],
                            qualification_dir=report['qualification_dir'], installed=True) \
        if args.installed_probe else verify_in_process(args.root, args.report)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
