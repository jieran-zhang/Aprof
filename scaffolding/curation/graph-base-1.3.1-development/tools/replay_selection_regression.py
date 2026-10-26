#!/usr/bin/env python3
"""离线核验保存的自主选择、实际知识展开与内部咨询；不重新生成判断或运行算子。"""
import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[4] / 'skill-libs/graph-base/1.3.1')
    parser.add_argument('--case', action='append')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path.insert(0, str(root / 'runtime/src'))
    from aprof_runtime import action_decision, bindings, diagnosis
    from aprof_runtime.diagnosis_retrieval import validate_expansion
    from aprof_runtime.jsonio import content_hash, file_hash
    from aprof_runtime.knowledge import local, route_tree, validate_schema

    def read(path):
        return json.loads(path.read_text())

    def checked(base, ref):
        path = local(base, ref['path'])
        if not path.is_file() or file_hash(path) != ref['sha256']:
            raise ValueError(f'回放引用身份不符: {ref["path"]}')
        return path

    base = Path(__file__).resolve().parents[1] / 'selection-regression-15'
    inventory = read(base / 'inventory.json')
    selected = set(args.case or [r['case'] for r in inventory['tasks']])
    if selected - {r['case'] for r in inventory['tasks']}:
        raise ValueError('不存在的任务')
    results, bundles = [], {}
    for task in inventory['tasks']:
        if task['case'] not in selected:
            continue
        task_root = local(base, task['path'])
        for ref in task['files']:
            checked(task_root, ref)
        rows = []
        for entry in task['rounds']:
            decision = read(checked(task_root, entry['decision_ref']))
            reasoning = read(checked(task_root, decision['reasoning_ref']))
            key = decision['routing_ref']['sha256']
            if key not in bundles:
                bundles[key] = bindings.load_frozen_bundle(root, decision['routing_ref'])
            artifacts, config = bundles[key]
            graph = artifacts['diagnosis']
            validation = action_decision.validate_decision(root, decision, task_root=task_root)
            if diagnosis.retrieve(graph, reasoning['context_snapshot'], root) != read(checked(task_root, entry['retrieval_ref'])):
                raise ValueError('目录/邻接检索与保存结果不同')
            expansion = read(checked(task_root, entry['expansion_ref']))
            validate_expansion(graph, reasoning['context_snapshot'], expansion, root)
            if entry.get('c1_ref'):
                c1 = read(checked(task_root, entry['c1_ref']))
                validate_schema(root, 'knowledge-handoff-v3', c1)
                if (c1['reasoning'] != reasoning or c1['task_id'] != decision['task_id']
                        or c1['stage'] != 'C1' or c1['candidate_id'] is not None
                        or c1['parent_hash'] != decision['current_parent_ref']['sha256']):
                    raise ValueError('C1未绑定实际推理、任务或父本')
                decisions = []
                for ref in c1['artifacts']:
                    path = checked(task_root, ref)
                    value = read(path) if path.suffix == '.json' else None
                    if isinstance(value, dict) and value.get('schema_version') == 'aprof.action-decision/v2':
                        decisions.append(ref)
                if decisions != [entry['decision_ref']]:
                    raise ValueError('C1必须唯一引用本轮实际decision')
            consultation = {'parallel-planning': [], 'optimization': []}
            for receipt in entry['consultations']:
                owner = receipt['owner']
                trace = read(checked(task_root, receipt['route_ref']))
                if receipt['kind'] == 'action':
                    inst = next(i for i in reasoning['action_instances'] if i['instance_id'] == receipt['instance_id'])
                    rule = next(r for r in config['actions'] if r['action_id'] == inst['action_id'])
                    context = bindings.routing_context(root, reasoning, inst, task_root=task_root, artifact=graph)
                    field = 'planning_subtrees' if owner == 'parallel-planning' else 'optimization_subtrees'
                    expected = bindings.route_candidates(artifacts[owner], context, rule[field])
                elif receipt['kind'] == 'full_tree':
                    expected = route_tree(artifacts[owner], trace['context_snapshot'])
                else:
                    raise ValueError('未知咨询类型')
                if trace['override_hash'] is not None or trace != expected:
                    raise ValueError('保存的内部router咨询不能重放')
                if trace['task_id'] != decision['task_id'] or trace['context_snapshot']['attributes'] != reasoning['context_snapshot']['attributes']:
                    raise ValueError('咨询的任务或事实属性不匹配')
                consultation[owner].extend(m['id'] for m in trace['matches'])
            consultation = {owner: sorted(set(ids)) for owner, ids in consultation.items()}
            selected_id = decision['selection']['action_instance_id']
            instance = next((i for i in reasoning['action_instances'] if i['instance_id'] == selected_id), None)
            action_routes = {}
            if instance is not None:
                rule = next(r for r in config['actions'] if r['action_id'] == instance['action_id'])
                context = bindings.routing_context(root, reasoning, instance, task_root=task_root, artifact=graph)
                for owner, field in [('parallel-planning', 'planning_subtrees'), ('optimization', 'optimization_subtrees')]:
                    trace = bindings.route_candidates(artifacts[owner], context, rule[field])
                    action_routes[owner] = [m['id'] for m in trace['matches']]
            rows.append({'round':decision['round'], 'validation':validation,
                         'expanded_problems':[r['problem_id'] for r in expansion['entries']],
                         'action':instance['action_id'] if instance else None,
                         'selection_mode':decision['selection']['mode'],
                         'knowledge_documents':[u['document_ref'] for u in decision['knowledge_use']],
                         'consultation':consultation, 'action_route_candidates':action_routes,
                         'formal_C2_C3_selection':False, 'hardware':False})
        results.append({'case':task['case'], 'operator':task['operator'], 'rounds':rows})
    result = {'valid':True, 'schema':'aprof.selection-regression-replay/v1', 'tasks':results,
              'limit':'保存记录和实际router回放；不是重新执行Agent判断、硬件验证或性能证明。'}
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'valid':True,'tasks':len(results),'rounds':sum(len(t['rounds']) for t in results)},ensure_ascii=False))


if __name__ == '__main__':
    main()
