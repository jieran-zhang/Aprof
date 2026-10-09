"""Explicit protocol admission for byte-preserving storage readers.

Missing protocol fields occur in old closure records and retain their original
six-process requirement. Only the named search-lite protocol admits two rows.
Measurement evidence is replayed elsewhere; storage never promotes its claims.
"""
from msprof_search_protocol import LITE_PROTOCOL, LITE_ANALYSIS, LITE_PRODUCER, LITE_DESIGN

LEGACY_PROTOCOLS = (None, 'msprof_task_time_exploration_v1', 'msprof_task_time_exploration_v2')


def require(value, message):
    if not value:
        raise ValueError(message)


def cohort_process_count(*, plan=None, report=None):
    documents = [value for value in (plan, report) if value is not None]
    require(documents, 'cohort protocol declaration is required')
    protocols = [value.get('protocol') for value in documents]
    require(all(value in (*LEGACY_PROTOCOLS, LITE_PROTOCOL) for value in protocols),
            'unsupported storage measurement protocol')
    if LITE_PROTOCOL not in protocols:
        return 6
    require(all(value == LITE_PROTOCOL for value in protocols), 'cohort plan/report protocol mismatch')
    require(all(value.get('analysis_version') == LITE_ANALYSIS for value in documents),
            'lite storage requires its explicit analysis version')
    if plan is not None:
        schedule = plan.get('schedule', [])
        require(len(schedule) == 2, 'lite cohort requires exactly two planned processes')
        for entry, design in zip(schedule, LITE_DESIGN):
            request = entry.get('request', {})
            require(request.get('version') == LITE_PRODUCER, 'lite plan/producer protocol mismatch')
            require(tuple(request.get(key) for key in ('load_order', 'first_order', 'buffer_configs')) == design,
                    'lite process order design differs')
            if 'pairs' in request:
                require(type(request['pairs']) is int and request['pairs'] == 6, 'lite pair count differs')
            if 'warmup' in request:
                require(type(request['warmup']) is int and request['warmup'] == 10, 'lite warmup differs')
    if report is not None:
        require(report.get('formal_admission') == 'not_evaluated'
                and report.get('graph_policy_eligible') is False and report.get('episode_ref') is None,
                'lite storage cannot promote formal or graph admission')
        for row in [*report.get('results', []), *report.get('suite', {}).values()]:
            require(row.get('qualified_performance_eligible') is False and row.get('ci95') is None,
                    'lite storage cannot promote qualified performance or confidence intervals')
    return 2


def validate_prepared_request(request, *, lite):
    require(request.get('version') == (LITE_PRODUCER if lite else 'msprof_kernel_time_study_v2'),
            'prepared request producer differs from cohort protocol')
    if 'pairs' in request:
        require(type(request['pairs']) is int and request['pairs'] == (6 if lite else 30),
                'request pair count differs from cohort protocol')
