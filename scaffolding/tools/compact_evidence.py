#!/usr/bin/env python3
"""Export and verify a small, byte-preserving view of the external trace library."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'collection/scripts'))
from organize_optimization_traces import safe_path, entry_bytes

MAX_FILE_BYTES = 16 * 1024 * 1024
SOURCE_ARTIFACT = re.compile(r'^(train|validation)/tasks/[^/]+/(baseline-source\.tar|candidates/[^/]+/(source\.tar|proposal\.json|source-binding\.json|parallel_plan\.json|dispatch_plan\.json|dispatch-launch\.json|patch\.(?:diff|patch)))$')


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def export(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if (output / 'index.json').exists():
        raise ValueError('compact index already exists; use a new export directory')
    original_bytes = safe_path(source, 'index.json').read_bytes()
    original = json.loads(original_bytes)
    files = {}

    def add(key, destination, data, expected=None):
        if len(data) > MAX_FILE_BYTES:
            raise ValueError(f'compact file limit exceeded: {key}')
        actual = digest(data)
        if expected and actual != expected:
            raise ValueError(f'source bytes differ from indexed hash: {key}')
        path = safe_path(output, destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
        files[key] = {'path': destination, 'sha256': actual, 'size_bytes': len(data)}

    add('source/index.json', 'traces/source-catalog.json', original_bytes)
    for dataset in original['level1']['datasets']:
        base = dataset['local_path']
        for split in ('train', 'validation'):
            for filename in ('optimization_traces.jsonl', 'lessons.jsonl'):
                key = f'{base}/current/{split}/{filename}'
                category = 'lessons' if filename == 'lessons.jsonl' else 'traces'
                add(key, f'{category}/{key}', safe_path(source, key).read_bytes())
        key = f'{base}/current.json'
        add(key, 'traces/' + key, safe_path(source, key).read_bytes())
    for filename, category in (('memory-catalog.json', 'traces'), ('lesson-catalog.json', 'lessons')):
        key = 'level1/' + filename
        add(key, category + '/' + key, safe_path(source, key).read_bytes())
    level2 = original['level2']
    base = level2['local_path']
    indexed = json.loads(safe_path(source, base + '/file-index.json').read_bytes())
    for key in level2['readable_files']:
        destination = 'traces/' + key.replace('/readable/', '/')
        logical = key.split('/readable/', 1)[1]
        add(key, destination, safe_path(source, key).read_bytes(), indexed[logical].get('sha256'))
    for name in ('source_attempts.jsonl', 'status.json'):
        key = base + '/' + name
        add(key, 'traces/' + key, safe_path(source, key).read_bytes())
    for logical, entry in indexed.items():
        if not SOURCE_ARTIFACT.fullmatch(logical):
            continue
        if entry['size_bytes'] > MAX_FILE_BYTES or 'sha256' not in entry:
            raise ValueError(f'compact source artifact must be bounded and hashed: {logical}')
        key = base + '/' + logical
        add(key, 'traces/' + key, b''.join(entry_bytes(source, entry)), entry['sha256'])
    maintenance = source / 'maintenance'
    if maintenance.is_dir():
        for path in sorted(maintenance.glob('*.json')):
            key = 'maintenance/' + path.name
            add(key, 'traces/' + key, safe_path(source, key).read_bytes())
    # Existing selected-source deliveries are included without rewriting their records.
    deliveries = output / 'deliveries'
    if deliveries.is_dir():
        for path in sorted(deliveries.rglob('*')):
            if path.is_file():
                relative = path.relative_to(output).as_posix()
                data = safe_path(output, relative).read_bytes()
                files[relative] = {'path': relative, 'sha256': digest(data), 'size_bytes': len(data)}
    value = {'schema_version': 1, 'kind': 'compact_optimization_evidence',
             'offline_evidence_complete': False,
             'level1': {k: original['level1'][k] for k in ('memory_rows', 'lesson_rows', 'unique_memory_revisions', 'unique_lesson_revisions')},
             'level2': {k: level2[k] for k in ('status', 'closed_attempts', 'source_attempts_planned', 'graph_policy_eligible', 'episode_ref', 'published_lessons', 'published_optimization_memories')},
             'external': {'root_hint': str(source), 'index_sha256': digest(original_bytes),
                          'raw_bytes': level2['external_raw_bytes'], 'raw_files': level2['external_raw_files'],
                          'full_file_index': base + '/file-index.json', 'raw_inventory': base + '/external-raw-inventory.json',
                          'note': 'Original paths are provenance. Use archive readers and maintenance receipts for retired raw. No original-path fallback.'},
             'files': files}
    with (output / 'index.json').open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write('\n')
    return verify(output)


def read(root, key):
    root = Path(root).resolve()
    value = json.loads(safe_path(root, 'index.json').read_bytes())
    if key not in value['files']:
        raise FileNotFoundError(f'evidence is external or not selected: {key}; no original-path fallback')
    row = value['files'][key]
    data = safe_path(root, row['path']).read_bytes()
    if len(data) != row['size_bytes'] or digest(data) != row['sha256']:
        raise ValueError(f'compact evidence changed: {key}')
    return data


def verify(root):
    root = Path(root).resolve()
    value = json.loads(safe_path(root, 'index.json').read_bytes())
    if value['kind'] != 'compact_optimization_evidence' or value['offline_evidence_complete'] is not False:
        raise ValueError('compact evidence cannot claim full offline closure')
    total = 0
    for key in value['files']:
        total += len(read(root, key))
    return {'valid': True, 'files': len(value['files']), 'bytes': total,
            'offline_evidence_complete': False, 'level1': value['level1'], 'level2': value['level2']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('export', 'verify', 'read'))
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--key')
    args = parser.parse_args()
    if args.command == 'read':
        sys.stdout.buffer.write(read(args.root, args.key))
    else:
        if args.command == 'export' and args.source is None:
            parser.error('export requires --source')
        print(json.dumps(export(args.source, args.root) if args.command == 'export' else verify(args.root)))


if __name__ == '__main__':
    main()
