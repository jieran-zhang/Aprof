"""Pure Task Duration partition/calibration for a prospective windowed method.

This helper has no collector, gate, or publication authority. Native command
intervals below are derived only for payload validation, never persisted ACKs.
"""
from decimal import Decimal, localcontext
import math
from pathlib import Path

from .errors import ContractError
from .task_timing import _native, _tasks, PHASES, ROLES
from .measurement_admission import _pilot_samples, _session_samples


def _need(condition, message):
    if not condition:
        raise ContractError(message)


def _names(value):
    _need(isinstance(value, dict) and set(value) == set(ROLES), "kernel roles differ")
    for role in ROLES:
        sequence = value[role]
        _need(isinstance(sequence, (list, tuple)) and bool(sequence)
              and all(isinstance(name, str) and name and name.strip() == name for name in sequence),
              "invalid serial kernel sequence")
    return value


def case_task_config(config, case_id=None):
    """Validate all v5 case bindings and project one case for the v4 parser.

    Only this temporary view has scalar counts/sequences. Registered config,
    source inventory, case commands and workload refs retain the complete maps.
    """
    _need(isinstance(config, dict), "invalid case Task config")
    ids = config.get("expected_case_ids")
    _need(isinstance(ids, list) and ids and all(type(cid) is int and cid > 0 for cid in ids)
          and len(ids) == len(set(ids)), "invalid case Task scope")
    selected = ids[0] if case_id is None else case_id
    _need(type(selected) is int and selected in ids, "unregistered Task case")
    keys = {str(cid) for cid in ids}
    roles = config.get("roles")
    profile = config.get("task_profile")
    _need(isinstance(roles, dict) and set(roles) == set(ROLES)
          and isinstance(profile, dict), "invalid case Task roles/profile")
    names = profile.get("role_kernel_names")
    _need(isinstance(names, dict) and set(names) == set(ROLES), "case kernel roles differ")
    projected_roles, projected_names = {}, {}
    for role in ROLES:
        definition = roles[role]
        _need(isinstance(definition, dict), "invalid case callback definition")
        counts, sequences = definition.get("launches_per_operator"), names[role]
        _need(isinstance(counts, dict) and set(counts) == keys
              and isinstance(sequences, dict) and set(sequences) == keys,
              "case callback map scope differs")
        for key in keys:
            count, sequence = counts[key], sequences[key]
            _need(type(count) is int and count > 0
                  and isinstance(sequence, list) and len(sequence) == count
                  and all(isinstance(name, str) and name and name.strip() == name for name in sequence),
                  "invalid case complete-call kernel sequence")
        projected_roles[role] = {**definition, "launches_per_operator": counts[str(selected)]}
        projected_names[role] = list(sequences[str(selected)])
    return {**config, "roles": projected_roles,
            "task_profile": {**profile, "role_kernel_names": projected_names}}


def _derived_events(messages, mode):
    events = []
    for message in messages[1:]:
        if message["kind"] == "complete":
            start = message["untimed_verifications"][0]["started_monotonic_ns"]
            finish = message["untimed_verifications"][-1]["finished_monotonic_ns"]
        elif mode == "pilot" and message["kind"] == "pilot_sample":
            start = message["baseline"]["started_monotonic_ns"]
            finish = message["baseline"]["finished_monotonic_ns"]
        else:
            start, finish = message["started_monotonic_ns"], message["finished_monotonic_ns"]
        events.append({"request_monotonic_ns": start, "response_monotonic_ns": finish,
                       "message": message})
    return events


