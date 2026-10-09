"""Explicit exploratory sampling design; legacy/final protocols are unchanged.

Two processes cannot identify the independent effects of module loading, initial
order, and buffer order. This protocol supplies descriptive search feedback only.
"""

LITE_PROTOCOL = 'msprof_task_time_search_lite_v1'
LITE_ANALYSIS = 'msprof_search_lite_analysis_v1'
LITE_PRODUCER = 'msprof_kernel_time_search_lite_v1'
LITE_PAIRS = 6
LITE_WARMUP = 10
LITE_DESIGN = (
    ('AB', 'AB', 'normal,swapped'),
    ('BA', 'BA', 'swapped,normal'),
)


def pairs_for_producer(version):
    if version == LITE_PRODUCER:
        return LITE_PAIRS
    if version in ('msprof_kernel_time_study_v1', 'msprof_kernel_time_study_v2'):
        return 30
    raise ValueError('unknown timing producer: ' + str(version))
