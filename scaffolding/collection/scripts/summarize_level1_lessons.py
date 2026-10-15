#!/usr/bin/env python3
"""Render Chinese lessons from completed Level1 records; never gate or select sources."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN = ROOT / '.aprof/runs/level1-20260907T152600Z'
GAIN_VERDICTS = {'production_safe_gain', 'benchmark_specialized_gain'}
VERDICTS = {
    'production_safe_gain': '生产范围收益通过', 'benchmark_specialized_gain': '仅基准范围收益通过',
    'baseline_retained': '保留基线', 'build_failed': '构建失败', 'accuracy_failed': '正确性失败',
    'runtime_failed': '运行失败', 'measurement_unstable': '测量不稳定',
    'attribution_uncertain': '归因未确定', 'heldout_regression': '留出 case 回归',
    'stable_no_gain': '稳定但无合格收益', 'artifacts_incomplete': '证据不完整',
    'static_rejected': '静态检查拒绝', 'inconclusive': '结论不足',
}
# These labels describe frozen interventions, not measured bottlenecks or outcomes.
HANDLERS = {
    'exp.attribute_identity_dispatch': ('恒等仿射指令开销', '核内一次分派，省略乘一/加零', '运行时 multiplier=1 或 shift=0；不跳过乘零'),
    'exp.localize_tiling_and_split_tail': ('重复 tiling 读取与尾分支', '缓存不变量并分离整 tile/尾 tile', '算子已向量化；不改变 tile 大小和数学次序'),
    'exp.double_buffer_prolog_steady_drain': ('相邻 tile 的搬运/计算等待', '双输入/输出槽与预取、稳态、收尾', '每核至少两个 tile，所有存活缓冲区适配 UB'),
    'exp.capacity_adaptive_transfer_tiles': ('小 tile 的搬运与标量设置开销', '按运行时 UB 和 dtype 扩大连续 tile', '保留有效 count；UB、对齐和 API repeat 上限共同约束'),
    'exp.align_core_dma_boundaries': ('核间起始地址未对齐', '将每核连续区间按 32 字节对齐', '保持动态核数；末核长度变化需单独观察'),
    'exp.zero_affine_exp_identity': ('零仿射输入上的 Exp 开销', '保留 x×0，后接加一代替 Exp', '仅 multiplier=0 且 shift=0；NaN/Inf 仍须经过乘零'),
    'foreach_norm.minimum_tile_budget_dynamic_split': ('独立 partial 归约并行度不足', '按最小 tile 工作量与实际核数分配任务', '任务量和运行时核数共同限制；不能把小工作量低利用率视为瓶颈'),
    'foreach_norm.algebraic_common_orders': ('简单阶数使用通用 Power', 'p=1/2/4 使用恒等、乘法和开方', '其他 p 保留通用路径；不得外推到 p=2.5'),
    'foreach_norm.vector_resident_sequential_accumulator': ('逐 tile 标量累加反馈', 'FP32 顺序累加状态驻留 UB', 'GENERAL/ZERO 路径；维持累加顺序与 INF 路径'),
    'masked_scale_prefetch_double_buffer': ('tile 搬运与计算等待', '双槽队列预取并延迟输出', '多个独立 tile，原始队列和计算临时量全部计入容量'),
    'masked_scale_elide_fp32_materialization': ('FP32 队列的恒等物化拷贝', '直接引用 FP32 队列 tensor', '只适用于 FP32 输入分支；队列生命周期必须覆盖消费'),
    'masked_scale_dtype_aware_ub_tiling': ('逐 tile copy/queue 设置开销', '用完整 dtype 足迹约束更大 tile', '按实际 x/mask dtype 计算所有缓冲区；保留尾部语义'),
    'foreach_addcdiv_scalar.align_core_copy32': ('核间连续区间和搬运未对齐', '32 字节对齐主搬运，尾部保留 DataCopyPad', '每个元素恰好分配一次；不让 padding 进入数学'),
    'foreach_addcdiv_scalar.prefetch_fifo_double_buffer': ('相邻 tile 等待', '一 tile 前瞻与原始队列双缓冲', '输入/输出所有槽及 scratch 适配 UB，维持 FIFO 所有权'),
    'foreach_addcdiv_scalar.ub_bounded_contiguous_batch': ('连续 tile 设置开销', '按 dtype 和 UB 批处理更多元素', '完整存活量、有效 count 和动态 shape 均受约束'),
    'mish.reuse_negative_tail_exponential': ('负尾部重复求指数', '复用稳定 softplus 已有指数结果', '仅已有负尾修正路径；不能改变数值稳定分支'),
    'mish.prefetch_double_buffer': ('tile 搬运与计算等待', '双槽队列加一 tile 预取', '至少两个 tile 且缓冲区生命周期不重叠覆盖'),
    'mish.direct_fp32_input': ('FP32 输入的加零暂存', '直接消费 FP32 输入队列 tensor', '输入引用在消费完成前保持有效；其他 dtype 保持转换'),
    'sigmoid.align_block_ownership': ('每核 GM 起点未对齐', '按 32 字节对齐核内所有权', '动态核数不变；末核分配偏差与尾部需验证'),
    'sigmoid.double_buffer_prefetch': ('相邻 tile 搬运等待', '前瞻预取与延迟写回', '独立 tile、双槽容量和最终 drain 完整'),
    'sigmoid.coalesce_dma_chunks': ('DMA 与队列设置频繁', '合并相邻 DMA 块，保留原计算块', '两块连续且不跨依赖边界；计算 scratch 仍有界'),
    'gelu_prefetch_double_buffer': ('tile 搬运与计算等待', '输入前瞻、双 DMA 槽和最终 drain', '保留单份 VECCALC scratch；至少两个 tile'),
    'gelu_capacity_batched_tiles': ('固定小 tile 设置开销', '按 dtype 足迹和 UB 扩大 tile', '64 元素对齐且包含 mask 分配成本'),
    'gelu_hoist_launch_invariants': ('重复 tiling 读取和模式分派', '初始化缓存，核内一次模板模式分派', '所有模式与 dtype 分支保留；不改数值公式'),
}


def read(path):
    def reject(value):
        raise ValueError(f'nonfinite JSON constant in {path}: {value}')
    return json.loads(Path(path).read_text(), parse_constant=reject)


def rows(path):
    def reject(value):
        raise ValueError(f'nonfinite JSON constant in {path}: {value}')
    return [json.loads(line, parse_constant=reject) for line in Path(path).read_text().splitlines() if line.strip()]


def esc(value):
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    return value.replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')


def link(label, path):
    path = Path(path).resolve()
    return f'[{esc(label)}](<{path}>)'


def number(value, reason='没有对应数值'):
    if value is None:
        return '未知：' + esc(reason)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('expected a finite numeric measurement or an explicit null')
    return format(value, '.9g')


def percent(value, reason='未采集'):
    return number(value * 100) + '%' if value is not None else number(None, reason)


def null_reason(trace, field, fallback):
    return trace.get('null_reasons', {}).get(field, fallback)


def cas_path(run, split, digest):
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest or ''):
        raise ValueError('invalid finalized artifact hash')
    hex_digest = digest.split(':', 1)[1]
    return run / split / 'episodes.sqlite.objects/sha256' / hex_digest[:2] / hex_digest[2:]


def hash_link(run, split, digest, label, reason='最终记录未提供哈希'):
    if digest is None:
        return f'{label}：未知（{esc(reason)}）'
    path = cas_path(run, split, digest)
    if not path.is_file():
        raise ValueError(f'finalized artifact is missing: {digest} ({path})')
    if 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError(f'finalized artifact bytes differ from their hash: {path}')
    return link(f'{label} {digest}', path)


def observed(report):
    """Descriptive equal-case ratios only; never infer machine eligibility."""
    if report is None:
        return {'text': '未采集', 'details': [], 'case_count': 0}
    cases = report.get('per_case', [])
    valid = [c for c in cases if c.get('speedup') is not None]
    for case in valid:
        number(case['speedup'])
        if case['speedup'] <= 0:
            raise ValueError('nonpositive per-case speedup')
    if not valid:
        reason = '；'.join(report.get('reasons', [])) or '没有有效配对样本'
        return {'text': '未知：' + esc(reason), 'details': [], 'case_count': 0}
    gain = math.exp(sum(math.log(c['speedup']) for c in valid) / len(valid))
    low = min(valid, key=lambda c: (c['speedup'], c['case_id']))
    high = max(valid, key=lambda c: (c['speedup'], -c['case_id']))
    cva = max((c['baseline_cv'] for c in valid if c.get('baseline_cv') is not None), default=None)
    cvb = max((c['candidate_cv'] for c in valid if c.get('candidate_cv') is not None), default=None)
    pairs = [c['pair_count'] for c in valid if c.get('pair_count') is not None]
    regression = [c for c in valid if c.get('regression') is not None]
    worst = max(regression, key=lambda c: c['regression']) if regression else None
    slow = [c for c in regression if c['regression'] > 0]
    over = [c for c in regression if c['regression'] > .03]
    text = f"观测几何比 {number(gain)}×（{len(valid)}/{len(cases)} case）"
    text += '；测量稳定' if report.get('stable') is True else '；测量不稳定/不完整，禁止作为合格收益'
    detail = (f"case {low['case_id']} 最低 {number(low['speedup'])}×，case {high['case_id']} 最高 {number(high['speedup'])}×；"
        f"最大 CV 基线/候选 {percent(cva)}/{percent(cvb)}；")
    detail += f"配对数 {min(pairs)}–{max(pairs)}" if pairs else '配对数未知'
    detail += f"；最差有符号回归 case {worst['case_id']}={percent(worst['regression'])}" if worst else '；回归未知：没有有效配对 case'
    detail += f"；变慢 {len(slow)} 个，超过 3% 共 {len(over)} 个"
    if slow:
        detail += '：' + '，'.join(f"case {c['case_id']} {percent(c['regression'])}" for c in slow)
    return {'text': text, 'details': [detail], 'case_count': len(valid)}


def load_campaign(run, expected_attempts=24, expected_operators=7):
    run = Path(run).resolve()
    manifest = read(run / 'run-manifest.json')
    operators = manifest['operators']
    if len(operators) != expected_operators or len(set(operators)) != len(operators):
        raise ValueError(f'expected exactly {expected_operators} unique operators')
    tasks = []
    all_ids = set()
    for op in operators:
        task = run / 'tasks' / op
        final = read(task / 'finalization_report.json')
        if final.get('status') != 'completed':
            raise ValueError(f'{op}: finalization has not completed')
        traces = rows(task / 'optimization_traces.jsonl')
        roster = read(task / 'frozen-roster.json')
        expected = {c['candidate_id'] for c in roster['candidates']}
        if len(expected) != len(roster['candidates']) or not expected:
            raise ValueError(f'{op}: frozen roster is empty or contains duplicates')
        actual = [t['identity']['candidate_id'] for t in traces]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise ValueError(f'{op}: finalized traces do not cover the exact frozen roster')
        if all_ids.intersection(actual):
            raise ValueError('duplicate candidate identities across operators')
        all_ids.update(actual)
        final_rows = {item['candidate_id']: item for item in final['attempts']}
        if (set(final_rows) != expected or len(final_rows) != len(final['attempts'])
                or final.get('attempt_count') != len(expected)):
            raise ValueError(f'{op}: finalization attempt count differs from roster')
        split = 'validation' if op in manifest['validation_operators'] else 'train'
        selection = read(task / 'best_source_selection.json')
        if selection != final['best_source']:
            raise ValueError(f'{op}: selection differs from finalized machine selection')
        attempts = []
        for trace in sorted(traces, key=lambda t: t['identity']['candidate_id']):
            identity = trace['identity']
            cid = identity['candidate_id']
            if identity['operator'] != op or identity['split'] != split or identity['run_id'] != run.name:
                raise ValueError(f'{cid}: operator, split or run identity changed')
            for key in ('verdict', 'first_failed_stage', 'speedup', 'speedup_lcb', 'max_regression'):
                if trace['result'].get(key) != final_rows[cid].get(key):
                    raise ValueError(f'{cid}: summary and finalized {key} differ')
            if trace['lesson']['status'] != final_rows[cid]['lesson_status']:
                raise ValueError(f'{cid}: summary and finalized lesson status differ')
            directory = task / 'candidates' / cid.removeprefix(op + '-')
            plan = read(directory / 'candidate_plan.json')
            if plan['candidate_id'] != cid or plan['handler_id'] != trace['intervention']['handler']['id']:
                raise ValueError(f'{cid}: proposal handler identity differs from final trace')
            if plan['parameters'] != trace['intervention']['parameters']:
                raise ValueError(f'{cid}: proposal parameters differ from final trace')
            binding_path = directory / 'mechanism_binding.json'
            binding = read(binding_path) if binding_path.exists() else None
            if binding and binding['candidate_id'] != cid:
                raise ValueError(f'{cid}: mechanism binding has a different candidate')
            measurements = {}
            for phase in ('search', 'final'):
                path = task / 'timing' / phase / directory.name / 'measurement_report.json'
                if path.exists() and not path.with_name('raw_measurements.json').is_file():
                    raise ValueError(f'{cid}: {phase} report lacks raw measurements')
                measurements[phase] = (read(path) if path.exists() else None, path)
            attempts.append({'trace': trace, 'plan': plan, 'directory': directory,
                'binding': binding, 'measurements': measurements})
        chosen = selection.get('candidate_id')
        if chosen is not None:
            selected = next((a for a in attempts if a['trace']['identity']['candidate_id'] == chosen), None)
            if (selected is None or selected['trace']['result']['verdict'] not in GAIN_VERDICTS
                    or selection['source_hash'] != selected['trace']['provenance']['candidate_source_hash']):
                raise ValueError(f'{op}: selected source lacks its finalized gain/source identity')
        elif selection['source_hash'] != attempts[0]['trace']['provenance']['baseline_source_hash']:
            raise ValueError(f'{op}: retained baseline source hash differs')
        tasks.append({'operator': op, 'split': split, 'task': task, 'selection': selection, 'attempts': attempts})
    if len(all_ids) != expected_attempts:
        raise ValueError(f'expected {expected_attempts} finalized attempts, found {len(all_ids)}')
    return run, manifest, tasks


def hardware(task, identifier):
    directory = task / 'executions' / identifier
    groups = {}
    for path in sorted(directory.rglob('execution.json')):
        record = read(path)
        if record.get('physical_device') is None:
            continue  # CPU build/verifier records are not device evidence.
        stage = str(path.relative_to(directory))
        category = ('计时' if 'timing' in stage else '剖析' if 'profile' in stage else
            '正确性' if 'correctness' in stage or 'special-values' in stage else '执行')
        groups.setdefault(category, set()).add((record.get('host', '未知主机'), record['physical_device']))
    parts = [category + '：' + '，'.join(f'{host}/物理设备{device}' for host, device in sorted(devices))
        for category, devices in sorted(groups.items())]
    if '计时' not in groups:
        parts.append('没有实际计时执行设备记录')
    return '；'.join(parts) + ('；' + link('执行记录', directory) if groups else '')


def render(run, expected_attempts=24, expected_operators=7):
    run, manifest, tasks = load_campaign(run, expected_attempts, expected_operators)
    traces = [a['trace'] for t in tasks for a in t['attempts']]
    states = Counter(t['lesson']['status'] for t in traces)
    verdicts = Counter(t['result']['verdict'] for t in traces)
    lines = [f'本报告覆盖 {len(tasks)} 个算子、{len(traces)} 个冻结尝试；全部来自已完成的机器归档。', '',
        '按“性能问题—干预—证据—适用条件—实测结果”整理。问题栏描述待验证假设；耗时下降本身不证明机制。'
        '候选和基线的交付选择直接引用 best_source_selection，本脚本不重新排名或授予门禁结论。', '',
        '“观测几何比”是各有效 case 配对 speedup 的等权几何平均，即 exp(mean(log(speedup_case)))；'
        '缺样或不稳定时仍只作描述。回归为 geometric_mean(候选/基线)−1，正数表示变慢。'
        '搜索只含冻结哨兵；最终接纳依据独立 all20 记录。CV 使用各 case 样本统计；数字显示 9 位有效数字，精确值见 JSON。', '',
        f"经验状态：supported={states['supported']}，refuted={states['refuted']}，inconclusive={states['inconclusive']}。"
        f"机器收益：生产范围 {verdicts['production_safe_gain']} 个，仅基准范围 {verdicts['benchmark_specialized_gain']} 个；其余结论均保留。", '',
        link('运行清单', run / 'run-manifest.json') + '；' + link('脚本', Path(__file__)), '']
    capacities = sorted((run / 'setup').glob('*capacity*.json'))
    for path in capacities:
        data = read(path)
        facts = {key: data[key] for key in ('soc', 'ub_bytes', 'aiv', 'aic') if key in data}
        lines += [f"平台实测：{esc(facts) if facts else '字段见快照'}；{link('容量原始快照', path)}。", '']
    for split in ('train', 'validation'):
        group = [t for t in tasks if t['split'] == split]
        lines += [f"**{split}（{'训练' if split == 'train' else '独立验证'}）：{len(group)} 个算子，{sum(len(t['attempts']) for t in group)} 次尝试**", '']
        if split == 'validation':
            lines += ['验证算子的结果单独呈现；不将其反向用于冻结候选的搜索或策略更新。', '']
        for task_data in group:
            task, op, selected = task_data['task'], task_data['operator'], task_data['selection']
            lines += [f'**{op}**', '',
                f"机器交付：{esc(selected.get('candidate_id') or '基线')}；{VERDICTS.get(selected['verdict'], selected['verdict'])}。"
                f"{link('选择依据', task / 'best_source_selection.json')}；{link('交付源码', selected['source_directory'])}。", '',
                '| 性能问题（假设） | 干预 | 证据 | 适用条件 | 实测结果 |',
                '| --- | --- | --- | --- | --- |']
            details = ['冻结工作负载：' + esc({key: task_data['attempts'][0]['trace']['workload'].get(key, '最终记录缺失')
                for key in ('case_ids', 'shapes', 'dtypes', 'layouts', 'attributes', 'accuracy_contract')}) + '。', '']
            for item in task_data['attempts']:
                trace, plan, directory, binding = item['trace'], item['plan'], item['directory'], item['binding']
                cid = trace['identity']['candidate_id']
                hid = trace['intervention']['handler']['id']
                problem, intervention, conditions = HANDLERS.get(hid, (
                    '；'.join(trace['diagnosis'].get('symptoms', [])) or trace['intervention']['rationale'],
                    trace['intervention']['intent'], '仅限最终记录覆盖的 dtype、shape、属性和平台；精确限制见候选计划'))
                lesson = trace['lesson']['status']
                mechanism = binding['status'] if binding else 'inconclusive（未提供三态绑定）'
                evidence = f"经验 {lesson}；机制集 {mechanism}；" + link('最终 trace', task / 'optimization_traces.jsonl')
                if binding:
                    evidence += '；' + link('计数器绑定', directory / 'mechanism_binding.json')
                scope = ','.join(trace['workload'].get('dtypes', [])) or 'dtype 未记录'
                result = trace['result']
                timing, timing_path = item['measurements']['final']
                search, search_path = item['measurements']['search']
                observed_final = observed(timing)
                measured_text = '最终：' + observed_final['text']
                if search:
                    measured_text += '；搜索哨兵：' + observed(search)['text']
                measured_text += '；机器裁决：' + VERDICTS.get(result['verdict'], result['verdict']) + f"（{result['verdict']}）"
                if result['verdict'] in GAIN_VERDICTS:
                    measured_text += '；合格收益 ' + number(result.get('speedup')) + '×'
                else:
                    measured_text += '；无机器合格收益'
                measured_text += '；门禁 speedup=' + number(result.get('speedup'), null_reason(trace, '$.result.speedup', '门禁没有接纳稳定最终计时'))
                measured_text += '，LCB=' + number(result.get('speedup_lcb'), null_reason(trace, '$.result.speedup_lcb', '没有可用下界'))
                if result.get('first_failed_stage'):
                    measured_text += '；首个阻断：' + esc(result['first_failed_stage'])
                lines.append('| ' + ' | '.join([esc(problem), link(cid, directory / 'candidate_plan.json') + '：' + esc(intervention),
                    evidence, esc(conditions) + '；dtype=' + esc(scope), measured_text]) + ' |')
                details += [f'**{cid} 的证据与反证**', '',
                    '参数：`' + esc(trace['intervention']['parameters']).replace('`', '\\`') + '`；' + link('完整计划', directory / 'candidate_plan.json') + '。', '',
                    '执行门禁：' + esc('；'.join(f"{name}={trace['validation'].get(name, {}).get('status', '未记录')}"
                        for name in ('static_review', 'build', 'correctness', 'runtime', 'timing', 'profile')))
                    + '；正确性通过/总 case：' + number(trace['validation'].get('passed_count'), '最终记录缺少通过数')
                    + '/' + number(trace['validation'].get('case_count'), '最终记录缺少总数') + '。', '',
                    '来源：' + hash_link(run, split, trace['provenance'].get('baseline_source_hash'), '基线源码') + '；'
                    + hash_link(run, split, trace['provenance'].get('candidate_source_hash'), '候选源码') + '；'
                    + hash_link(run, split, trace['provenance'].get('patch_hash'), '补丁') + '。', '',
                    '硬件：' + hardware(task, directory.name) + '；' + hash_link(run, split,
                        trace['workload'].get('hardware_fingerprint'), '平台指纹',
                        null_reason(trace, '$.workload.hardware_fingerprint', '未记录平台分母')) + '。', '',
                    '图路由：' + esc(trace['routing']['mode']) + '；图覆盖缺口：' + esc(trace['routing'].get('coverage_gap') or '没有记录缺口；以最终路由为准') + '。', '']
                for phase, report, path in [('最终', timing, timing_path), ('搜索哨兵', search, search_path)]:
                    stats = observed(report)
                    if report:
                        details += [phase + ' case 差异：' + stats['text'] + '；' + '；'.join(stats['details']) + '。'
                            + link('测量报告', path) + '；' + link('原始配对', path.with_name('raw_measurements.json')), '']
                        if report.get('reasons'):
                            details += [phase + ' 未解决测量问题：' + esc('；'.join(report['reasons'])) + '。', '']
                failures = [f"{name}={value['status']}：{value.get('reason') or '原因未记录'}"
                    for name, value in trace['validation'].items() if isinstance(value, dict) and value.get('status') in ('failed', 'interrupted')]
                skipped = [f"{name}=not_run：{value.get('reason') or '原因未记录'}"
                    for name, value in trace['validation'].items() if isinstance(value, dict) and value.get('status') == 'not_run']
                if failures:
                    details += ['失败证据：' + esc('；'.join(failures)) + '。', '']
                if skipped:
                    details += ['未执行阶段：' + esc('；'.join(skipped)) + '。', '']
                if binding:
                    details += ['| 机制 case / metric | 原始计数器 基线→候选 | 预期方向 | 判断与限制 |',
                        '| --- | --- | --- | --- |']
                    for comparison in binding.get('comparisons', []):
                        reason = comparison.get('reason') or '没有完整对照'
                        before = number(comparison.get('baseline_value'), reason)
                        after = number(comparison.get('candidate_value'), reason)
                        details.append('| ' + ' | '.join([esc(f"{comparison['case_id']} / {comparison['name']}"),
                            before + '→' + after + ' ' + esc(comparison.get('unit') or '单位未记录'),
                            esc(comparison['expected_direction']), esc(comparison['status'] + '：' + reason
                                + ('；' + comparison['limitation'] if comparison.get('limitation') else ''))]) + ' |')
                    details += ['', '机制集结论：' + esc(binding['status']) + '；' + esc(binding.get('reason', '未提供原因'))
                        + '。计数器方向一致也不证明排他因果；refuted/inconclusive 不会因耗时下降而改判。', '']
                unresolved = list(dict.fromkeys(trace['diagnosis'].get('missing_evidence', []) + plan.get('missing_evidence', [])))
                if unresolved:
                    details += ['缺失视图/原计划待验证项（保留历史语境）：' + esc('；'.join(map(str, unresolved))) + '。', '']
                for label, key in [('有效条件（最终记录）', 'effective_conditions'), ('无效条件/反例', 'ineffective_conditions'),
                                   ('反例 case', 'counterexamples'), ('限制', 'limitations')]:
                    values = trace['lesson'].get(key, [])
                    if values:
                        details += [label + '：' + esc('；'.join(values)) + '。', '']
                details += ['后续方向（归档记录）：' + esc(trace['lesson']['next_step']) + '。', '']
            lines += ['', '<details>', f'<summary>{op}：源码/硬件哈希、case 差异、机制对照与未解决方向</summary>', '', *details, '</details>', '']
    lines += ['报告只呈现归档事实。原始收益、机制支持、生产适用范围及最终源码选择是分别记录的结论；'
        '失败和未解决方向不会从报告中删除。', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=DEFAULT_RUN)
    parser.add_argument('--output', type=Path, help='Default: <run>/optimization_lessons.md')
    parser.add_argument('--expected-attempts', type=int, default=24)
    parser.add_argument('--expected-operators', type=int, default=7)
    args = parser.parse_args()
    text = render(args.run, args.expected_attempts, args.expected_operators)
    output = (args.output or args.run / 'optimization_lessons.md').resolve()
    if output.exists() and output.read_text() != text:
        raise ValueError('refusing to overwrite a different lessons report; choose a new output path')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text)
    print(json.dumps({'status': 'rendered', 'output': str(output),
        'sha256': hashlib.sha256(text.encode()).hexdigest(), 'attempt_count': args.expected_attempts}, ensure_ascii=False))


if __name__ == '__main__':
    main()
