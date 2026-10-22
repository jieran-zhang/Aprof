"""Six-pair screen only; never a formal measurement or gate projection."""
from decimal import Decimal
import json
import math
from shared_validation_adapter import selected_runtime

RELEASE = selected_runtime()
from aprof_runtime.task_timing import _tasks
from aprof_runtime.measurement_admission import _cv, _geomean

PROTOCOL = 'shared_buffer_msprof_task_screen_v1'
PREFIX = 'APROF_TASK_SCREEN_JSON:'
ROLES = ('baseline', 'candidate')
CASES = {'exp': [1, 3, 8, 9, 14, 20], 'sigmoid': [1, 3, 8, 14, 16, 20]}
COMMON = {'schema_version', 'protocol', 'operator', 'pid', 'device', 'context_address',
          'stream_address', 'warmup', 'repeat', 'prime_repeat', 'pairs',
          'launches_per_operator', 'role_symbols', 'buffers'}
INTERVAL = {'started_monotonic_ns', 'finished_monotonic_ns'}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def messages(stdout):
    return [json.loads(line[len(PREFIX):]) for line in stdout.splitlines() if line.startswith(PREFIX)]


def interval(value, lower=0, upper=None):
    a, b = (value[k] for k in ('started_monotonic_ns', 'finished_monotonic_ns'))
    need(type(a) is int and type(b) is int and lower <= a < b
         and (upper is None or b <= upper), 'screen interval order differs')
    return b


