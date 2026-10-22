"""历史单实例 v3 的结果关联；新方案由 v4 模块处理，旧生成器保持原字节。"""
from copy import deepcopy
from pathlib import Path

from . import bindings
from .errors import GraphError
from .jsonio import content_hash, file_hash
from .knowledge import validate_schema


def link_result_v3(root, c1, c2, c3, timing, *, task_root, timing_ref):
    root, task_root = Path(root), Path(task_root)
    if {item.get('schema_version') for item in (c1, c2, c3)} != {'aprof.handoff/v3'}:
        raise GraphError('结果关联不能混装交接版本')
    for item in (c1, c2, c3):
        validate_schema(root, 'knowledge-handoff-v3', item)
    config_hash = c2['selection']['routing_config_hash']
    name = f'{bindings.ROUTING_SNAPSHOTS}/{config_hash.removeprefix("sha256:")}.json'
    if not (root / name).is_file():
        raise GraphError('历史 v3 路由快照缺失')
    artifacts, config = bindings.load_frozen_bundle(root, {'path': name, 'sha256': file_hash(root / name)})
    validation = bindings.validate_chain(root, c1, c2, c3, task_root=task_root,
                                         artifacts=artifacts, routing_config=config)
    if validation['status'] != 'implemented':
        raise GraphError('NOOP 不能关联为新候选的计时结果')
    if (set(timing) != {'path', 'sha256', 'candidate_id', 'protocol'} or
            timing['candidate_id'] != c3['candidate_id'] or
            timing['protocol'] != 'single_role_l2_clean_task_v1'):
        raise GraphError('计时引用与实际候选或协议不符')
    result_path = Path(timing['path'])
    if not result_path.is_absolute():
        result_path = Path(timing_ref).resolve().parent / result_path
    if not result_path.is_file() or file_hash(result_path) != timing['sha256']:
        raise GraphError('计时结果引用 hash 不符')
    measured = bindings._json_file(result_path)
    validate_schema(root, 'unified-timing-result', measured)
    if measured['decision_hash'] != content_hash({key: value for key, value in measured.items() if key != 'decision_hash'}):
        raise GraphError('计时结果 decision_hash 不符')
    if (measured.get('kind') != 'unified_timing_result' or
            measured.get('candidate_id') != timing['candidate_id'] or
            measured.get('protocol') != timing['protocol']):
        raise GraphError('计时结果与候选或协议不符')
    ref = measured.get('request')
    if not isinstance(ref, dict) or set(ref) != {'path', 'sha256'}:
        raise GraphError('计时结果缺少原请求引用')
    request_path = Path(ref['path'])
    if not request_path.is_absolute():
        request_path = result_path.parent / request_path
    if not request_path.is_file() or file_hash(request_path) != ref['sha256']:
        raise GraphError('计时请求引用 hash 不符')
    request = bindings._json_file(request_path)
    validate_schema(root, 'unified-timing-request', request)
    if (request['operator'] != measured['operator'] or
            request['operator'] != c2['selection']['confirmed_plan']['parallel_plan']['operator']):
        raise GraphError('计时请求、结果与确认计划的算子不同')
    if (request.get('candidate_id') != c3['candidate_id'] or
            request.get('protocol') != timing['protocol'] or
            request.get('candidate_source_sha256') != c3['execution']['implementation_source_ref']['sha256'] or
            request.get('baseline_source_sha256') != c1['reasoning']['current']['implementation_ref']['sha256']):
        raise GraphError('计时请求与 C3 源码或父本不同')
    instance = c2['selection']['instance']
    return {'schema_version': 'aprof.knowledge-outcome/v2', 'task_id': c1['task_id'],
            'candidate_id': c3['candidate_id'],
            'handoff_hashes': [content_hash(item) for item in (c1, c2, c3)],
            'recommended_actions': sorted({i['action_id'] for i in c1['reasoning']['action_instances']}),
            'selected_actions': [instance['action_id']],
            'executed_actions': [instance['action_id']] if c3['execution']['executed_instances'] else [],
            'selected_instances': [instance['instance_id']],
            'executed_instances': deepcopy(c3['execution']['executed_instances']),
            'actual_combination': validation['actual_combination'], 'timing_result': deepcopy(timing),
            'causal_claim': False, 'legacy_episode_eligible': False}
