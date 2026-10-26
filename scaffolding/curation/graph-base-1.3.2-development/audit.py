#!/usr/bin/env python3
"""完整开发审计：221 个归档、迁移分区、旧种子和纸面合同；仅 CPU。"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


ARCHIVE = Path(__file__).resolve().parent
EXPECTED_GROUPS = {'legacy-seed': 197, 'legacy-build-inputs': 8, 'paper-cases': 4,
                   'proposals': 3, 'audit-reports': 3, 'initialization-reports': 3,
                   'profiling-history': 3}


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def local(root, name):
    root = Path(root).resolve()
    rel = Path(name)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts:
        raise ValueError(f'unsafe audit path: {name}')
    path = root / rel
    if not path.resolve().is_relative_to(root) or any(
            p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(root)):
        raise ValueError(f'audit path escapes or is a symlink: {name}')
    return path


def verify_archive(root, archive=ARCHIVE):
    """审计材料和原覆盖；包安装校验由独立的 release.py 承担。"""
    root, archive = Path(root).resolve(), Path(archive).resolve()
    manifest = read(archive / 'relocation.json')
    if manifest['groups'] != EXPECTED_GROUPS or len(manifest['files']) != 221:
        raise ValueError('开发材料清单必须完整覆盖 221 个文件和七组材料')
    entries = {entry['original_path']: entry for entry in manifest['files']}
    if len(entries) != 221 or len({entry['path'] for entry in entries.values()}) != 221:
        raise ValueError('重复的开发材料身份')
    actual = {p.relative_to(archive).as_posix() for p in (archive / 'materials').rglob('*') if p.is_file()}
    if actual != {entry['path'] for entry in entries.values()}:
        raise ValueError('开发材料缺失或存在未登记文件')
    for entry in entries.values():
        path = local(archive, entry['path'])
        if entry['path'] != 'materials/' + entry['original_path'] or sha(path) != entry['sha256']:
            raise ValueError(f"归档 hash 或路径不匹配: {entry['original_path']}")
        if path.stat().st_size != entry['bytes']:
            raise ValueError(f"归档字节数不匹配: {entry['original_path']}")
        if entry['sha256'] != entry['original_sha256'] and entry['original_path'] not in manifest['edited_documents']:
            raise ValueError('非导航文件不能改写原始材料')

    def resolve(name):
        return local(archive, entries[name]['path']) if name in entries else local(root, name)

    baseline = read(archive / 'migration-baseline.json')
    if sha(archive / 'migration-baseline.json') != manifest['migration_baseline_sha256']:
        raise ValueError('迁移基准 hash 不符')
    current = read(root / 'workflows/migration/migration.json')
    archived = read(archive / 'migration-files.json')
    expected_rows = {row['original_path']: row for row in baseline['files']}
    combined = current['files'] + archived
    if (len(archived) != 8 or len(combined) != len(expected_rows)
            or {row['original_path']: row for row in combined} != expected_rows
            or {k: v for k, v in current.items() if k != 'files'} !=
               {k: v for k, v in baseline.items() if k != 'files'}):
        raise ValueError('安装与开发迁移清单必须无遗漏、无重复地重组原基准')
    if {row['path'] for row in archived} != {p for p, e in entries.items() if e['group'] == 'legacy-build-inputs'}:
        raise ValueError('迁移分区错误')
    for row in combined:
        path = resolve(row['path'])
        if not path.is_file() or row['disposition'].startswith('frozen') and sha(path) != row['original_hash']:
            raise ValueError(f"历史来源缺失或改变: {row['path']}")

    graph_base = 'skills/ascendc-aprof-diagnosis/graph/'
    seed_base = graph_base + 'history/seed-v0003/'
    seed = read(resolve(seed_base + 'files.json'))
    if len(seed['files']) != 196 or {e['path'] for e in seed['files']} != set(entries) & {
            p for p in entries if p.startswith(seed_base) and not p.endswith('/files.json')}:
        raise ValueError('旧种子清单覆盖不完整')
    for entry in seed['files']:
        if sha(resolve(entry['path'])) != entry['sha256']:
            raise ValueError('v0003 种子原字节改变')
    old = read(root / graph_base / 'versions/v0003/graph.json')
    if len(old['records']) != 195:
        raise ValueError('旧图记录数改变')
    for record in old['records']:
        name = seed_base + record['source_path'].removeprefix(graph_base)
        if sha(resolve(name)) != record['source_hash']:
            raise ValueError(f"旧图与种子身份不符: {record['id']}")
    if sha(root / 'runtime/src/aprof_runtime/_knowledge_v1.py') != manifest['frozen_compiler_sha256']:
        raise ValueError('冻结编译器字节改变')

    sys.path.insert(0, str(root / 'runtime/src'))
    from aprof_runtime.diagnosis_reasoning import validate_case, validate_proposal
    cases = [p for p, e in entries.items() if e['group'] == 'paper-cases']
    proposals = [p for p, e in entries.items() if e['group'] == 'proposals' and p.endswith('.json')]
    if len(cases) != 4 or len(proposals) != 2:
        raise ValueError('必须验证四个纸面案例和两项提案，不能跳过空目录')
    for name in cases:
        if validate_case(root, read(resolve(name)))['outcome']['status'] != 'not_run':
            raise ValueError('纸面案例不能伪装成已执行实验')
    for name in proposals:
        if validate_proposal(root, read(resolve(name)))['promotion']['eligible']:
            raise ValueError('pending 提案不能伪装成已满足晋升条件')
    return {'valid': True, 'archived_files': 221, 'migration_files': 8,
            'seed_records': 195, 'paper_cases': 4, 'proposals': 2}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path,
                        default=ARCHIVE.parents[2] / 'skill-libs/graph-base/1.3.2')
    args = parser.parse_args()
    root = args.root.resolve()
    spec = importlib.util.spec_from_file_location('development_release', root / 'tools/release.py')
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    release.verify_unsealed(root)
    print(json.dumps(verify_archive(root), ensure_ascii=False))


if __name__ == '__main__':
    main()