def partition_window_tasks(table_path=None, messages=None, *, csv_text=None, config,
                           mode, cycle, repeat, role_kernel_names):
    """Partition every serial callback Task, retaining 3 pilot or 30 macro samples.

    Current one-kernel pilot has 722 Tasks (721 baseline, one candidate snapshot).
    Serial multi-kernel callbacks are validated against the exact registered
    name sequence and have proportionally more Tasks.
    """
    _need((table_path is None) != (csv_text is None), "provide exactly one Task CSV source")
    _need(isinstance(messages, list) and isinstance(config, dict)
          and isinstance(config.get("operator"), str) and bool(config["operator"])
          and isinstance(config.get("roles"), dict)
          and all(isinstance(config["roles"].get(role), dict)
                  and type(config["roles"][role].get("launches_per_operator")) is int
                  for role in ROLES),
          "invalid native messages or operator")
    _need(mode in ("pilot", "confirmation") and type(cycle) is int
          and (cycle == 0 if mode == "pilot" else 0 <= cycle < 6),
          "invalid native mode or cycle")
    _need(type(repeat) is int and 100 <= repeat <= 100000 and repeat % 100 == 0
          and (mode != "pilot" or repeat == 100), "invalid Task sampling repeat")
    names = _names(role_kernel_names)
    _need(all(len(names[role]) == config["roles"][role]["launches_per_operator"] for role in ROLES),
          "registered serial kernel count differs from native callback")
    try:
        if mode == "pilot":
            _need(len(messages) == 6, "pilot needs READY and five commands")
            ready = messages[0]
            _pilot_samples({"mode": "pilot", "cycle": 0, "ready": ready,
                            "execution": {"pid": ready["pid"]},
                            "events": _derived_events(messages, mode)}, config)
        else:
            ready = _native(messages, config["operator"], cycle, repeat, names)
            _session_samples({"mode": "confirmation", "cycle": cycle, "ready": ready,
                              "execution": {"pid": ready["pid"]},
                              "events": _derived_events(messages, mode)},
                             config, expected_repeat=repeat)
    except (KeyError, IndexError, TypeError) as error:
        raise ContractError("invalid native Task window payload") from error
    if table_path is not None:
        csv_text = Path(table_path).read_text(encoding="utf-8")
    _need(isinstance(csv_text, str), "Task CSV must be text")
    rows, tasks, auxiliary = _tasks(csv_text, ready, names)
    _need(not auxiliary and len(rows) == len(tasks), "full Task CSV contains auxiliary rows")
    expected_count = ((721 * len(names["baseline"]) + len(names["candidate"])) if mode == "pilot"
                      else ((1011 + 25 * repeat) * len(names["baseline"])
                            + (211 + 5 * repeat) * len(names["candidate"])))
    _need(len(tasks) == expected_count, "full Task CSV count differs")
    groups = []
    values = {phase: {role: [] for role in ROLES} for phase in PHASES}
    pilot_samples = []
    cursor = 0

    def consume(kind, implementation, calls, *, phase=None, pair_index=None, role=None, sample=None):
        nonlocal cursor
        sequence = names[implementation]
        count = calls * len(sequence)
        selected = tasks[cursor:cursor + count]
        _need(len(selected) == count
              and all(task["op_name"] == sequence[index % len(sequence)]
                      for index, task in enumerate(selected)),
              "Task count or serial callback kernel order differs")
        # Default Decimal precision can round a 100-call sum up to the
        # 10 ms calibration boundary before choose_task_repeat sees it.
        durations = [task["duration_us"] for task in selected]
        with localcontext() as context:
            context.prec = max(28, max(value.adjusted() for value in durations)
                               - min(value.as_tuple().exponent for value in durations)
                               + len(str(len(durations))) + 5)
            total = sum(durations, Decimal(0)) * 1000
        span = (selected[-1]["end_us"] - selected[0]["start_us"]) * 1000
        gap = max((right["start_us"] - left["end_us"] for left, right in zip(selected, selected[1:])),
                  default=Decimal(0)) * 1000
        duration_float, per_call_float, span_float, gap_float = (
            float(total), float(total / calls), float(span), float(gap))
        _need(duration_float > 0 and per_call_float > 0
              and all(math.isfinite(value) for value in
                      (duration_float, per_call_float, span_float, gap_float)),
              "Task duration or span cannot be represented finitely")
        group = {"kind": kind, "phase": phase, "pair_index": pair_index, "role": role,
                 "implementation": implementation, "calls": calls,
                 "task_indices": [cursor, cursor + count],
                 "csv_row_indices": [task["csv_row_index"] for task in selected],
                 "task_count": count, "task_duration_total_ns": duration_float,
                 "task_duration_total_ns_decimal": str(total),
                 "task_duration_ns_per_call": per_call_float,
                 "task_span_ns": span_float, "max_intertask_gap_ns": gap_float,
                 "event_ns_per_call": sample["elapsed_ns"] if sample else None,
                 "host_wall_ns": (sample["finished_monotonic_ns"] - sample["started_monotonic_ns"])
                 if sample else None}
        groups.append(group)
        cursor += count
        if kind == "pilot_sample":
            pilot_samples.append(str(total))
        elif kind == "pair":
            values[phase][role].append(per_call_float)

    if mode == "pilot":
        consume("warmup", "baseline", 20, role="baseline")
        for role in messages[1]["prime_order"]:
            _need(role == "baseline", "pilot prime was not baseline-only")
            consume("prime", "baseline", 100, phase="pilot", role=role)
        for index in range(3):
            message = messages[index + 2]
            consume("pilot_sample", "baseline", 100, phase="pilot", pair_index=index,
                    role="baseline", sample=message["baseline"])
    else:
        for slot in range(2):
            role = ROLES[(slot + cycle) % 2]
            consume("warmup", role, 10, role=role)
        for phase_index, phase in enumerate(PHASES):
            prime = messages[1 + 6 * phase_index]
            for role in prime["prime_order"]:
                consume("prime", role if phase == "formal" else "baseline", 100,
                        phase=phase, role=role)
            for pair_index in range(5):
                message = messages[2 + 6 * phase_index + pair_index]
                for role in message["order"]:
                    sample = message[role]
                    consume("pair", sample["implementation"], repeat, phase=phase,
                            pair_index=pair_index, role=role, sample=sample)
    for role in ROLES:
        consume("snapshot", role, 1, role=role)
    _need(cursor == len(tasks) == expected_count, "missing or extra Task in full CSV")
    if mode == "pilot":
        _need(len(pilot_samples) == 3 and sum(group["kind"] == "pilot_sample" for group in groups) == 3,
              "pilot Task sample count differs")
    else:
        _need(sum(group["kind"] == "pair" for group in groups) == 30
              and all(len(values[phase][role]) == 5 for phase in PHASES for role in ROLES),
              "confirmation must contain 30 macro samples")
    return {"metric": "msprof.op_summary.Task_Duration", "mode": mode,
            "native_protocol": ready["protocol"],
            "native_intervals": "derived_payload_validation_only", "operator": config["operator"],
            "cycle": cycle, "repeat": repeat, "task_count": len(tasks),
            "csv_row_count": len(rows), "noncompute_csv_row_indices": auxiliary,
            "groups": groups, "pilot_samples_task_total_ns_decimal": pilot_samples,
            "values_ns_per_call": values if mode == "confirmation" else None}


