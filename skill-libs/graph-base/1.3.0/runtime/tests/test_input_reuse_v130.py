"""输入驻留的文档路由门禁；CPU only，不表示 Action/C3 已实施或有性能收益。"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from aprof_runtime import bindings
from aprof_runtime.jsonio import content_hash, file_hash
from aprof_runtime.knowledge import route_tree

ROOT = Path(__file__).resolve().parents[2]
MAIN = 'implementation.memory-transfer.input-tile-residency'
ACTION = 'action.reuse_input_tiles'
# 明确的单个纸面工作负载，不从 router.required_evidence 自动填 true。
REVIEW = {
    'constraint.same_input_region': '两消费者都读同 owner 的 x[base:base+n]、FP32、stride=1、同一有效 n。',
    'constraint.input_value_preserved': '消费者1 Mul 写独立 yUb；xUb 无 alias/写入，消费者2 Adds 完成前保持原值。',
    'constraint.semantic_equivalence': '复用同一原始 x；两消费者的顺序、数值 API、舍入和有效输出不变。',
    'constraint.capacity': '假设 UB256KiB；4块独立64KiB缓冲、slot=1、scratch=0；删重复输入后3块192KiB。',
    'constraint.reuse_domain': '每 owner 独占连续输出，两个消费者同 owner、同 tile，无核间共享。',
    'constraint.dependency_lifetime': 'MTE2完成后读取；最后Vector输入消费者完成后方覆盖；MTE3完成前不重用输出。',
    'constraint.output_ownership': '每个有效输出仍由原 owner 写一次，无 workspace/归并改变。',
    'constraint.plan_freedom': '已确认纸面计划允许 local_transfer 和 buffer_lifetime，所有权/通路/同步拓扑固定。',
}


@pytest.fixture(scope='module')
def bundle():
    config = json.loads((ROOT / bindings.CONFIG).read_text())
    ref = bindings.routing_snapshot_ref(ROOT, config)
    return bindings.load_frozen_bundle(ROOT, ref)


def paper_context(tmp_path, **changes):
    review = {'synthetic_only': True, 'explanations': REVIEW,
              'states': {key: True for key in REVIEW}}
    review['states'].update(changes)
    path = tmp_path / 'paper-input.json'
    path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
    ref = {'path': path.name, 'sha256': file_hash(path)}
    return {'schema_version': 'aprof.evidence/v1', 'task_id': 'input-reuse-paper',
            'source_context_ref': ref,
            'attributes': {'platform': 'dav-2201', 'family': ['elementwise'],
                           'dtype': 'float32', 'features': ['memory-transfer']},
            'facts': {key: {'state': value, 'kind': 'source_review', 'evidence_id': key,
                            'ref': {**ref, 'locator': 'states.' + key}}
                      for key, value in review['states'].items()}}


def action_trace(bundle, context):
    artifacts, config = bundle
    row = next(row for row in config['actions'] if row['action_id'] == ACTION)
    return bindings.route_candidates(artifacts['optimization'], context,
                                     row['optimization_subtrees'])


def test_input_residency_is_a_primary_candidate_with_explicit_method_evidence(bundle, tmp_path):
    trace = action_trace(bundle, paper_context(tmp_path))
    match = next(item for item in trace['matches'] if item['id'] == MAIN)
    assert match['status'] == 'reference_ready'
    assert match['missing'] == []
    # A real knowledge body and source snapshot, not a route-only label/link.
    assert match['snapshot']['sources'] and match['snapshot']['body']
    assert MAIN not in bundle[1]['support_entries']
    action = next(r for r in bundle[0]['diagnosis']['records'] if r['id'] == ACTION)
    assert {(p['fact'], p['state']) for p in action['preconditions']} == {
        ('symptom.source.insufficient_input_reuse', True),
        ('constraint.reuse_domain', True), ('constraint.semantic_equivalence', True),
        ('constraint.capacity', True)}


@pytest.mark.parametrize('key', tuple(REVIEW))
@pytest.mark.parametrize('state', [False, 'unknown'])
def test_a_counterexample_or_unknown_cannot_become_a_ready_recipe(bundle, tmp_path, key, state):
    trace = action_trace(bundle, paper_context(tmp_path, **{key: state}))
    match = next(item for item in trace['matches'] if item['id'] == MAIN)
    assert match['status'] == 'needs_evidence'
    assert key in match['missing']
    # Legacy route_tree uses needs_evidence for both false and unknown. It does
    # not declare the mechanism false or authorize C3; keep that contract.


@pytest.mark.parametrize('attribute,value', [('platform', 'dav-3510'),
                                            ('features', ['buffer-lifetime'])])
def test_registered_action_hint_does_not_inject_platform_or_domain(bundle, tmp_path, attribute, value):
    ctx = paper_context(tmp_path)
    ctx['attributes'][attribute] = value
    trace = action_trace(bundle, ctx)
    assert MAIN not in {item['id'] for item in trace['matches']}


def test_current_action_range_and_old_frozen_bundle_keep_distinct_versions(bundle):
    artifacts, config = bundle
    assert artifacts['optimization']['version'] == 'v0007'
    row = next(row for row in config['actions'] if row['action_id'] == ACTION)
    assert MAIN in row['optimization_subtrees']
    # Locate the package-owned old routing archive by its declared versions.
    # No /tmp, external source tree, test-output directory or current REGION.
    old = next(json.loads(p.read_text())
               for p in (ROOT / bindings.ROUTING_SNAPSHOTS).glob('*.json')
               if json.loads(p.read_text())['bases']['diagnosis']['version'] == 'v0004'
               and json.loads(p.read_text())['bases']['optimization']['version'] == 'v0002')
    old_ref = bindings.routing_snapshot_ref(ROOT, old)
    old_artifacts, old_config = bindings.load_frozen_bundle(ROOT, old_ref)
    assert old_artifacts['optimization']['version'] == 'v0002'
    assert old_artifacts['parallel-planning']['version'] == 'v0002'
    assert MAIN not in {r['id'] for r in old_artifacts['optimization']['records']}
    assert content_hash(old_config) != content_hash(config)
    assert old_artifacts['diagnosis']['version'] == 'v0004'
    assert artifacts['diagnosis']['version'] == 'v0007'
    assert artifacts['parallel-planning']['version'] == 'v0004'
    # 本轮D/P也新增后继；历史bundle仍指向自己的原内容，不能要求其等于当前知识。
    assert content_hash(old_artifacts['diagnosis']) != content_hash(artifacts['diagnosis'])
    assert content_hash(old_artifacts['parallel-planning']) != content_hash(artifacts['parallel-planning'])
