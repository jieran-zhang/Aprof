"""Read-only correctness/boundary replay after task-local paths are removed.

Original reports/paths are never rewritten. Small source bytes are read from a
proof-bound post-task supplement; input/output/log bytes remain in existing CAS.
This leaf has no campaign, route, mechanism or publication admission authority.
"""
import json
from pathlib import Path
import sys
import types

from archive_task_rule_sources import verify_source_archive
from timing_admission import BOUNDARY_SIZES, THRESHOLDS, checked_path, identity, read, require, verify_boundary_report

import task_screen_bridge as screen
from task_rule_correctness import _same_native_metadata
ROLES = ('baseline', 'candidate')
from validation_host_evaluator import verify_correctness_report


def verify_mechanical_identity(reader, proof, build, report, source_archive_ref):
    paths = verify_source_archive(reader, source_archive_ref, proof, build, report)
    role_files = {r: proof['roles'][r]['files'] for r in ROLES}
    roles = {r: {name: paths[str(Path(proof['roles'][r]['path']) / name)].read_bytes()
                 for name in role_files[r]} for r in ROLES}
    historical = proof['historical_source_binding']; op = proof['operator']
    require(op in screen.rule.OPERATORS and historical['freeze']['sha256'] == 'sha256:' + screen.rule.FROZEN[op],
            'historical source freeze differs')
    freeze = read(reader, historical['freeze']['sha256'])
    require(freeze['source_hashes'] == {r: historical['roles'][r]['sha256'] for r in ROLES},
            'historical role source bindings differ')
    for role in ROLES:
        require(read(reader, historical['roles'][role]['sha256']) ==
                {'schema_version': '1.0.0', 'files': role_files[role]}
                and historical['roles'][role]['files'] == role_files[role]
                and screen.base.inventory(roles[role]) == role_files[role], 'archived role source differs')
    assembly = Path(build['binary']['path']).parent.parent
    headers = {name: paths[str(assembly / 'source/op_host' / name)].read_bytes() for name in screen.rule.HEADERS}
    require(proof['trusted_headers'] == screen.rule.HEADERS
            and screen.base.inventory(headers) == screen.rule.HEADERS, 'archived trusted headers differ')
    for path, digest in proof['producer_files'].items():
        # Execute only the current trusted generator with identical producer bytes.
        require(screen.file_hash(path) == digest, 'trusted mechanical replay producer changed')
    # These two private adapter inputs normally read the original baseline/freeze
    # from disk. All their bytes and hard-coded freeze hashes were verified above.
    previous = screen.rule.prepared_baseline, screen.rule.frozen_binding
    screen.rule.prepared_baseline = lambda operator: roles['baseline'] if operator == op else None
    screen.rule.frozen_binding = lambda operator: historical if operator == op else None
    try:
        generated = screen.generated(op, roles, headers)
        rebuilt = screen.proof_for(op, {r: Path(proof['roles'][r]['path']) for r in ROLES}, assembly,
                                  roles, generated, role_files, proof['trusted_headers'])
    finally:
        screen.rule.prepared_baseline, screen.rule.frozen_binding = previous
    require(screen.base.inventory(generated) == proof['adapted_files'] and rebuilt == proof,
            'archived source or full mechanical proof differs from exact regeneration')
    require(all(paths[str(assembly / 'source' / name)].read_bytes() == data for name, data in generated.items()),
            'archived adapted source bytes differ')
    attempt_path = assembly / 'build-attempt.json'
    require(build['binary']['path'] == str(assembly / 'build' / op)
            and build['status'] == 'passed' and build['error'] is None
            and build['source_review_hash'] == report['source_review_ref']
            and build['attempt_ref']['path'] == str(attempt_path), 'archived combined build differs')
    checked_path(reader, build['binary']['path'], build['binary']['sha256'])
    attempt = read(reader, build['attempt_ref']['sha256'])
    require(set(attempt) == {'source_review_hash', 'independent_review', 'route'}
            and attempt['source_review_hash'] == report['source_review_ref'], 'archived exclusive build attempt differs')
    screen.bridge._check_build_route(attempt['route'])
    require(len(build['commands']) == 2, 'archived build command count differs')
    for stage, command in zip(('configure', 'build'), build['commands'], strict=True):
        require(command['argv'] == proof['commands'][stage] and command['cwd'] == str(assembly / 'source')
                and type(command['exit_status']) is int and command['exit_status'] == 0 and command['error'] is None,
                'archived build command/exit differs')
    import sdk_build_evidence
    sdk_build_evidence.verify(build, proof, reader=reader)
    return proof


