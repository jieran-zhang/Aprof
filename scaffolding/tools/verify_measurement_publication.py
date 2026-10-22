#!/usr/bin/env python3
"""Replay independent evidence before publishing graph-base/0.5.1."""
from __future__ import annotations
import argparse
import ast
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import sys
import tomllib

REPO = Path(__file__).resolve().parents[2]
COLLECTION = REPO / 'scaffolding/collection/scripts'
OPERATORS = ('exp', 'sigmoid')
TIMELINES = {'exp': (1, 9), 'sigmoid': (1, 4)}
BASELINE_MANIFEST = '7c3aab13365d3c41ba5516b593e238538546d405d247ee4161f962aed4429bbc'


def require(condition, message):
    if not condition:
        raise ValueError('0.5.1 measurement publication: ' + message)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def hex_digest(value):
    require(isinstance(value, str) and re.fullmatch(r'(?:sha256:)?[0-9a-f]{64}', value), 'invalid SHA-256')
    return value.removeprefix('sha256:')


def load(path):
    return json.loads(Path(path).read_text())


def reference(value):
    require(isinstance(value, dict) and set(value) == {'path', 'sha256'}, 'file reference requires path/sha256')
    path = Path(value['path'])
    require(path.is_absolute() and not path.is_symlink() and path.is_file(), 'reference is not an absolute regular file')
    require(digest(path) == hex_digest(value['sha256']), 'file reference changed: ' + str(path))
    return path


def bound(path):
    return {'path': str(Path(path).resolve()), 'sha256': digest(path)}


def release_tool(root):
    spec = importlib.util.spec_from_file_location('measurement_release_inventory', Path(root) / 'tools/release.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def protected_rules(root, baseline):
    """New admission joins are allowed; graphs, schemas and gate arithmetic are frozen."""
    tool = release_tool(baseline)
    old = tool.verify(baseline)
    require(digest(baseline / 'release.json') == BASELINE_MANIFEST, 'canonical 0.5.0 manifest changed')
    current = tool.inventory(root)
    prefixes = ('schemas/', 'skillgraph/versions/')
    expected = {p: h for p, h in old['files'].items() if p.startswith(prefixes)}
    require({p: h for p, h in current.items() if p.startswith(prefixes)} == expected, 'frozen graph/schema inventory changed')
    contracts = 'runtime/src/aprof_runtime/contracts.py'
    require(current.get(contracts) == old['files'][contracts], 'frozen machine contracts or floors changed')
    def arithmetic(path):
        names = {'_median', '_cv', '_paired_estimate', 'CandidateGate', 'evaluate_candidate_evidence'}
        return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(path.read_text()).body
                if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names}
    relative = Path('runtime/src/aprof_runtime/gates.py')
    require(arithmetic(root / relative) == arithmetic(baseline / relative), 'frozen gate arithmetic changed')
    return old, current


class ReadonlyCAS:
    def __init__(self, path):
        self.path = Path(path).resolve(strict=True)
        require(self.path.is_file(), 'CAS database missing')
        self.connection = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)
        self.connection.execute('BEGIN')
        self.verified = {}

    @staticmethod
    def _identity(path):
        try:
            value = path.lstat()
        except OSError as error:
            raise ValueError('0.5.1 measurement publication: CAS object missing or unreadable') from error
        require(stat.S_ISREG(value.st_mode), 'CAS object is not a regular non-symlink file')
        return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
                value.st_mtime_ns, value.st_ctime_ns)

    def verify_artifact(self, ref):
        hexadecimal = hex_digest(ref)
        require(ref == 'sha256:' + hexadecimal, 'CAS references require canonical prefix')
        path = self.path.parent / (self.path.name + '.objects') / 'sha256' / hexadecimal[:2] / hexadecimal[2:]
        identity = self._identity(path)
        if self.verified.get(ref) != identity:
            require(digest(path) == hexadecimal, 'CAS object content changed')
            require(self._identity(path) == identity, 'CAS object changed during verification')
        require(self.connection.execute('SELECT 1 FROM artifacts WHERE content_hash=?', (ref,)).fetchone(), 'CAS object is not indexed')
        self.verified[ref] = identity
        return path

    def load(self, ref):
        return load(self.verify_artifact(ref))

    def close(self):
        self.connection.close()


