"""Partition a complete msprof task table using the fixed v2 native schedule.

This is a pure replay helper.  Its native command envelopes are *derived* only
to validate payloads; they are never controller acknowledgements or receipts.
"""

import csv
from decimal import Decimal, InvalidOperation
from io import StringIO
from pathlib import Path

from .errors import ContractError


PHASES = ("aa_before", "formal", "aa_after")
ROLES = ("baseline", "candidate")
COMPUTE_TYPES = {"AI_CORE", "AI_VECTOR_CORE"}
MIX_TYPES = {"MIX_AIC", "MIX_AIV"}
# The qualified exp/sigmoid op_summary tables contain no auxiliary task type.
# Add one only after its profiling semantics are evidenced and reviewed.
AUXILIARY_TYPES = frozenset()
COLUMNS = {"Op Name", "Task Start Time(us)", "Task Duration(us)", "Task Type",
           "Stream ID", "Task ID", "Device_id"}


def protocol_commands():
    """The fixed 19-line confirmation command file for the v2 native header."""
    result = []
    for phase in PHASES:
        result.append(f"prime {len(result)} {phase}")
        for pair in range(5):
            result.append(f"pair {len(result)} {phase} {pair}")
    result.append(f"finish {len(result)}")
    return result


def _need(condition, message):
    if not condition:
        raise ContractError(message)


def _decimal(value, field):
    try:
        number = Decimal(value.strip())
    except (AttributeError, InvalidOperation):
        raise ContractError("invalid " + field) from None
    _need(number.is_finite() and number >= 0, "invalid " + field)
    return number


def _native(messages, operator, cycle, repeat, names):
    """Validate v2 payloads with derived intervals, never persisted as ACKs."""
    from .measurement_admission import _session_samples

    _need(isinstance(messages, list) and len(messages) == 20, "expected READY and 19 native messages")
    ready = messages[0]
    _need(isinstance(ready, dict), "invalid native READY")
    events = []
    try:
        for message in messages[1:]:
            if message["kind"] == "complete":
                start = message["untimed_verifications"][0]["started_monotonic_ns"]
                end = message["untimed_verifications"][-1]["finished_monotonic_ns"]
            else:
                start, end = message["started_monotonic_ns"], message["finished_monotonic_ns"]
            events.append({"request_monotonic_ns": start, "response_monotonic_ns": end,
                           "message": message})
        config = {"operator": operator, "device": ready["device"],
                  "roles": {role: {"symbol": ready["role_symbols"][role],
                                   "launches_per_operator": len(names[role])} for role in ROLES}}
        _session_samples({"mode": "confirmation", "cycle": cycle, "ready": ready,
                          "execution": {"pid": ready["pid"]}, "events": events},
                         config, expected_repeat=repeat)
    except (KeyError, IndexError, TypeError) as error:
        raise ContractError("invalid native command payload") from error
    return ready


def _tasks(csv_text, ready, names):
    reader = csv.DictReader(StringIO(csv_text))
    _need(reader.fieldnames is not None and len(reader.fieldnames) == len(set(reader.fieldnames))
          and COLUMNS <= set(reader.fieldnames), "unknown task table schema")
    rows = list(reader)
    tasks = []
    noncompute = []
    known = {name for sequence in names.values() for name in sequence}
    for row_index, row in enumerate(rows):
        _need(None not in row and all(row[column] is not None for column in COLUMNS),
              "malformed task table row")
        kind, name = row["Task Type"], row["Op Name"]
        _need(kind not in MIX_TYPES, "MIX tasks cannot be counted twice")
        if kind not in COMPUTE_TYPES:
            _need(kind in AUXILIARY_TYPES and name not in known, "unregistered task type")
            noncompute.append(row_index)
            continue
        _need(name in known, "unregistered compute kernel")
        start = _decimal(row["Task Start Time(us)"], "task start")
        duration = _decimal(row["Task Duration(us)"], "Task Duration(us)")
        _need(duration > 0, "Task Duration(us) must be positive")
        _need(row["Device_id"] == str(ready["device"]) and bool(row["Stream ID"])
              and bool(row["Task ID"]), "task device/stream/identity differs")
        tasks.append({"csv_row_index": row_index, "op_name": name,
                      "task_type": kind, "device": row["Device_id"],
                      "stream": row["Stream ID"], "task_id": row["Task ID"],
                      "start_us": start, "duration_us": duration, "end_us": start + duration})
    _need(bool(tasks) and len({task["stream"] for task in tasks}) == 1,
          "compute tasks require one stream")
    identities = [(task["device"], task["stream"], task["task_id"], task["start_us"])
                  for task in tasks]
    _need(len(set(identities)) == len(tasks), "duplicate task identity")
    tasks.sort(key=lambda task: (task["start_us"], task["csv_row_index"]))
    _need(all(right["start_us"] >= left["end_us"] for left, right in zip(tasks, tasks[1:])),
          "overlapping or parallel compute tasks")
    return rows, tasks, noncompute