def _metadata(reader, protocol, report, proof):
    op, stage = report['operator'], report['kind'].removeprefix('task_rule_')
    require(stage in ('correctness', 'boundary'), 'unsupported correctness stage')
    inputs = read(reader, protocol['input_inventory_ref'])
    oracle = str(Path(proof['roles']['baseline']['path']) / 'scripts/verify_result.py')
    oracle_ref = proof['roles']['baseline']['files']['scripts/verify_result.py']
    require(protocol['oracle_files'].get(oracle) == oracle_ref == report['oracle_ref'], 'original oracle binding differs')
    checked_path(reader, oracle, oracle_ref)
    ids = list(range(1, 21)); cases = None
    if stage == 'boundary':
        plan = read(reader, protocol['boundary_plan_ref']); cases = plan['cases']
        require(plan['schema_version'] == 1 and plan['operator'] == op and plan['verifier_ref'] == oracle_ref
                and [(c['dtype'], c['numel']) for c in cases] == [(t,n) for t in THRESHOLDS for n in BOUNDARY_SIZES[op]]
                and [c['case_id'] for c in cases] == list(range(101, 101 + len(cases))), 'frozen boundary inventory differs')
        ids = [c['case_id'] for c in cases]
    require(report['case_ids'] == report['passed_case_ids'] == ids
            and [(r['case_id'],r['role']) for r in report['rows']] == [(i,r) for i in ids for r in ROLES],
            'correctness case/role inventory differs')
    metadata = []
    for index,cid in enumerate(ids):
        reference = report['rows'][index*2]['original_metadata_ref']
        names = [name for name,digest in inputs.items() if digest == reference
                 and Path(name).parts[-2:] == (f'case_{cid:02d}', 'metadata.json')]
        require(len(names) == 1, 'original case metadata path is absent or ambiguous')
        path = names[0]; value = json.loads(checked_path(reader, path, reference).read_text())
        require(value['case_id'] == cid and value['dtype'] in THRESHOLDS, 'prepared case identity differs')
        raw = checked_path(reader, value['input'], inputs[value['input']])
        require(raw.stat().st_size == value['numel'] * (4 if value['dtype'] == 'float32' else 2), 'prepared input byte count differs')
        if cases is not None:
            case = cases[index]; attrs = value.get('attrs', {k:value[k] for k in ('base','scale','shift') if k in value})
            require(all(value[k] == case[k] for k in ('case_id','shape','dtype','numel'))
                    and attrs == case.get('attrs', {}) and case['input_files'] == {value['input']:inputs[value['input']]},
                    'boundary metadata differs from frozen plan')
        metadata.append((path, value))
    return inputs, metadata, oracle