def formal_aa_controls(report):
    require(report.get('case_ids') == list(range(1, 21)), 'confirmation must include exactly the original 20 cases')
    rows = report.get('controls', [])
    require([r.get('case_id') for r in rows] == list(range(1, 21)), 'missing confirmation controls')
    for row in rows:
        require([c.get('cycle') for c in row['cycles']] == list(range(6)), 'confirmation requires six fresh cycles')
        for value in [row['overall'], *row['cycles']]:
            bias = value['formal']['role_bias']
            require(type(bias) in (int, float) and math.isfinite(bias) and 0 <= bias <= 0.02,
                    f"case {row['case_id']} formal A/A role bias exceeds 2%")


def runtime_replay(root, confirmations, *, installed=False):
    if not installed:
        sys.path.insert(0, str(root / 'runtime/src'))
    from aprof_runtime.measurement_admission import replay_measurement_admission
    import aprof_runtime.measurement_admission as module
    actual = Path(module.__file__).resolve()
    require(actual.is_relative_to(root), 'runtime imported from another release/environment')
    require(digest(actual) == digest(root / 'runtime/src/aprof_runtime/measurement_admission.py'), 'installed replay code differs')
    if installed:
        import importlib.metadata
        require(importlib.metadata.version('aprof-runtime') == '0.2.2', 'installed runtime version differs')
        for source in (root / 'runtime/src/aprof_runtime').glob('*.py'):
            require((actual.parent / source.name).is_file() and digest(actual.parent / source.name) == digest(source), 'installed module differs: ' + source.name)
    results = {}
    for operator in OPERATORS:
        item = confirmations[operator]
        store = ReadonlyCAS(item['store_path'])
        try:
            receipt = store.load(item['receipt_ref'])
            require(receipt.get('protocol') == 'shared_buffer_msprof_task_v2',
                    'only local-scratch Task v2 evidence can qualify this release')
            result = replay_measurement_admission(store, item['receipt_ref'], expected={'operator': operator})
            require(result['valid'] is True, 'measurement replay did not validate')
            require(receipt['source_hashes']['baseline'] == receipt['source_hashes']['candidate'], 'method confirmation is not A/A')
            formal_aa_controls(result['report'])
            results[operator] = {'replay': result, 'receipt': receipt, 'config': store.load(receipt['config_ref']),
                                'registration': store.load(receipt['registration_ref']), 'raw': store.load(receipt['raw_ref'])}
        finally:
            store.close()
    return {'runtime_module': str(actual), 'runtime_module_sha256': digest(actual), 'operators': results}


def mechanical_sources(preparation, plan, frozen, results):
    for operator in OPERATORS:
        item = plan['operators'][operator]
        proof = load(item['source_review'])
        source, original = Path(item['source']), Path(item['original_source'])
        require(set(proof['patches']) == {f'op_host/{operator}.asc', 'scripts/verify_result.py'}, 'source adaptation scope differs')
        for relative, adapter in ((f'op_host/{operator}.asc', preparation.adapt_host), ('scripts/verify_result.py', preparation.adapt_oracle)):
            require((source / relative).read_text() == adapter((original / relative).read_text(), operator), 'changes exceed the exact mechanical adapter')
        for relative, before in proof['original_files'].items():
            if relative not in proof['patches']:
                require(proof['adapted_files'].get(relative) == before, 'kernel/tiling/source was modified')
        require(set(proof['adapted_files']) - set(proof['original_files']) == {'op_host/device_shared_timing.h'}, 'unexpected source additions')
        result, config = results[operator], results[operator]['config']
        require(config == load(frozen['configs'][operator]), 'collected config differs from frozen config')
        identity, inventory = result['registration']['identity'], result['registration']['inventory']
        expected = {p: 'sha256:' + h for p, h in proof['original_role_files'].items()}
        require(inventory['sources'] == {r: expected for r in ('baseline', 'candidate')}, 'A/A original source bundle differs')
        require(inventory['build_sources'] == {p: 'sha256:' + h for p, h in proof['adapted_files'].items()}, 'compiled source bundle differs')
        build = load(Path(item['source_review']).parent / 'build-receipt.json')
        require(build['status'] == 'passed' and identity['build']['binary_ref'] == 'sha256:' + build['binary_sha256'], 'timed binary differs from build')
        require(len(build['commands']) == 2 and all(c['exit_status'] == 0 for c in build['commands']), 'build commands incomplete')
        for command in build['commands']:
            require(digest(command['log']) == command['log_sha256'], 'build log changed')
        for case in config['cases']:
            required = next(c for c in item['cases'] if c['case_id'] == case['case_id'])
            require(case['prepared_files'] == [required['metadata'], required['input']] and case['workload'] == required['workload'], 'prepared inputs/workload changed')
            metadata = load(required['metadata'])
            require(case['workload'] == preparation.workload_json({k: v for k, v in metadata.items() if k not in {'input', 'output'}}),
                    'workload is not the exact tagged encoding of original metadata')
            bindings = identity['cases'][str(case['case_id'])]
            require(bindings['prepared_files'] == {p: 'sha256:' + plan['frozen_files'][p] for p in case['prepared_files']}, 'CAS inputs differ from preregistration')
        require(result['raw']['started_at'] >= frozen['created_at'] >= plan['created_at'], 'confirmation predates preregistration')