def partition(csv_text, wire, *, operator, device, role_kernel_names, expected_pid):
    need(operator in CASES and type(device) is int and device >= 0, 'unsupported screen scope')
    need(len(wire) == 9 and [m.get('kind') for m in wire] == ['ready', 'prime'] + ['pair'] * 6 + ['complete'],
         'screen needs its own nine messages')
    ready = wire[0]
    common = {key: ready[key] for key in COMMON}
    need(common['schema_version'] == '1.0.0' and common['protocol'] == PROTOCOL
         and common['operator'] == operator and type(common['pid']) is int
         and common['pid'] == expected_pid and expected_pid > 0 and common['device'] == device
         and all(type(common[key]) is int and common[key] == value for key, value in
                 {'warmup': 10, 'repeat': 100, 'prime_repeat': 100, 'pairs': 6}.items())
         and common['launches_per_operator'] == {r: 1 for r in ROLES}
         and common['role_symbols'] == {r: 'launch_' + r for r in ROLES}, 'screen identity differs')
    for key in ('context_address', 'stream_address'):
        need(isinstance(common[key], str) and common[key].isdigit() and int(common[key]) > 0,
             'screen context or stream missing')
    need(role_kernel_names == {r: ['aprof_' + r + '_' + operator + '_kernel'] for r in ROLES},
         'screen kernel role identity differs')
    spans, names = [], set()
    need(set(common['buffers']) == {'inputs', 'outputs', 'workspaces'}
         and common['buffers']['inputs'] and common['buffers']['outputs'], 'screen buffers missing')
    need([s['name'] for s in common['buffers']['inputs']] == ['input', 'baseline_tiling', 'candidate_tiling']
         and [s['name'] for s in common['buffers']['outputs']] == ['output']
         and common['buffers']['workspaces'] == [], 'screen complete shared buffer scope differs')
    for group in common['buffers'].values():
        need(isinstance(group, list), 'screen buffer roster invalid')
        for span in group:
            need(set(span) == {'name', 'address', 'bytes'} and isinstance(span['name'], str)
                 and span['name'] and span['name'] not in names and isinstance(span['address'], str)
                 and span['address'].isdigit() and int(span['address']) > 0
                 and type(span['bytes']) is int and span['bytes'] > 0, 'screen buffer identity invalid')
            a, b = int(span['address']), int(span['address']) + span['bytes']
            need(b <= 2**64 and all(b <= c or a >= d for c, d in spans), 'screen buffers overlap')
            spans.append((a, b)); names.add(span['name'])
    prior = 0
    for index, msg in enumerate(wire):
        extra = set() if index == 0 else ({'order'} if index == 1 else
            {'pair_index', 'order', *ROLES} if index < 8 else {'untimed_verifications', 'input_bytes_unchanged'})
        need(set(msg) == COMMON | INTERVAL | {'kind'} | extra
             and {key: msg[key] for key in COMMON} == common, 'screen wire fields or identity changed')
        prior = interval(msg, prior)
        if 2 <= index < 8:
            order = list(ROLES[::1 if index % 2 == 0 else -1])
            need(type(msg['pair_index']) is int and msg['pair_index'] == index - 2 and msg['order'] == order,
                 'screen pair schedule differs')
            selected = [msg[r] for r in order]
        elif index == 8:
            need(msg['input_bytes_unchanged'] is True, 'screen input mutation')
            order, selected = list(ROLES), msg['untimed_verifications']
            need(isinstance(selected, list) and len(selected) == 2, 'screen snapshots missing')
        else:
            if index == 1:
                need(msg['order'] == ['baseline', 'candidate', 'candidate', 'baseline'], 'screen prime order differs')
            continue
        last = msg['started_monotonic_ns']
        for role, sample in zip(order, selected, strict=True):
            need(set(sample) == INTERVAL | {'implementation', 'launches_per_operator'}
                 and sample['implementation'] == role and type(sample['launches_per_operator']) is int
                 and sample['launches_per_operator'] == 1, 'screen sample role differs')
            last = interval(sample, last, msg['finished_monotonic_ns'])
    rows, tasks, auxiliary = _tasks(csv_text, ready, role_kernel_names)
    need(not auxiliary and len(rows) == len(tasks) == 1622, 'screen full Task count differs')
    groups, values, cursor = [], {r: [] for r in ROLES}, 0
    schedule = [('warmup', r, 10, None) for r in ROLES]
    schedule += [('prime', r, 100, None) for r in wire[1]['order']]
    schedule += [('pair', r, 100, m['pair_index']) for m in wire[2:8] for r in m['order']]
    schedule += [('snapshot', r, 1, None) for r in ROLES]
    for kind, role, calls, pair in schedule:
        selected = tasks[cursor:cursor + calls]
        need(len(selected) == calls and all(t['op_name'] == role_kernel_names[role][0] for t in selected),
             'screen complete callback role or kernel sequence differs')
        total = sum((t['duration_us'] for t in selected), Decimal(0)) * 1000
        value = float(total / calls)
        need(math.isfinite(value) and value > 0, 'screen Task duration is not finite positive')
        groups.append({'kind': kind, 'role': role, 'pair_index': pair, 'calls': calls,
            'task_indices': [cursor, cursor + calls], 'csv_row_indices': [t['csv_row_index'] for t in selected],
            'task_duration_total_ns_decimal': str(total), 'task_duration_ns_per_call': value,
            'task_span_ns': float((selected[-1]['end_us'] - selected[0]['start_us']) * 1000)})
        cursor += calls
        if kind == 'pair': values[role].append(value)
    need(cursor == 1622 and all(len(v) == 6 for v in values.values()), 'screen partition incomplete')
    return {'protocol': PROTOCOL, 'operator': operator, 'task_count': cursor, 'pairs': 6,
            'metric': 'msprof.op_summary.Task_Duration', 'groups': groups, 'values_ns_per_call': values}


def case_summary(case_id, part):
    a, b = (part['values_ns_per_call'][r] for r in ROLES)
    need(part['protocol'] == PROTOCOL and len(a) == len(b) == 6
         and all(math.isfinite(v) and v > 0 for v in a + b), 'screen six pairs required')
    cvs = [_cv(a), _cv(b)]
    regression, speedup = _geomean([y/x for x, y in zip(a, b)]) - 1, _geomean([x/y for x, y in zip(a, b)])
    return {'case_id': case_id, 'baseline_cv': cvs[0], 'candidate_cv': cvs[1],
            'regression': regression, 'speedup': speedup, 'passed': max(cvs) <= .05 and regression <= .03}


def summarize(operator, partitions):
    need(operator in CASES and list(partitions) == CASES[operator], 'screen case roster differs')
    need(all(part['operator'] == operator for part in partitions.values()), 'mixed screen operators')
    rows = [case_summary(cid, part) for cid, part in partitions.items()]
    speedup = _geomean([row['speedup'] for row in rows])
    return {'protocol': PROTOCOL, 'exploration_only': True, 'eligible_for_formal_admission': False,
            'gate_projection': {}, 'per_case': rows, 'geomean_speedup': speedup,
            'passed': all(row['passed'] for row in rows) and speedup >= 1}
