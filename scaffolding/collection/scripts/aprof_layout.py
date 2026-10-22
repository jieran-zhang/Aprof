"""Explicit release selection and immutable campaign binding for collectors."""
from __future__ import annotations
import functools
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

REPOSITORY = Path(__file__).resolve().parents[3]
SCAFFOLDING = REPOSITORY / 'scaffolding'
SCRIPTS = Path(__file__).resolve().parent


def _argument(name):
    for index, item in enumerate(sys.argv[1:], 1):
        if item.startswith(name + '='):
            return item.split('=', 1)[1]
        if item == name and index + 1 < len(sys.argv):
            return sys.argv[index + 1]
    return None


def _binding_for_arguments():
    run = _argument('--run')
    if run:
        return Path(run).resolve() / 'skill-lib.json'
    task = _argument('--task')
    if task:
        path = Path(task).resolve()
        for parent in (path, *path.parents):
            if (parent / 'skill-lib.json').is_file():
                return parent / 'skill-lib.json'
    return None


def skill_lib():
    """Never resolve a mutable 'latest' alias or another checkout's source tree."""
    selected = _argument('--skill-lib') or os.environ.get('APROF_SKILL_LIB')
    binding_path = _binding_for_arguments()
    binding = json.loads(binding_path.read_text()) if binding_path and binding_path.is_file() else None
    if binding:
        frozen = Path(binding['path']).resolve()
        if selected and Path(selected).resolve() != frozen:
            raise ValueError('selected skill release differs from frozen campaign')
        selected = str(frozen)
    if not selected:
        raise ValueError('select a release with --skill-lib or APROF_SKILL_LIB; no implicit latest is used')
    root = Path(selected).resolve()
    if not (root / 'runtime/src/aprof_runtime').is_dir() or not any((root / name).is_file() for name in ('skills/registry.json', 'skillgraph/registry.json')):
        raise ValueError(f'not a complete skill release: {root}')
    if binding and _sha(root / 'release.json') != binding['manifest_sha256']:
        raise ValueError('frozen skill release manifest changed')
    if binding:
        _verify_bound_release(str(root), binding['manifest_sha256'])
    os.environ['APROF_SKILL_LIB'] = str(root)
    return root


@functools.lru_cache(maxsize=8)
def _verify_bound_release(root, manifest_hash):
    release_module(root).verify(root)


def _sha(path):
    return 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def release_module(root):
    spec = importlib.util.spec_from_file_location('aprof_selected_release', Path(root) / 'tools/release.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def identity(root=None):
    root = Path(root or skill_lib()).resolve()
    release = release_module(root).verify(root)
    runtime = sys.modules.get('aprof_runtime')
    if runtime and not Path(runtime.__file__).resolve().is_relative_to(root / 'runtime/src'):
        raise ValueError('a different release runtime is already loaded; select the release before starting Python')
    return {'path': str(root), 'release_id': release['release_id'],
            'manifest_sha256': _sha(root / 'release.json'), 'runtime_version': release['runtime_version'],
            'default_graph': release['default_graph'], 'graphs': release['graphs']}


def bind_run(run, root=None):
    run = Path(run).resolve()
    value = identity(root)
    path = run / 'skill-lib.json'
    if path.exists():
        if json.loads(path.read_text()) != value:
            raise ValueError('campaign skill release binding differs')
        return value
    if run.exists() and any(run.iterdir()):
        raise ValueError('cannot attach a new release to a historical run; use an explicit continuation epoch')
    run.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
    return value


def verify_run(run):
    path = Path(run).resolve() / 'skill-lib.json'
    if not path.is_file():
        raise ValueError('historical run has no release binding; use its frozen producer or an explicit continuation epoch')
    value = json.loads(path.read_text())
    if identity(value['path']) != value:
        raise ValueError('frozen campaign release changed')
    if skill_lib() != Path(value['path']):
        raise ValueError('loaded release differs from campaign')
    return value