def independent_install(root, report, expected_files, *, probe_script=None):
    receipt_path = reference(report['install_receipt_ref'])
    receipt = load(receipt_path)
    require(receipt.get('schema_version') == 1, 'invalid independent installation receipt')
    copied = Path(receipt['package_root']).resolve(strict=True)
    require(copied != root and not copied.is_relative_to(root) and not root.is_relative_to(copied), 'installation is not independent')
    require(release_tool(root).inventory(copied) == expected_files, 'independently installed payload differs')
    require(not release_tool(copied).registry_errors(copied), 'installed registry/links are invalid')
    interpreter = copied / '.runtime-env/bin/python'
    require(interpreter.is_file(), 'independent runtime interpreter is absent')
    execution = load(reference(receipt['pip_execution_ref']))
    require(execution.get('argv') == [str(interpreter), '-m', 'pip', 'install', str(copied / 'runtime')]
            and type(execution.get('exit_status')) is int and execution['exit_status'] == 0, 'missing actual independent pip installation')
    require(execution['started_at'] <= execution['finished_at'], 'invalid pip execution interval')
    reference(execution['stdout_ref']); reference(execution['stderr_ref'])
    result = subprocess.run([str(interpreter), '-I', str(Path(probe_script or __file__).resolve()), '--root', str(copied),
                             '--report', str(report['_report_path']), '--installed-probe'], capture_output=True, text=True, timeout=900)
    require(result.returncode == 0, 'isolated installed-runtime replay failed: ' + result.stderr[-3000:])
    replay = json.loads(result.stdout)
    require(set(replay['operators']) == set(OPERATORS), 'installed replay scope differs')
    return {'receipt': bound(receipt_path), 'package_root': str(copied), 'runtime_module': replay['runtime_module'],
            'runtime_module_sha256': replay['runtime_module_sha256'],
            'replayed_receipts': {op: replay['operators'][op]['receipt']['measurement_report_ref'] for op in OPERATORS}}


