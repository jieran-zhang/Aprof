#!/usr/bin/env python3
"""Hardlink identical, closed Cummin standalone and verifier outputs.

Both logical paths and every recorded hash remain valid. The manifest is durable
before any inode replacement; a partial run resumes only after rechecking bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid

from level2_storage import exclusive_host, write_new, sync_directory

VERSION = 'level2_correctness_output_dedup_v1'


def require(ok, why):
    if not ok:
        raise ValueError(why)


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return 'sha256:' + h.hexdigest()


def ref(path):
    return {'path': str(path), 'sha256': digest(path)}


def safe(path, root):
    path = Path(path)
    require(path.is_absolute() and path.is_relative_to(root) and '..' not in path.parts,
            'output path outside closed correctness stage')
    for part in (path, *path.parents):
        require(not part.is_symlink(), 'symlink output or ancestor')
    require(path.is_file() and stat.S_ISREG(path.stat().st_mode), 'missing regular output')
    return path


def inventory(stage):
    stage = Path(stage)
    require(stage.is_absolute() and '..' not in stage.parts and stage == stage.resolve(),
            'noncanonical correctness stage')
    owner = stage.parent.parent
    task = owner.parent.parent if owner.parent.name == 'candidates' else owner
    require(stage.name == 'correctness' and stage.parent.name == 'stages'
            and task.name == 'cummin' and task.parent.name == 'tasks'
            and task.parent.parent.name in ('train', 'validation', 'test'),
            'expected a closed correctness stage')
    result = read(stage / 'result.json')
    standalone = read(stage / 'standalone/completion.json')
    evidence = read(stage / 'evidence/completion.json')
    require(result.get('status') == standalone.get('status') == evidence.get('status') == 'passed'
            and result.get('kind') == 'correctness' and result.get('ended_at') is not None
            and standalone.get('planned_cases') == evidence.get('planned_cases')
            and len(standalone.get('completed', [])) == len(evidence.get('completed', [])) == 20,
            'correctness stage is not a complete passed 20-case result')
    pairs = []
    for row in standalone['completed']:
        cid = row['case_id']
        require(type(cid) is int and 1 <= cid <= 20 and isinstance(row.get('outputs'), dict)
                and set(row['outputs']) == {'values', 'indices'}, 'unexpected Cummin output roster')
        case = f'case_{cid:02d}'
        bundle_path = stage / 'evidence' / case / 'output.bin.outputs.json'
        bundle = read(bundle_path)
        require(bundle.get('version') == 'level2_output_bundle_v1' and bundle.get('operator') == 'cummin'
                and {x['name'] for x in bundle['outputs']} == {'values', 'indices'},
                'verifier bundle differs')
        for item in bundle['outputs']:
            name = item['name']
            source = safe(item['path'], stage)
            target_ref = row['outputs'][name]
            target = safe(target_ref['path'], stage)
            require(source == stage / 'evidence' / case / f'output.bin.{name}'
                    and target == stage / 'standalone' / case / f'output.bin.{name}'
                    and item['sha256'] == target_ref['sha256']
                    and item['bytes'] == source.stat().st_size == target.stat().st_size,
                    'independently verified output identity differs')
            pairs.append({'source': str(source), 'target': str(target),
                          'sha256': item['sha256'], 'size_bytes': item['bytes']})
    require(len(pairs) == 40 and len({p['target'] for p in pairs}) == 40,
            'incomplete or duplicate Cummin outputs')
    return {'version': VERSION, 'stage': str(stage), 'result': ref(stage / 'result.json'),
            'standalone_completion': ref(stage / 'standalone/completion.json'),
            'evidence_completion': ref(stage / 'evidence/completion.json'), 'pairs': pairs}


def deduplicate(stage, *, writers_closed=False):
    require(writers_closed is True, 'all correctness writers must be closed')
    stage = Path(stage)
    with exclusive_host():
        value = inventory(stage)
        destination = stage / 'correctness-output-dedup'
        require(not destination.is_symlink(), 'dedup namespace is a symlink')
        destination.mkdir(exist_ok=True)
        sync_directory(stage)
        manifest = destination / 'manifest.json'
        if manifest.exists():
            require(read(manifest) == value, 'prior immutable dedup manifest differs')
        else:
            write_new(manifest, value)
        sync_directory(destination)
        saved = 0
        for pair in value['pairs']:
            source, target = Path(pair['source']), Path(pair['target'])
            require(digest(source) == digest(target) == pair['sha256'],
                    'logical output bytes changed before linking')
            before_source, before_target = source.stat(), target.stat()
            if before_source.st_ino == before_target.st_ino:
                continue
            require(before_source.st_dev == before_target.st_dev,
                    'hardlink requires the same filesystem')
            temporary = target.with_name(target.name + '.aprof-link-' + uuid.uuid4().hex)
            try:
                os.link(source, temporary, follow_symlinks=False)
                os.replace(temporary, target)
                sync_directory(target.parent)
            finally:
                temporary.unlink(missing_ok=True)
            after = target.stat()
            require(after.st_ino == source.stat().st_ino and digest(target) == pair['sha256'],
                    'linked output failed post-replacement verification')
            saved += before_target.st_blocks * 512
        receipt = {'version': VERSION, 'status': 'complete', 'manifest': ref(manifest),
                   'logical_pairs': len(value['pairs']), 'source_bytes_preserved': True,
                   'space_reclaimed_estimate_bytes': saved}
        path = destination / 'completion.json'
        if path.exists():
            previous = read(path)
            require({k:v for k,v in previous.items() if k != 'space_reclaimed_estimate_bytes'} ==
                    {k:v for k,v in receipt.items() if k != 'space_reclaimed_estimate_bytes'},
                    'prior dedup receipt differs')
            receipt = previous
        else:
            write_new(path, receipt)
        for pair in value['pairs']:
            source, target = Path(pair['source']), Path(pair['target'])
            require(source.stat().st_ino == target.stat().st_ino
                    and digest(target) == pair['sha256'], 'closed output replay differs')
        return {'receipt': ref(path), **receipt}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--writers-closed', action='store_true')
    args = parser.parse_args()
    print(json.dumps(deduplicate(args.stage, writers_closed=args.writers_closed)))


if __name__ == '__main__':
    main()
