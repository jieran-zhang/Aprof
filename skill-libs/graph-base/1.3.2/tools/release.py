#!/usr/bin/env python3
"""Verify a self-contained release without the development checkout."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import tomllib
import sys

IGNORED = {'__pycache__', '.runtime-env', '.pytest_cache', '.git', '.cursor', 'build', 'dist', '.eggs'}


def sha(path):
    return 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local(root, name):
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise ValueError(f'unsafe release path: {name}')
    path = root / relative
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f'release symlink: {part}')
        if part == root:
            break
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'release path escapes package: {name}')
    return path


def inventory(root):
    root = Path(root)
    result = {}
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if (any(part in IGNORED or part.endswith('.egg-info') for part in rel.parts)
                or path.suffix in {'.pyc', '.pyo'} or rel.as_posix() == 'release.json'):
            continue
        local(root, rel)
        if path.is_file():
            result[rel.as_posix()] = sha(path)
    return result


def registry_path(root):
    root = Path(root)
    return root / ("skills/registry.json" if (root / "skills/registry.json").is_file() else "skillgraph/registry.json")


def graph_paths(root):
    root = Path(root)
    base = root / "skills/ascendc-aprof-diagnosis/graph"
    if base.is_dir():
        return sorted((base / "history/versions").glob("v*")) + sorted((base / "versions").glob("v*"))
    return sorted((root / "skillgraph/versions").glob("v*"))


def verify_knowledge(root):
    sys.path.insert(0, str(Path(root) / "runtime/src"))
    from aprof_runtime.knowledge import REGIONS, verify as verify_region
    from aprof_runtime.graph import load_snapshot
    for owner in REGIONS:
        region = Path(root) / REGIONS[owner]
        identity = json.loads((region / 'REGION.json').read_text())
        if owner == 'diagnosis' and identity.get('schema_version') == 'aprof.diagnosis-region/v1':
            from aprof_runtime.diagnosis import verify
            verify(Path(root))
        else:
            verify_region(Path(root), owner)
    for path in graph_paths(root):
        graph, _ = load_snapshot(path)
        if graph.get('schema_version') == 'aprof.diagnosis-graph/v1':
            from aprof_runtime.diagnosis import verify_snapshot
            verify_snapshot(Path(root), path)
    diagnosis_identity = json.loads((Path(root) / REGIONS['diagnosis'] / 'REGION.json').read_text())
    if diagnosis_identity.get('schema_version') == 'aprof.diagnosis-region/v1':
        verify_mechanism_package(Path(root))
    migration = json.loads((Path(root) / 'workflows/migration/migration.json').read_text())
    source_files = {item['original_path']: item for item in migration['files']}
    for item in source_files.values():
        target = local(Path(root), item['path'])
        if not target.is_file():
            raise ValueError(f"迁移文件去向不存在: {item['path']}")
        if item['disposition'].startswith('frozen') and sha(target) != item['original_hash']:
            raise ValueError(f"历史来源字节改变: {item['path']}")
    identifiers = set()
    tags = {'tiling', 'data_movement', 'pipeline_parallel', 'onchip_memory', 'ai_core_utilization', 'api_algorithm'}
    for item in migration['items']:
        if item['id'] in identifiers or not item.get('targets') or not item.get('reason'):
            raise ValueError('迁移条目重复或缺少去向/理由')
        identifiers.add(item['id'])
        if item['source'] not in source_files or item['source_hash'] != source_files[item['source']]['original_hash']:
            raise ValueError('迁移条目来源身份不匹配')
        for target in item['targets']:
            if target not in tags and not local(Path(root), target).is_file():
                raise ValueError(f'迁移目标不存在: {target}')
    for version in ('v0001', 'v0002'):
        path = next(p for p in graph_paths(root) if p.name == version)
        graph = json.loads((path / 'graph.json').read_text())
        expected = {f"{version}:{item['id']}" for kind in ('anchors', 'predicates', 'mechanisms', 'transformations', 'edges') for item in graph[kind]}
        if not expected <= identifiers:
            raise ValueError(f'{version} 存在未登记迁移的节点或边')
    for original, entry in source_files.items():
        if (not original.endswith('.md') or original.endswith('/NOTICE.md')
                or not any(original.startswith(prefix) for prefix in (
                    'skills/ascendc-aprof-diagnosis/references/',
                    'skills/ascendc-aprof-optimization/references/',
                    'skills/ascendc-perf-optimize/', 'skills/ascendc-tiling-design/',
                    'skills/ascendc-performance-best-practices/'))):
            continue
        lines = local(Path(root), entry['path']).read_text().splitlines()
        for number, line in enumerate(lines, 1):
            line = line.strip()
            row = (line.startswith('|') and not re.fullmatch(r'\|[\s:|\-]+', line)
                   and (number == len(lines) or not re.fullmatch(r'\|[\s:|\-]+', lines[number].strip())))
            rule = re.match(r'^(?:[-*]|\d+[.)])\s+', line)
            if (row or rule) and f'{original}:L{number}' not in identifiers:
                raise ValueError(f'矩阵行或路由规则漏迁移: {original}:L{number}')
    for path in Path(root).rglob('*.md'):
        if any(part in IGNORED | {'history', 'knowledge-history', 'archive', 'sources'} for part in path.relative_to(root).parts):
            continue
        body = re.sub(r'```.*?```', '', path.read_text(), flags=re.S)
        for link in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)', body):
            link = link.split('#')[0].strip('<>')
            if not link or re.match(r'\w+://', link) or link.startswith('mailto:'):
                continue
            target = (path.parent / link).resolve()
            if not target.is_relative_to(Path(root).resolve()) or not target.exists():
                raise ValueError(f'本地链接失效: {path.relative_to(root)} -> {link}')


def verify_mechanism_package(root):
    """核对迁移身份、不可变路由及包内材料，不把检查报告当作真实性证明。"""
    from aprof_runtime import bindings, diagnosis
    from aprof_runtime.jsonio import canonical_json
    skill = root / 'skills/ascendc-aprof-diagnosis'
    graph = diagnosis.verify(root)
    # v0003→v0004 迁移台账保持原义；后续条件修订由独立冻结策略校验。
    migration_graph = diagnosis.verify_snapshot(root, skill / 'graph/versions/v0004') if graph['version'] != 'v0004' else graph
    old = json.loads((skill / 'graph/versions/v0003/graph.json').read_text())
    old_records = {r['id']: r for r in old['records']}
    current = {r['id']: r for r in migration_graph['records']}
    ledger = json.loads((skill / 'migration-ledger.json').read_text())
    rows = {r['id']: r for r in ledger['records']}
    if len(rows) != len(ledger['records']) or set(rows) != set(old_records):
        raise ValueError('诊断迁移台账必须逐项覆盖旧记录')
    for identifier, before in old_records.items():
        after, row = current[identifier], rows[identifier]
        if row['old_file_sha256'] != before['source_hash'] or row['new_file_sha256'] != after['source_hash']:
            raise ValueError(f'诊断迁移来源身份不匹配: {identifier}')
        fields = ['kind', 'learning']
        if before['kind'] == 'action':
            fields += ['preconditions', 'invariants']
        if before['kind'] == 'edge':
            fields += ['relation', 'from', 'to', 'conditions']
        if any(canonical_json(before[k]) != canonical_json(after[k]) for k in fields):
            raise ValueError(f'旧记录的身份或原有前提改变: {identifier}')
    if set(current) - set(old_records) != set(ledger['new_relations']):
        raise ValueError('新增诊断记录与迁移台账不符')
    if graph['version'] != 'v0004':
        from aprof_runtime.action_decision import condition_policy
        condition_policy(root, graph)
    manifests = ['workflows/references/knowledge-sources-1.3.0.json']
    if int(graph['version'][1:]) >= 6:
        manifests.append('workflows/references/knowledge-sources-selection-v2.json')
    if int(graph['version'][1:]) >= 7:
        manifests.append('workflows/references/knowledge-sources-execution-cost-v1.json')
    paths = set()
    for name in manifests:
        manifest = json.loads((root / name).read_text())
        if len(manifest['archived_files']) != manifest['archived_file_count']:
            raise ValueError('来源档案计数不符')
        for entry in manifest['archived_files']:
            path = local(root, entry['path'])
            if entry['path'] in paths or sha(path) != entry['sha256'] or path.stat().st_size != entry['bytes']:
                raise ValueError(f"来源档案身份不符或重复: {entry['path']}")
            paths.add(entry['path'])
    history = root / 'workflows/references/knowledge-history/manifest.json'
    if history.is_file():
        for entry in json.loads(history.read_text())['files']:
            if sha(local(root, entry['archive_path'])) != entry['sha256']:
                raise ValueError('历史知识正文归档 hash 不匹配')
    config = bindings.load_routing(root)
    bindings.load_frozen_bundle(root, bindings.routing_snapshot_ref(root, config))
    for path in (root / bindings.ROUTING_SNAPSHOTS).glob('*.json'):
        bindings.load_frozen_bundle(root, {'path': path.relative_to(root).as_posix(), 'sha256': sha(path)})


def registry_errors(root):
    root = Path(root)
    registry = json.loads(registry_path(root).read_text())
    errors, names, sources = [], set(), set()
    entries = [e for rows in registry['capabilities'].values() for e in rows] + registry['support_skills']
    for entry in entries:
        name, source = entry['name'], entry['source']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) or name in names:
            errors.append(f'invalid or duplicate capability: {name}')
        names.add(name)
        if source in sources:
            errors.append(f'duplicate capability source: {source}')
        sources.add(source)
        try:
            path = local(root, source)
            if path.parent != root / 'skills' or path.name != name:
                raise ValueError(f'capability must have its canonical directory: {source}')
            text = (path / 'SKILL.md').read_text()
            if not re.search(r'^name:\s*' + re.escape(name) + r'\s*$', text, re.M):
                errors.append(f'skill frontmatter name mismatch: {name}')
        except (ValueError, OSError) as exc:
            errors.append(str(exc))
    expected = {e['name'] for e in registry['capabilities']['core'] + registry['support_skills']}
    for entry in registry['support_skills']:
        if not entry.get('trigger') or not entry.get('roles') or set(entry['roles']) - {'coordinator', 'code-understanding', 'diagnosis', 'parallel-planning', 'optimization', 'profiling'}:
            errors.append(f"support skill lacks valid role/trigger: {entry['name']}")
    actual = {p.name for p in (root / 'skills').iterdir() if p.is_dir() and p.name not in IGNORED}
    if actual != expected:
        errors.append('skill inventory differs from registry')
    agents = {}
    for entry in registry['cursor_agents']:
        name, source = entry['name'], entry['source']
        if name in agents or source in agents.values():
            errors.append(f'duplicate agent: {name}')
        agents[name] = source
        try:
            path = local(root, source)
            if path != root / 'AGENTS.md' and path.parent != root / 'workflows/agents':
                raise ValueError(f'agent must belong to workflow: {source}')
            if not re.search(r'^name:\s*' + re.escape(name) + r'\s*$', path.read_text(), re.M):
                errors.append(f'agent frontmatter name mismatch: {name}')
        except (ValueError, OSError) as exc:
            errors.append(str(exc))
    workflow_agents = registry['workflow_plugin']['agents']
    expected_agents = {source for source in agents.values() if source != 'AGENTS.md'}
    actual_agents = {p.relative_to(root).as_posix() for p in (root / 'workflows/agents').glob('*.md')}
    if (len(workflow_agents) != len(set(workflow_agents))
            or set(workflow_agents) != expected_agents or actual_agents != expected_agents):
        errors.append('workflow agent inventory differs from registry')
    version = registry['library']['version']
    for host in ('.codex-plugin', '.claude-plugin'):
        manifest = json.loads((root / host / 'plugin.json').read_text())
        if manifest['name'] != registry['workflow_plugin']['name'] or manifest['version'] != version:
            errors.append(f'{host} identity differs from registry')
        if host == '.claude-plugin':
            listed = manifest.get('agents', [])
            if sorted(listed) != sorted('./' + source for source in workflow_agents):
                errors.append('plugin agents differ from workflow registry')
    return errors


def verify(root, *, check_knowledge=True):
    root = Path(root).resolve()
    manifest = json.loads((root / 'release.json').read_text())
    if manifest.get('schema_version') != 1 or manifest.get('status') != 'stable':
        raise ValueError('expected a sealed stable release')
    actual = inventory(root)
    if actual != manifest['files']:
        changed = sorted(k for k in actual.keys() | manifest['files'].keys()
                         if actual.get(k) != manifest['files'].get(k))
        raise ValueError('release bytes differ: ' + ', '.join(changed[:12]))
    errors = registry_errors(root)
    if errors:
        raise ValueError('; '.join(errors))
    if check_knowledge and (root / 'skills/registry.json').is_file():
        verify_knowledge(root)
    return manifest


def verify_unsealed(root, *, check_knowledge=True):
    """Check a complete development package, without granting release acceptance."""
    root = Path(root).resolve()
    if (root / 'release.json').exists() or (root / 'release.json').is_symlink():
        raise ValueError('unsealed check requires no release.json; verify the sealed release instead')
    actual = inventory(root)
    required = (
        'AGENTS.md', 'README.md', 'tools/aprofctl', 'tools/install.py', 'tools/release.py',
        'runtime/pyproject.toml', 'runtime/src/aprof_runtime/__init__.py',
        'runtime/src/aprof_runtime/__main__.py', 'runtime/src/aprof_runtime/cli.py',
        'runtime/src/aprof_runtime/knowledge.py', 'runtime/src/aprof_runtime/_knowledge_v1.py',
        'schemas/context.schema.json', 'schemas/gate-request.schema.json',
        'schemas/gate-outcome.schema.json', 'skills/registry.json',
        'workflows/migration/migration.json', 'workflows/aprof-performance-workflow.md',
        'workflows/contracts/common.md', 'workflows/contracts/preparation.md',
        'workflows/contracts/code-understanding.md',
        'workflows/contracts/diagnosis.md', 'workflows/contracts/planning.md',
        'workflows/contracts/candidate.md', 'workflows/contracts/profiling.md',
        'workflows/contracts/decision.md', 'workflows/references/runtime-contracts.md',
    )
    missing = [name for name in required if name not in actual]
    if missing:
        raise ValueError('incomplete package: ' + ', '.join(missing))
    errors = registry_errors(root)
    if errors:
        raise ValueError('; '.join(errors))
    registry = json.loads(registry_path(root).read_text())
    version = registry['library']['version']
    project = tomllib.loads((root / 'runtime/pyproject.toml').read_text())['project']
    if (not re.fullmatch(r'\d+\.\d+\.\d+', version)
            or project['name'] != 'aprof-runtime'
            or not re.fullmatch(r'\d+\.\d+\.\d+', project['version'])):
        raise ValueError('invalid package or runtime identity')
    if tuple(map(int, project['version'].split('.'))) >= (0, 8, 0):
        scheme_files = ('schemas/action-decision-v3.schema.json',
                        'schemas/knowledge-handoff-v4.schema.json',
                        'runtime/src/aprof_runtime/action_decision_v3.py',
                        'runtime/src/aprof_runtime/bindings_v4.py',
                        'workflows/references/optimization-schemes.md',
                        'workflows/references/optimization-history.md')
        missing = [name for name in scheme_files if name not in actual]
        if missing:
            raise ValueError('incomplete scheme protocol: ' + ', '.join(missing))
    if check_knowledge:
        verify_knowledge(root)
    return {'schema_version': 1, 'status': 'unsealed', 'verification': 'structure_only',
            'release_id': f'graph-base/{version}', 'runtime_version': project['version'],
            'files': actual, 'publication_accepted': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--allow-unsealed', action='store_true',
                        help='check development package structure only; does not seal or approve publication')
    args = parser.parse_args()
    release = verify_unsealed(args.root) if args.allow_unsealed else verify(args.root)
    print(json.dumps({'valid': True, 'release_id': release['release_id'], 'files': len(release['files']),
                      'status': release['status'],
                      'verification': release.get('verification', 'sealed_payload')}))


if __name__ == '__main__':
    main()