def partition_task_samples(table_path=None, messages=None, *, csv_text=None, operator,
                           cycle, repeat=100, role_kernel_names):
    """Return 30 Task Duration ns/call samples and an exhaustive task partition.

    ``role_kernel_names`` preregisters the exact ordered kernels in one callback
    call.  AA candidate *slots* execute the baseline callback.  CSV row indexes
    are zero-based data rows and retain the full original table's row identity.
    """
    _need((table_path is None) != (csv_text is None), "provide one task CSV source")
    _need(type(repeat) is int and repeat == 100, "Task Duration protocol requires repeat=100")
    _need(type(cycle) is int and 0 <= cycle < 6 and isinstance(operator, str) and operator,
          "invalid operator or cycle")
    names = role_kernel_names
    _need(isinstance(names, dict) and set(names) == set(ROLES), "kernel roles differ")
    for role in ROLES:
        sequence = names[role]
        _need(isinstance(sequence, (list, tuple)) and sequence and
              all(isinstance(name, str) and name.strip() == name and name for name in sequence),
              "invalid registered kernel sequence")
    if table_path is not None:
        csv_text = Path(table_path).read_text(encoding="utf-8")
    _need(isinstance(csv_text, str), "task CSV must be text")
    ready = _native(messages, operator, cycle, repeat, names)
    rows, tasks, noncompute = _tasks(csv_text, ready, names)
    groups = []
    values = {phase: {role: [] for role in ROLES} for phase in PHASES}
    cursor = 0

    def consume(kind, implementation, calls, *, phase=None, pair_index=None, role=None, sample=None):
        nonlocal cursor
        expected = list(names[implementation]) * calls
        selected = tasks[cursor:cursor + len(expected)]
        _need(len(selected) == len(expected) and [task["op_name"] for task in selected] == expected,
              "task count or ordered kernel sequence differs")
        total = sum((task["duration_us"] for task in selected), Decimal(0)) * 1000
        span = (selected[-1]["end_us"] - selected[0]["start_us"]) * 1000
        gap = max((right["start_us"] - left["end_us"] for left, right in zip(selected, selected[1:])),
                  default=Decimal(0)) * 1000
        group = {"kind": kind, "phase": phase, "pair_index": pair_index,
                 "role": role, "implementation": implementation, "calls": calls,
                 "task_indices": [cursor, cursor + len(selected)],
                 "csv_row_indices": [task["csv_row_index"] for task in selected],
                 "task_count": len(selected), "task_duration_total_ns": float(total),
                 "task_span_ns": float(span), "max_intertask_gap_ns": float(gap),
                 "event_ns_per_call": sample["elapsed_ns"] if sample else None,
                 "host_wall_ns": (sample["finished_monotonic_ns"] - sample["started_monotonic_ns"])
                 if sample else None}
        groups.append(group)
        cursor += len(selected)
        if kind == "pair":
            values[phase][role].append(float(total / calls))

    for slot in range(2):
        role = ROLES[(slot + cycle) % 2]
        consume("warmup", role, 10, role=role)
    for phase_index, phase in enumerate(PHASES):
        prime = messages[1 + 6 * phase_index]
        for role in prime["prime_order"]:
            implementation = role if phase == "formal" else "baseline"
            consume("prime", implementation, 100, phase=phase, role=role)
        for pair_index in range(5):
            message = messages[2 + 6 * phase_index + pair_index]
            for role in message["order"]:
                sample = message[role]
                consume("pair", sample["implementation"], repeat, phase=phase,
                        pair_index=pair_index, role=role, sample=sample)
    for role in ROLES:
        consume("snapshot", role, 1, role=role)
    _need(cursor == len(tasks), "extra compute tasks in full task table")
    _need(all(len(values[phase][role]) == 5 for phase in PHASES for role in ROLES),
          "formal pair cardinality differs")
    return {"metric": "msprof.op_summary.Task_Duration", "native_protocol": ready["protocol"],
            "native_intervals": "derived_payload_validation_only", "operator": operator,
            "cycle": cycle, "repeat": repeat, "task_count": len(tasks),
            "csv_row_count": len(rows), "noncompute_csv_row_indices": noncompute,
            "groups": groups, "values_ns_per_call": values}