def choose_task_repeat(pilot_partition):
    """Freeze R once from three fresh baseline 100-call Task totals; target 10 ms."""
    _need(isinstance(pilot_partition, dict) and pilot_partition.get("mode") == "pilot"
          and pilot_partition.get("metric") == "msprof.op_summary.Task_Duration"
          and pilot_partition.get("repeat") == 100,
          "calibration requires one complete Task pilot")
    samples = pilot_partition.get("pilot_samples_task_total_ns_decimal")
    groups = pilot_partition.get("groups")
    _need(isinstance(samples, list) and len(samples) == 3
          and all(isinstance(value, str) for value in samples)
          and isinstance(groups, list) and all(isinstance(g, dict) for g in groups)
          and len([g for g in groups if g.get("kind") == "pilot_sample"]) == 3,
          "pilot baseline sample count differs")
    try:
        totals = [Decimal(value) for value in samples]
        recorded = [Decimal(group["task_duration_total_ns_decimal"])
                    for group in groups if group.get("kind") == "pilot_sample"]
    except (KeyError, TypeError, ArithmeticError) as error:
        raise ContractError("invalid exact pilot Task totals") from error
    _need(all(value.is_finite() and value > 0 for value in totals)
          and totals == recorded
          and all(isinstance(group.get("task_duration_total_ns_decimal"), str)
                  and group.get("implementation") == group.get("role") == "baseline"
                  and group.get("calls") == 100 for group in groups if group.get("kind") == "pilot_sample"),
          "pilot calibration includes candidate or altered Task duration")
    median = sorted(totals)[1]
    _need(median >= Decimal(10_000_000) / 1000,
          "10 ms Task target exceeds maximum repeat")
    numerator, denominator = median.as_integer_ratio()
    windows = (10_000_000 * denominator + numerator - 1) // numerator
    repeat = max(100, 100 * windows)
    _need(repeat <= 100000, "10 ms Task target exceeds maximum repeat")
    with localcontext() as context:
        context.prec = max(28, len(median.as_tuple().digits) + len(str(windows)) + 7)
        predicted_ms = str(median * windows / Decimal(1_000_000))
    return {"metric": "msprof.op_summary.Task_Duration", "repeat": repeat,
            "target_ms": 10, "pilot_samples_100_calls_ns_decimal": [str(x) for x in totals],
            "median_100_calls_ns_decimal": str(median),
            "predicted_selected_duration_ms_decimal": predicted_ms,
            "pilot_excluded_from_confirmation": True}
