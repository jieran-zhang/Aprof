"""1.3.0 新知识入口、跨代隔离与真实独立目录演练；只使用 CPU。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from aprof_runtime.knowledge import digest, route_tree, verify

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def trees():
    return {owner: verify(ROOT, owner) for owner in ('parallel-planning', 'optimization')}


def context(tree, *, ready=False, **attributes):
    facts = {}
    if ready:
        for record in tree['records']:
            for route in record.get('routes', []):
                for key in route['required_evidence']:
                    facts[key] = {'state': True, 'kind': 'source_review', 'evidence_id': key,
                                  'ref': {'path': 'paper-only.txt', 'sha256': digest(b'paper fixture'),
                                          'locator': key}}
    return {'schema_version': 'aprof.evidence/v1', 'task_id': 'knowledge-v130-paper',
            'source_context_ref': {'path': 'C0.json', 'sha256': digest(b'paper context')},
            'attributes': attributes, 'facts': facts}


def test_new_planning_families_compose_without_losing_existing_routes(trees):
    tree = trees['parallel-planning']
    result = route_tree(tree, context(tree, ready=True, platform='dav-2201',
                        family=['indexing', 'moe-routing', 'sort-topk', 'layout']))
    matched = {entry['id'] for entry in result['matches']}
    assert {'planning.indexing.gather_output_owned', 'planning.indexing.indexed_write_reduce',
            'planning.moe-routing.route_sort_gather',
            'planning.moe-routing.finalize_weighted_reduce', 'planning.sort-topk.merge',
            'planning.layout.transpose'} <= matched
    assert all(entry['status'] == 'reference_ready' for entry in result['matches'])


def test_new_execution_branches_have_real_content_and_require_evidence(trees):
    tree = trees['optimization']
    features = ['cube-api', 'scalar-control', 'fusion-composition', 'pipeline-sync']
    result = route_tree(tree, context(tree, platform='dav-2201', features=features))
    prefixes = ('implementation.cube-api.', 'implementation.scalar-control.',
                'implementation.fusion-composition.')
    entries = [entry for entry in result['matches'] if entry['id'].startswith(prefixes)
               and not entry['id'].endswith('.fallback')]
    assert all(any(entry['id'].startswith(prefix) for entry in entries) for prefix in prefixes)
    assert all(entry['status'] == 'needs_evidence' and entry['missing'] for entry in entries)
    for entry in entries:
        assert entry['snapshot']['evidence_status'] == 'source_reviewed_not_benchmarked'
        assert 'body' in entry['snapshot'] and 'sources' in entry['snapshot']
    satisfied = route_tree(tree, context(tree, ready=True, platform='dav-2201', features=features))
    assert all(entry['status'] == 'reference_ready' for entry in satisfied['matches'])


def test_arch22_source_templates_are_not_promoted_to_950(trees):
    tree = trees['parallel-planning']
    result = route_tree(tree, context(tree, ready=True, platform='dav-3510',
                                     family=['indexing', 'moe-routing']))
    matched = {entry['id'] for entry in result['matches']}
    assert 'planning.indexing.gather_output_owned' not in matched
    assert 'planning.moe-routing.route_sort_gather' not in matched
    assert 'planning.moe-routing.finalize_weighted_reduce' not in matched
    assert any(entry['id'].endswith('.fallback') for entry in result['matches'])


def test_streamk_reference_needs_an_independent_target_implementation(trees):
    tree = trees['parallel-planning']
    ctx = context(tree, ready=True, platform='dav-2201', family=['matmul'],
                  features=['streamk_schedule'])
    del ctx['facts']['constraint.streamk_target_implementation']
    result = route_tree(tree, ctx)
    entry = next(entry for entry in result['matches'] if entry['id'] == 'planning.matmul.streamk')
    assert entry['status'] == 'needs_evidence'
    assert entry['missing'] == ['constraint.streamk_target_implementation']


def test_old_vector_entry_is_retained_while_the_branch_routes_to_separate_methods(trees):
    tree = trees['optimization']
    legacy = next(record for record in tree['records']
                  if record['id'] == 'implementation.vector-api.cast-control')
    assert legacy['status'] == 'deprecated'
    assert 'implementation.vector-api.cast' in legacy['references']
    result = route_tree(tree, context(tree, ready=True, platform='dav-2201', features=['vector-api']))
    matched = {entry['id'] for entry in result['matches']}
    assert {'implementation.vector-api.batch', 'implementation.vector-api.cast'} <= matched
    assert all(entry['status'] == 'reference_ready' for entry in result['matches'])


def test_arch22_optimization_paths_are_isolated_from_950(trees):
    tree = trees['optimization']
    result = route_tree(tree, context(tree, ready=True, platform='dav-3510',
                        features=['memory-transfer', 'buffer-lifetime', 'fusion-composition']))
    matched = {entry['id'] for entry in result['matches']}
    assert 'implementation.fusion-composition.cv_multistage_handoff' not in matched
    assert 'implementation.buffer-lifetime.arch22-bank-layout' not in matched
    assert 'implementation.memory-transfer.strided-pad' not in matched


def test_package_relocates_builds_and_hands_off_without_upstream_or_network(tmp_path):
    package = tmp_path / 'standalone'
    shutil.copytree(ROOT, package, ignore=shutil.ignore_patterns(
        '__pycache__', '.pytest_cache', '.runtime-env', '*.egg-info'))
    # 审计钩子在新进程中拒绝原包、来源 checkout 和网络；不是只搜索路径字符串。
    script = r'''
import json, os, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
blocked = [Path(value).resolve() for value in sys.argv[2:]]
def isolate(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        raise RuntimeError('standalone fixture forbids network')
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        if any(path.is_relative_to(parent) for parent in blocked):
            raise RuntimeError('standalone fixture forbids original/source paths: ' + str(path))
sys.addaudithook(isolate)
from aprof_runtime.knowledge import build, verify, digest, route_tree, route_diagnosis, link_result
from aprof_runtime.jsonio import content_hash
owners = ('parallel-planning', 'optimization')
trees = {owner: build(root, owner) for owner in owners}
assert all(verify(root, owner) == trees[owner] for owner in owners)
from aprof_runtime.graph import load_snapshot
from aprof_runtime.diagnosis import verify as verify_diagnosis
assert verify_diagnosis(root)['graph_version'] == 'v0004'
graph = load_snapshot(root / 'skills/ascendc-aprof-diagnosis/graph/versions/v0003')[0]
facts = {}
for artifact in [graph, *trees.values()]:
    for record in artifact['records']:
        for key in [p['fact'] for p in record.get('preconditions', [])] + [
                key for route in record.get('routes', []) for key in route['required_evidence']]:
            facts[key] = dict(state=True, kind='source_review', evidence_id=key,
                ref=dict(path='paper.txt', sha256=digest(b'paper fixture'), locator=key))
ctx = dict(schema_version='aprof.evidence/v1', task_id='standalone-paper',
    source_context_ref=dict(path='C0.json', sha256=digest(b'paper context')),
    attributes=dict(platform='dav-2201', family=['under-fusion'],
        features=['fusion-composition', 'pipeline-sync', 'vector-api']), facts=facts)
c1 = dict(schema_version='aprof.handoff/v2', stage='C1', task_id=ctx['task_id'],
    candidate_id=None, parent_hash=None, route=route_diagnosis(graph, ctx), artifacts=[])
action = 'action.fuse_kernel_chain'
assert any(a['id'] == action and a['status'] == 'executable' for a in c1['route']['actions'])
c2 = dict(schema_version='aprof.handoff/v2', stage='C2', task_id=ctx['task_id'],
    candidate_id=None, parent_hash=content_hash(c1), route=route_tree(trees['parallel-planning'], ctx),
    selected_actions=[action], selected_entries=['planning.under-fusion.chain'],
    parameters=dict(capacity_bytes=65536, tile_elements=1024, dtype='float32',
        algorithm='y=(x*scale)+bias; preserve declared arithmetic and rounding order',
        ownership='each owner writes a disjoint contiguous output tile',
        fusion_boundary=['scale', 'bias'], exchange_path='owner-local UB',
        resource_budget=dict(input_bytes=4096, temporary_bytes=4096, output_bytes=4096,
                             api_scratch_bytes=0, resident_parameter_bytes=8)),
    alternatives=[dict(name='separate kernels', reason='paper comparison only')],
    implementation_freedom=['local buffer allocation and event choices within the declared budget'], artifacts=[])
# C3 获得序列化的 C2 快照及明确的计划参数，无需回到 planning 目录找正文。
c2 = json.loads(json.dumps(c2))
plan = next(m['snapshot'] for m in c2['route']['matches'] if m['id'] in c2['selected_entries'])
assert plan['body'] and plan['sources'] and c2['parameters']['exchange_path'] == 'owner-local UB'
route = route_tree(trees['optimization'], ctx)
chosen = 'implementation.fusion-composition.vector_chain_residency'
assert next(m for m in route['matches'] if m['id'] == chosen)['status'] == 'reference_ready'
c3 = dict(schema_version='aprof.handoff/v2', stage='C3', task_id=ctx['task_id'],
    candidate_id='paper-candidate', parent_hash=content_hash(c2), route=route,
    executed_actions=[action], selected_entries=[chosen], parameters={}, parameter_adjustments=[],
    implementation_source_hash=digest(b'paper source'), plan_compliance='compliant', artifacts=[])
timing = dict(path='not-measured.json', sha256=digest(b'paper reference'),
              candidate_id='paper-candidate', protocol='single_role_l2_clean_task_v1')
outcome = link_result(c1, c2, c3, timing)
assert not outcome['causal_claim'] and not outcome['legacy_episode_eligible']
import importlib.util
spec = importlib.util.spec_from_file_location('standalone_release', root / 'tools/release.py')
release_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_tool)
release = release_tool.verify_unsealed(root)
assert release['release_id'] == 'graph-base/1.3.0' and not release['publication_accepted']
print(json.dumps(dict(standalone=True, network='blocked', upstream='blocked',
    planning_version=trees['parallel-planning']['version'],
    optimization_version=trees['optimization']['version'], selected_execution=chosen)))
'''
    environment = dict(os.environ, PYTHONPATH=str(package / 'runtime/src'),
                       APROF_SKILL_LIB=str(package), PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([sys.executable, '-B', '-c', script, str(package),
                             str(next((p for p in ROOT.parents if (p / '.git').exists()), ROOT)),
                             '/tmp/aprof-knowledge-sources-1SHAlx',
                             '/tmp/aprof-knowledge-130-lbpokgm7',
                             *([environment['APROF_TEST_SOURCE_REPO']]
                               if environment.get('APROF_TEST_SOURCE_REPO') else [])],
                            cwd=package, env=environment, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    checked = json.loads(result.stdout)
    assert checked['standalone'] and checked['upstream'] == checked['network'] == 'blocked'
    assert checked['planning_version'] == 'v0002'
    assert checked['optimization_version'] == 'v0004'
