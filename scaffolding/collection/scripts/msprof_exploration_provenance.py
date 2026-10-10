"""Read-only dependency verification for explicitly frozen new-campaign producers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from msprof_search_protocol import LITE_PROTOCOL, LITE_PRODUCER

REPOSITORY = Path(__file__).resolve().parents[3]
ENGINEERING_SCRIPTS = REPOSITORY / 'scaffolding/collection/scripts'
CAMPAIGN_RUNS = REPOSITORY / '.aprof/runs'
LEGACY_RUNS = REPOSITORY.parent / 'aprof/.aprof/runs'
LEGACY_SCRIPTS = REPOSITORY.parent / 'aprof/scripts'
PRODUCERS = {
    'msprof_exploration_execute.py', 'run_msprof_exploration_stage.py',
    'msprof_exploration_standalone.py', 'msprof_exploration_oracle.py',
    'msprof_exploration_report.py', 'msprof_exploration_archive.py',
    'msprof_exploration_safety.py', 'msprof_exploration_campaign.py',
    'msprof_exploration_provenance.py', 'msprof_search_protocol.py',
}
FRESH_PRODUCERS = PRODUCERS | {
    "level2_stage_recovery.py", "level2_prestart_recovery.py", "level2_gather_search_recovery.py", "level2_cohort_continuation.py", "level2_failed_capture_preservation.py",
    'level2_adapters.py', 'level2_pilot.py', 'level2_campaign.py',
    'level2_iteration.py', 'level2_boundaries.py', 'level2_finalize.py',
    'level2_guard_contract.py', 'level2_candidate_guard.py',
    'level2_final_report_authority.py', 'level2_final_report_attestation.py',
    'level2_native_output_storage.py', 'level2_verification_storage.py',
    'level2_raw_archive_storage.py', 'level2_evidence_storage.py', 'msprof_storage_protocol.py',
    'level2_storage.py', 'level2_failure_classification.py', 'level2_raw_method.py', 'msprof_raw_storage.py',
    'cannbench_msprof_timing.py', 'cannbench_shared_context.py',
    'cannbench_shared_context_profile.py', 'shared_context_build.py',
}


def fresh_task_manifest(run, evidence_path):
    """A fresh campaign is identified by its declared task, not a name prefix."""
    parts = Path(evidence_path).relative_to(run).parts
    if len(parts) < 4 or parts[0] not in ('train', 'validation') or parts[1] != 'tasks':
        return None
    task = run / parts[0] / 'tasks' / parts[2]
    path = task / 'manifest.json'
    if path.is_symlink() or not path.is_file():
        return None
    value = load(path)
    if (value.get('version') != 'msprof_task_time_exploration_v2'
            or value.get('run_id') != run.name or value.get('operator') != parts[2]
            or value.get('split') != parts[0] or value.get('task_dir') != str(task)
            or value.get('source_split') not in ('train', 'validation', 'test')
            or value['split'] != ('validation' if value['source_split'] == 'validation' else 'train')):
        return None
    return path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    import level2_verification_storage as evidence_storage
    return evidence_storage.fingerprint(path)['sha256']


def load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate frozen provenance key')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs)


def campaign_root(evidence_path):
    if evidence_path is None:
        return None
    path = Path(evidence_path)
    if not path.is_absolute() or path != path.resolve():
        return None
    try:
        parts = path.relative_to(CAMPAIGN_RUNS.resolve()).parts
        runs = CAMPAIGN_RUNS.resolve()
    except ValueError:
        try:
            parts = path.relative_to(LEGACY_RUNS.resolve()).parts
            runs = LEGACY_RUNS.resolve()
        except ValueError:
            return None
    if len(parts) < 5 or parts[1] not in ('train', 'validation') or parts[2] != 'tasks':
        return None
    root = runs / parts[0]
    if runs == LEGACY_RUNS.resolve():
        from level2_legacy_epoch import check
        requests = sorted((root / 'preflight').glob('resume-epoch-*/request.json'))
        if not requests:
            return None
        check(requests[-1])
    if re.fullmatch(r'level1-msprof-feedback-\d{8}T\d{6}Z', parts[0]) or fresh_task_manifest(root, path):
        return root
    return None



def resolve_continuation(cohort, read_bytes=Path.read_bytes, *, require_closed=False):
    """Ordinary cohorts must not import the optional continuation producers."""
    cohort=Path(cohort)
    if cohort.parts[-6:] != ('dynamic_quant','candidates','dynamic_quant001','stages','search','direct_parent'):return None
    try:read_bytes(cohort/'continuation-01/qualification.json')
    except FileNotFoundError:return None
    from level2_cohort_continuation import resolve
    return resolve(cohort, read_bytes, require_closed=require_closed)


def closed_observation_code(origin, expected, evidence_path):
    """Authorize only known code identities actually bound by a closed fresh session."""
    directory=Path(evidence_path).parent
    if Path(evidence_path).name!='completion.json' or directory!=directory.resolve():
        return None
    run=campaign_root(evidence_path)
    if run is None or fresh_task_manifest(run,evidence_path) is None:
        return None
    scripts=ENGINEERING_SCRIPTS.resolve()
    eligible=(origin.parent==scripts and origin.name in FRESH_PRODUCERS) or origin==scripts.parent/'src/aprof_runtime/planning.py'
    if not eligible or origin.is_symlink() or origin!=origin.resolve():
        return None
    relative=directory.relative_to(run).parts
    tail=relative[3:]
    if tail[:1]==('candidates',):tail=tail[2:]
    if not (len(tail)==4 and tail[0]=='stages' and tail[2] in ('cohort','direct_parent','original_baseline')):
        return None
    stage=directory.parent.parent;cohort=directory.parent
    paths={'completion':directory/'completion.json','bindings':directory/'bindings.json',
           'request':directory/'request.json','execution':directory/'msprof.execution.json',
           'stage_result':stage/'result.json','group_completion':cohort/'group-completion.json'}
    recovery = None
    if not paths['stage_result'].exists():
        # Only the explicitly certified original completed prefix may reuse old
        # producer bytes while the same timing attempt remains ledger-active.
        continuation = resolve_continuation(cohort)
        if continuation is not None and str(directory) in continuation['directories'][:2]:
            require(load(paths['bindings']).get(str(origin)) == expected, 'producer not bound by reused observation')
            return {'completion': {'path': str(paths['completion']), 'sha256': sha(paths['completion'])},
                    'cohort_continuation': continuation}
        return None
    if load(paths['stage_result']).get('status') != 'passed' and (stage.name == 'final' or
            stage == run/'train/tasks/gather/candidates/gather003/stages/search'):
        from level2_stage_recovery import resolve_from_reader
        recovery = resolve_from_reader(stage, require_success=True)
        paths['stage_result'] = Path(recovery['current_result']['path'])
    require(all(p.is_file() and not p.is_symlink() and p==p.resolve() for p in paths.values()),'closed observation proof is missing or aliased')
    documents={key:load(path) for key,path in paths.items()}
    completion=documents['completion'];execution=documents['execution'];stage_result=documents['stage_result'];group=documents['group_completion']
    lite = documents['request'].get('version') == LITE_PRODUCER
    expected_processes = 2 if lite else 6
    require(documents['request'].get('version') in ('msprof_kernel_time_study_v2', LITE_PRODUCER)
            and completion.get('version')==documents['request']['version'] and completion.get('status')=='passed'
            and completion.get('error') is None and completion.get('formal_admission')=='not_evaluated',
            'observation code fallback requires a passed versioned session')
    require(execution.get('exit_code')==0 and execution.get('error') is None and execution.get('ended_at') is not None,
            'observation code fallback requires a completed native execution')
    require(stage_result.get('status')=='passed' and stage_result.get('error') is None
            and stage_result.get('ended_at') is not None and group.get('status')=='passed' and group.get('error') is None
            and str(directory) in group.get('completed_sessions',[]) and len(set(group['completed_sessions']))==len(group['completed_sessions'])==expected_processes,
            'observation code fallback requires a terminal protocol-sized cohort')
    if lite:
        require(group.get('protocol') == LITE_PROTOCOL, 'lite observation cohort protocol differs')
    require(documents['bindings'].get(str(origin))==expected,'producer was not bound by this exact observation')
    proof = {key:{'path':str(path),'sha256':sha(path)} for key,path in paths.items()}
    if recovery is not None:proof['stage_recovery'] = recovery
    continuation = resolve_continuation(cohort, require_closed=True)
    if continuation is not None:proof['cohort_continuation'] = continuation
    return proof


def frozen_producer(origin, expected, *, evidence_path, semantic_path):
    """Return an attested old producer; never substitute a native/input identity."""
    run = campaign_root(evidence_path)
    task_manifest = fresh_task_manifest(run, evidence_path) if run else None
    producers = FRESH_PRODUCERS if task_manifest else PRODUCERS
    observation=None
    if semantic_path==('observation_binding',):
        observation=closed_observation_code(origin,expected,evidence_path)
        if observation is None:return None
    elif (run is None or semantic_path not in (('producer',), ('campaign_build', 'generator'))
            or origin.parent not in (ENGINEERING_SCRIPTS.resolve(), LEGACY_SCRIPTS.resolve()) or origin.name not in producers
            or origin.is_symlink()):
        return None
    if origin.parent == LEGACY_SCRIPTS.resolve():
        require(run.is_relative_to(LEGACY_RUNS.resolve()), 'legacy producer requires a bound continuation')
    for manifest in sorted((run / 'bootstrap').glob('frozen-engineering*.json')):
        require(not manifest.is_symlink() and manifest.resolve() == manifest,
                'frozen engineering manifest location differs')
        value = load(manifest)
        require(isinstance(value.get('files'), list), 'invalid frozen engineering manifest')
        matching = [item for item in value['files'] if isinstance(item, dict)
                    and item.get('path') == str(origin) and item.get('sha256') == expected]
        if not matching:
            continue
        if task_manifest:
            declared = [entry for entry in value.get('task_manifests', []) if isinstance(entry, dict)
                        and entry.get('path') == str(task_manifest) and entry.get('sha256') == sha(task_manifest)]
            require(len(declared) == 1, 'fresh frozen producer requires an exact task manifest binding')
        target = run / 'bootstrap/source-cas' / expected[7:]
        for item in matching:
            snapshot = Path(item.get('snapshot', ''))
            require(snapshot.is_absolute() and snapshot == target and snapshot.resolve() == target
                    and not snapshot.is_symlink(), 'frozen engineering snapshot location differs')
            require(snapshot.is_file() and sha(snapshot) == expected, 'frozen engineering snapshot hash differs')
        return {'origin': {'path': str(origin), 'sha256': expected},
                'snapshot': {'path': str(target), 'sha256': expected},
                'frozen_manifest': {'path': str(manifest), 'sha256': sha(manifest)},
                'binding_mode': 'frozen_engineering_snapshot',
                **({'closed_observation':observation} if observation is not None else {})}
    return None


def legacy_harness_readme(expected, evidence_path):
    """Authenticate the sole moved harness README without loading old code."""
    run = campaign_root(evidence_path)
    if run is None or not run.is_relative_to(LEGACY_RUNS.resolve()):
        return False
    origin = LEGACY_RUNS.parent.parent / 'benchmarks/cannbench/harness/shared_context/README.md'
    old = run / 'bootstrap/frozen-engineering-026.json'
    rows = [row for row in load(old)['files']
            if row.get('path') == str(origin) and row.get('sha256') == expected]
    return len(rows) == 1 and sha(origin) == expected and sha(rows[0]['snapshot']) == expected


def verify_pointer_tree(value, *, evidence_path, producer_bindings=None):
    """Verify pointer bytes and return their exact closure without executing code."""
    paths = []
    def visit(node, semantic_path=()):
        if isinstance(node, dict):
            if isinstance(node.get('path'), str) and isinstance(node.get('sha256'), str):
                path = Path(node['path'])
                expected = node['sha256']
                expected = expected if expected.startswith('sha256:') else 'sha256:' + expected
                require(path.is_absolute() and re.fullmatch(r'sha256:[0-9a-f]{64}', expected),
                        'invalid dependency pointer identity')
                actual = sha(path)
                if actual == expected:
                    paths.append(path)
                else:
                    binding = frozen_producer(path, expected, evidence_path=evidence_path, semantic_path=semantic_path)
                    require(binding is not None, 'dependency pointer hash differs: ' + str(path))
                    paths.extend(Path(binding[key]['path']) for key in ('snapshot', 'frozen_manifest'))
                    if producer_bindings is not None and binding not in producer_bindings:
                        producer_bindings.append(binding)
            for key, item in node.items():
                visit(item, (*semantic_path, key))
        elif isinstance(node, list):
            for index, item in enumerate(node):
                visit(item, (*semantic_path, index))
    visit(value)
    return paths
