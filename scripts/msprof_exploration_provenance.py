"""Read-only dependency verification for explicitly frozen new-campaign producers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

REPOSITORY = Path(__file__).resolve().parents[1]
ENGINEERING_SCRIPTS = REPOSITORY / 'scripts'
CAMPAIGN_RUNS = REPOSITORY / '.aprof/runs'
PRODUCERS = {
    'msprof_exploration_execute.py', 'run_msprof_exploration_stage.py',
    'msprof_exploration_standalone.py', 'msprof_exploration_oracle.py',
    'msprof_exploration_report.py', 'msprof_exploration_archive.py',
    'msprof_exploration_safety.py', 'msprof_exploration_campaign.py',
    'msprof_exploration_provenance.py',
}
FRESH_PRODUCERS = PRODUCERS | {
    'level2_adapters.py', 'level2_pilot.py', 'level2_campaign.py',
    'level2_iteration.py', 'level2_boundaries.py',
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
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return 'sha256:' + h.hexdigest()


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
    except ValueError:
        return None
    if len(parts) < 5 or parts[1] not in ('train', 'validation') or parts[2] != 'tasks':
        return None
    root = CAMPAIGN_RUNS.resolve() / parts[0]
    if re.fullmatch(r'level1-msprof-feedback-\d{8}T\d{6}Z', parts[0]) or fresh_task_manifest(root, path):
        return root
    return None


def frozen_producer(origin, expected, *, evidence_path, semantic_path):
    """Return an attested old producer; never substitute a native/input identity."""
    run = campaign_root(evidence_path)
    task_manifest = fresh_task_manifest(run, evidence_path) if run else None
    producers = FRESH_PRODUCERS if task_manifest else PRODUCERS
    if (run is None or semantic_path not in (('producer',), ('campaign_build', 'generator'))
            or origin.parent != ENGINEERING_SCRIPTS.resolve() or origin.name not in producers
            or origin.is_symlink()):
        return None
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
                'binding_mode': 'frozen_engineering_snapshot'}
    return None


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