def verify_in_process(root, report_path):
    root, report_path = Path(root).resolve(strict=True), Path(report_path).resolve(strict=True)
    report = load(report_path)
    required = {'schema_version', 'protocol', 'qualification_dir', 'history_ref', 'confirmations',
                'observation_refs', 'attempt_roster_ref', 'install_receipt_ref',
                'candidate_inventory_ref', 'old_release_baseline_ref'}
    require(isinstance(report, dict) and set(report) == required and report['schema_version'] == 1,
            'invalid publication report schema')
    protocol = 'shared_buffer_msprof_task_v2'
    require(report['protocol'] == protocol, 'only the Task Duration v2 local-storage method can qualify this release')
    require(root.name == '0.5.1' and root.parent.name == 'graph-base', 'wrong release identity')
    require(tomllib.loads((root / 'runtime/pyproject.toml').read_text())['project']['version'] == '0.2.2',
            'runtime must be 0.2.2')
    old, current = protected_rules(root, REPO / 'skill-libs/graph-base/0.5.0')
    previous = load(reference(report['old_release_baseline_ref']))
    require(previous['baseline']['files'] == old['files']
            and hex_digest(previous['baseline']['manifest_sha256']) == BASELINE_MANIFEST,
            'old release fingerprint differs')
    inventory_path = reference(report['candidate_inventory_ref'])
    inventory = load(inventory_path)
    require(inventory.get('schema_version') == 1 and inventory.get('files') == current
            and Path(inventory['root']).resolve() == root, 'candidate payload inventory differs')
    require(set(report['confirmations']) == set(OPERATORS), 'both operator confirmations are required')
    require(set(report['observation_refs']) == set(OPERATORS), 'four independent observations are required')
    sys.path.insert(0, str(COLLECTION))
    import qualify_task_timing_v051 as preparation
    import qualify_shared_timing_v051 as native_preparation
    from replay_task_measurement_history import replay_task_history
    directory, _ = preparation.load_plan(report['qualification_dir'])
    plan, frozen = preparation.checked_plan(directory)
    require(reference(frozen['candidate_inventory']).resolve() == inventory_path.resolve(),
            'publication inventory was not the frozen candidate inventory')
    require(plan['protocol'] == protocol and plan['history'] == report['history_ref'],
            'qualification protocol or retained history differs')
    history = replay_task_history(report['history_ref'])
    require(history['valid'] is True and history['eligible_for_publication'] is False,
            'historical evidence was not preserved separately from new acceptance')
    roster_path = reference(report['attempt_roster_ref'])
    campaign = preparation.replay_task_campaign(roster_path, qualification_dir=directory)
    require(campaign.get('complete') is True and campaign.get('accepted') is True
            and campaign.get('protocol') == protocol
            and campaign.get('authority') == 'method_qualification_only_no_publication',
            'campaign is incomplete or contains failed/skipped attempts')
    results = runtime_replay(root, report['confirmations'])['operators']
    mechanical_sources(native_preparation, plan, frozen, results)
    for operator in OPERATORS:
        item = report['confirmations'][operator]
        execution_path = reference(item['execution_ref'])
        slot = campaign['slots'][operator + '-confirmation']
        terminal = load(reference(slot['terminal']))
        require(terminal['status'] == 'passed' and 'execution' in terminal,
                'confirmation has no passed registered execution')
        require(reference(terminal['execution']).resolve() == execution_path.resolve(),
                'confirmation execution is not registered')
        native_receipt = directory / operator / 'confirmation/measurement_admission.json'
        require(load(native_receipt) == results[operator]['receipt']
                and 'sha256:' + digest(native_receipt) == item['receipt_ref'],
                'confirmation receipt differs from registered result')
    observations = {}
    for operator in OPERATORS:
        require(set(report['observation_refs'][operator]) == {str(i) for i in TIMELINES[operator]},
                'observation case selection changed')
        for case_id in TIMELINES[operator]:
            path = reference(report['observation_refs'][operator][str(case_id)])
            require(path.name == 'observation-report.json', 'wrong observation report')
            result = preparation.replay_task_observation(path.parent, qualification_dir=directory,
                                                        operator=operator, case_id=case_id)
            require(result.get('complete') is True, 'independent task observation did not complete')
            matches = [slot for slot in campaign['slots'].values()
                       if slot.get('operator') == operator and slot.get('observation') == result]
            require(len(matches) == 1, 'observation is not the unique registered campaign result')
            terminal = load(reference(matches[0]['terminal']))
            require(reference(terminal['observation_report']).resolve() == path.resolve(),
                    'observation report differs from registered terminal')
            observations[f'{operator}:{case_id}'] = {'report': bound(path), 'replay': result}
    report['_report_path'] = report_path
    installed = independent_install(root, report, current)
    require(release_tool(root).inventory(root) == current, 'candidate changed during replay')
    preparation.checked_plan(directory)
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
    return {'accepted': True, 'purpose': 'measurement_method_only_no_optimization_promotion',
        'protocol': protocol, 'metric': 'msprof.op_summary.Task_Duration',
        'publication_report': bound(report_path), 'candidate_inventory': bound(inventory_path),
        'old_release_manifest_sha256': BASELINE_MANIFEST, 'plan': bound(directory / 'plan.json'),
        'freeze': bound(directory / 'freeze.json'), 'attempt_roster': bound(roster_path),
        'retained_history': history,
        'confirmations': {op: {'receipt_ref': report['confirmations'][op]['receipt_ref'],
            'store_path': report['confirmations'][op]['store_path'], 'report': results[op]['replay']['report']}
            for op in OPERATORS},
        'observations': observations, 'independent_install': installed,
        'source_provenance': {'source_commit': head, 'source_state': 'working_tree_payload',
            'committed_payload_claimed': False, 'payload_inventory_sha256': canonical_digest(current),
            'qualification_producer_files': frozen['frozen_files']}}


def verify_measurement_publication(root: Path, report_path: Path) -> dict:
    """A fresh process prevents cached modules from selecting a different runtime."""
    result = subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--root', str(root), '--report', str(report_path)],
                            capture_output=True, text=True, timeout=1800)
    require(result.returncode == 0, result.stderr[-6000:] or 'independent publication replay failed')
    value = json.loads(result.stdout)
    require(value.get('accepted') is True, 'independent publication was not accepted')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--installed-probe', action='store_true')
    args = parser.parse_args()
    value = runtime_replay(args.root.resolve(), load(args.report)['confirmations'], installed=True) if args.installed_probe else verify_in_process(args.root, args.report)
    print(json.dumps(value, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
