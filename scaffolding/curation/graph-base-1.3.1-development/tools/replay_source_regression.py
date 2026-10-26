#!/usr/bin/env python3
"""重放已保存的源码回归身份、推理与路由；不重新生成 Agent 判断或运行算子。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[4] / 'skill-libs/graph-base/1.3.1')
    parser.add_argument('--case', action='append', help='例如 case-01；省略时检查全部任务')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path.insert(0, str(root / 'runtime/src'))
    from aprof_runtime import action_decision, bindings, diagnosis
    from aprof_runtime.diagnosis_retrieval import validate_expansion
    from aprof_runtime.jsonio import content_hash, file_hash
    from aprof_runtime.knowledge import local, validate_schema

    def read(path):
        return json.loads(path.read_text())

    def checked(base, ref):
        path = local(base, ref['path'])
        if file_hash(path) != ref['sha256']:
            raise ValueError(f'任务引用 hash 不符: {path}')
        return path

    base = Path(__file__).resolve().parents[1] / 'source-regression-15'
    inventory = read(base / 'inventory.json')
    graph = None
    results = []
    bundles = {}
    selected = set(args.case or [r['case'] for r in inventory['tasks']])
    if selected - {r['case'] for r in inventory['tasks']}:
        raise ValueError('不存在的任务目录')
    for task in inventory['tasks']:
        if task['case'] not in selected:
            continue
        task_root = local(base, task['path'])
        for ref in task['files']:
            checked(task_root, ref)
        rounds = []
        for entry in task['rounds']:
            decision = read(checked(task_root, entry['decision_ref']))
            reasoning = read(checked(task_root, decision['reasoning_ref']))
            bundle_id = decision['routing_ref']['sha256']
            if bundle_id not in bundles:
                bundles[bundle_id] = bindings.load_frozen_bundle(root, decision['routing_ref'])
            artifacts, config = bundles[bundle_id]
            graph = artifacts['diagnosis']
            validation = action_decision.validate_decision(root, decision, task_root=task_root)
            c1 = read(checked(task_root, entry['c1_ref']))
            validate_schema(root, 'knowledge-handoff-v3', c1)
            if c1['reasoning'] != reasoning:
                raise ValueError('C1 与 decision 的 reasoning 不一致')
            for ref in c1['artifacts']:
                checked(task_root, ref)
            if not any(ref['sha256'] == entry['decision_ref']['sha256'] for ref in c1['artifacts']):
                raise ValueError('C1 未绑定实际决策记录')
            retrieval = diagnosis.retrieve(graph, reasoning['context_snapshot'], root)
            if retrieval != read(checked(task_root, entry['retrieval_ref'])):
                raise ValueError('检索回放与保存的目录/邻接结果不同')
            expansion = read(checked(task_root, entry['expansion_ref']))
            validate_expansion(graph, reasoning['context_snapshot'], expansion, root)
            instance_id = decision['selection']['action_instance_id']
            instance = next(i for i in reasoning['action_instances'] if i['instance_id'] == instance_id)
            bundle_id = decision['routing_ref']['sha256']
            if bundle_id not in bundles:
                bundles[bundle_id] = bindings.load_frozen_bundle(root, decision['routing_ref'])
            artifacts, config = bundles[bundle_id]
            row = next(r for r in config['actions'] if r['action_id'] == instance['action_id'])
            hint = {'parallel-planning': row['planning_subtrees'], 'optimization': row['optimization_subtrees']}
            context = bindings.routing_context(root, reasoning, instance, task_root=task_root, artifact=graph)
            p_route = bindings.route_candidates(artifacts['parallel-planning'], context, hint['parallel-planning'])
            # 没有 confirmed_plan，O 只做相同实例范围内的真实内部咨询。
            o_route = bindings.route_candidates(artifacts['optimization'], context, hint['optimization'])
            rounds.append({'round': decision['round'], 'validation': validation,
                           'decision_ref': entry['decision_ref'], 'problem_directory_size': len(retrieval['problem_directory']),
                           'expanded_problem_ids': [r['problem_id'] for r in expansion['entries']],
                           'action': instance['action_id'], 'P_candidate_ids': [r['id'] for r in p_route['matches']],
                           'O_consultation_ids': [r['id'] for r in o_route['matches']],
                           'formal_C2_C3_selection': False, 'performance_claim': False})
        results.append({'case': task['case'], 'operator': task['operator'], 'file_count': len(task['files']), 'rounds': rounds})
    result = {'schema': 'aprof.source-regression-replay/v1', 'valid': True, 'knowledge_hash': content_hash(graph),
              'tasks': results, 'limit': '仅回放保存记录、来源身份与内部路由，不重演Agent推理，不运行编译器/算子/硬件，不验证收益。'}
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'valid': True, 'tasks': len(results), 'rounds': sum(len(r['rounds']) for r in results)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