def verify_archived_rule_correctness(reader, report_ref, *, protocol_ref, expected, window, source_archive_ref, device=0):
    report, protocol = read(reader, report_ref), read(reader, protocol_ref)
    identity(report, expected); identity(protocol, expected)
    stage = report['kind'].removeprefix('task_rule_')
    require(report['status'] == 'passed' and report['error'] is None and report['protocol_ref'] == protocol_ref
            and report['device'] == device and window[0] <= report['started_at'] <= report['finished_at'] <= window[1],
            'correctness identity/status/window differs')
    require(report['source_review_ref'] == protocol['source_review_ref'], 'mechanical proof differs from frozen protocol')
    proof, build = (read(reader, report[key]) for key in ('source_review_ref','build_receipt_ref'))
    verify_mechanical_identity(reader, proof, build, report, source_archive_ref)
    require(proof['operator'] == expected['operator']
            and {r:proof['historical_source_binding']['roles'][r]['sha256'] for r in ROLES} == expected['source_hashes']
            and report['binary_hashes'] == protocol['binary_hashes'] == {r:build['binary']['sha256'] for r in ROLES}
            and report['input_inventory_ref'] == protocol['input_inventory_ref'], 'correctness source/build/input binding differs')
    inputs, metadata, oracle = _metadata(reader, protocol, report, proof)
    role_reports = {}
    if stage == 'correctness':
        # Reuse the actual legacy checker, substituting only its path resolver in
        # isolated globals. Its result/exit/stdout/full-output checks are unchanged.
        legacy = types.FunctionType(verify_correctness_report.__code__,
            dict(verify_correctness_report.__globals__, checked=lambda ref: checked_path(reader,ref['path'],ref['sha256'])))
        role_reports = {r: legacy(report['role_reports'][r]) for r in ROLES}
    else:
        verify_boundary_report(reader, report_ref, protocol_ref=protocol_ref, expected={**expected,'boundary_window':window})
    previous = report['started_at']; binary = Path(build['binary']['path'])
    for index,row in enumerate(report['rows']):
        original_path,m = metadata[index//2]; role = row['role']; bound = read(reader,row['metadata_ref'])
        require(row['passed'] is True and row['source_hash'] == expected['source_hashes'][role]
                and row['binary_hash'] == protocol['binary_hashes'][role]
                and row['original_metadata_ref'] == inputs[original_path]
                and row['input_refs'] == {m['input']:inputs[m['input']]}
                and _same_native_metadata(bound, dict(m,output=bound['output'])) and len(row['output_refs']) == 1,
                'correctness row source/input/output binding differs')
        output = Path(bound['output']); output_bytes = checked_path(reader,output,row['output_refs'][0])
        checked_path(reader,output.parent/'metadata.json',row['metadata_ref'])
        checked_path(reader,output.parent/'result.json',row['result_ref'])
        require(output_bytes.stat().st_size == m['numel']*(4 if m['dtype']=='float32' else 2), 'complete output byte count differs')
        outputs = {r:{'output':str(output.parent/(r+'-output.bin'))} for r in ROLES}
        command = screen.base.case_command(proof['operator'],binary,m,device,outputs)
        commands = [command+['--aprof-mechanism-role',role], [sys.executable,oracle,'--metadata',str(output.parent/'metadata.json')]]
        for key,argv in zip(('kernel','verifier'),commands,strict=True):
            record = read(reader,row[key+'_execution_ref']); raw = read(reader,record['original_execution_ref'])
            for stream in ('stdout','stderr'):
                require(set(record[stream]) == {'path','sha256'} and record[stream]['sha256'] == raw[stream+'_hash'],
                        'execution log projection differs')
                checked_path(reader,record[stream]['path'],raw[stream+'_hash'])
            projection = dict(argv=raw['argv'],cwd=raw['cwd'],started_at=raw['started_at'],finished_at=raw['ended_at'],
                exit_status=raw['exit_code'],error=raw['error'],environment=raw['environment'],timeout_seconds=raw['timeout_seconds'],
                pid=raw['pid'],stdout=record['stdout'],stderr=record['stderr'],log_ref=raw['stdout_hash'],
                original_execution_ref=record['original_execution_ref'])
            require(record == projection and record['argv'] == argv
                    and record['cwd'] == str(binary.parent.parent / 'source' if key == 'kernel' else Path(oracle).parent.parent)
                    and record['exit_status'] == 0 and record['error'] is None
                    and record['environment'] == {'APROF_SHARED_CYCLE':'0'}
                    and previous <= record['started_at'] <= record['finished_at'] <= report['finished_at'],
                    'correctness actual execution/role/order differs')
            previous = record['finished_at']
        if stage == 'correctness':
            legacy_row = role_reports[role]['rows'][index//2]
            for key,reference in [('metadata',row['metadata_ref']),('verification',row['result_ref']),
                    ('kernel_execution',row['kernel_execution_ref']),('verifier_execution',row['verifier_execution_ref'])]:
                require(legacy_row[key]['sha256'] == reference, 'role report differs from execution aggregate')
            require([v['sha256'] for v in legacy_row['outputs']] == row['output_refs'], 'role output refs differ')
    return {'passed':True,'stage':stage,'case_count':len(metadata),'report_ref':report_ref,'protocol_ref':protocol_ref,
            'source_archive_ref':source_archive_ref,'admission_authority':False,'eligible_for_publication':False}
