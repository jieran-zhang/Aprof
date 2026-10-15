"""Full-table Task Duration partition tests; synthetic CSV is not hardware evidence."""

import csv
from copy import deepcopy
from io import StringIO

import pytest

from aprof_runtime.errors import ContractError
from aprof_runtime.task_timing import partition_task_samples
from test_shared_measurement_admission import draft, wire


FIELDS = ["Op Name", "Task Start Time(us)", "Task Duration(us)", "Task Type",
          "Stream ID", "Task ID", "Device_id"]


def native(config, cycle=0, launches=1):
    ready, events = wire(config, cycle, repeat=100)
    messages = [ready] + [event["message"] for event in events]
    for message in messages:
        message["launches_per_operator"] = {"baseline": launches, "candidate": launches}
        if message["kind"] == "pair":
            for role in ("baseline", "candidate"):
                message[role]["launches_per_operator"] = launches
    return messages


def task_rows(messages, names):
    cycle = messages[0]["cycle_index"]
    calls = []
    for slot in range(2):
        calls += [(('baseline', 'candidate')[(slot + cycle) % 2], None)] * 10
    for phase_index, phase in enumerate(("aa_before", "formal", "aa_after")):
        prime = messages[1 + 6 * phase_index]
        for role in prime["prime_order"]:
            calls += [(role if phase == "formal" else "baseline", None)] * 100
        for pair_index in range(5):
            pair = messages[2 + 6 * phase_index + pair_index]
            for role in pair["order"]:
                calls += [(pair[role]["implementation"], phase)] * 100
    calls += [("baseline", None), ("candidate", None)]
    rows = []
    for implementation, phase in calls:
        for name in names[implementation]:
            index = len(rows)
            duration = "2" if phase == "formal" and implementation == "candidate" else "4"
            rows.append({"Op Name": name, "Task Start Time(us)": str(index * 10 + 1),
                         "Task Duration(us)": duration, "Task Type": "AI_CORE",
                         "Stream ID": "7", "Task ID": str(index + 1), "Device_id": "0"})
    return rows


def table(rows, fields=FIELDS):
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def partition(rows, messages, names, **options):
    return partition_task_samples(csv_text=table(rows), messages=messages,
                                  operator="synthetic_exp", cycle=messages[0]["cycle_index"],
                                  repeat=100, role_kernel_names=names, **options)


def test_complete_single_kernel_task_duration_not_event_or_task_count_n(draft):
    _, config = draft
    messages = native(config)
    names = {"baseline": ["exp_kernel"], "candidate": ["exp_kernel"]}
    rows = task_rows(messages, names)
    report = partition(rows, messages, names)
    assert report["metric"] == "msprof.op_summary.Task_Duration"
    assert report["native_protocol"] == "shared_buffer_acl_event_v2"
    assert report["native_intervals"] == "derived_payload_validation_only"
    assert report["task_count"] == 4222
    assert len(report["groups"]) == 46
    assert sum(group["kind"] == "pair" for group in report["groups"]) == 30
    assert report["values_ns_per_call"]["formal"]["candidate"] == [2000.0] * 5
    assert report["values_ns_per_call"]["formal"]["baseline"] == [4000.0] * 5
    assert report["values_ns_per_call"]["aa_before"]["candidate"] == [4000.0] * 5
    pair = next(group for group in report["groups"] if group["kind"] == "pair")
    assert pair["task_count"] == 100 and pair["task_duration_total_ns"] == 400_000
    assert pair["event_ns_per_call"] == pytest.approx(100) and pair["host_wall_ns"] == 49_990
    assert sorted(index for group in report["groups"] for index in group["csv_row_indices"]) == list(range(4222))


def test_serial_multi_kernel_exact_call_sequence(draft):
    _, config = draft
    messages = native(config, launches=2)
    names = {"baseline": ["base_a", "base_b"], "candidate": ["cand_a", "cand_b"]}
    rows = task_rows(messages, names)
    report = partition(rows, messages, names)
    assert report["task_count"] == report["csv_row_count"] == 8444
    assert report["noncompute_csv_row_indices"] == []
    assert report["values_ns_per_call"]["formal"]["candidate"] == [4000.0] * 5
    assert sorted(index for group in report["groups"] for index in group["csv_row_indices"]) == list(range(8444))


def test_rejects_serial_multi_kernel_reordering(draft):
    _, config = draft
    messages = native(config, launches=2)
    names = {"baseline": ["base_a", "base_b"], "candidate": ["cand_a", "cand_b"]}
    rows = task_rows(messages, names)
    rows[0]["Op Name"], rows[1]["Op Name"] = rows[1]["Op Name"], rows[0]["Op Name"]
    with pytest.raises(ContractError):
        partition(rows, messages, names)


@pytest.mark.parametrize("mutation", ["missing", "extra", "wrong_name", "duplicate",
                                      "overlap", "wrong_device", "wrong_stream", "mixed",
                                      "unknown_type", "na_type", "empty_type", "memcpy_type",
                                      "negative_duration", "zero_duration", "nan_duration"])
def test_rejects_incomplete_or_ambiguous_task_table(draft, mutation):
    _, config = draft
    messages = native(config)
    names = {"baseline": ["exp_kernel"], "candidate": ["exp_kernel"]}
    rows = task_rows(messages, names)
    if mutation == "missing":
        rows.pop(1000)
    elif mutation == "extra":
        item = deepcopy(rows[-1]); item["Task ID"] = "extra"; item["Task Start Time(us)"] = "50000"
        rows.append(item)
    elif mutation == "wrong_name":
        rows[1000]["Op Name"] = "unregistered_kernel"
    elif mutation == "duplicate":
        rows[1000] = deepcopy(rows[999])
    elif mutation == "overlap":
        rows[1000]["Task Start Time(us)"] = rows[999]["Task Start Time(us)"]
    elif mutation == "wrong_device":
        rows[1000]["Device_id"] = "1"
    elif mutation == "wrong_stream":
        rows[1000]["Stream ID"] = "8"
    elif mutation == "mixed":
        rows[1000]["Task Type"] = "MIX_AIC"
    elif mutation in {"unknown_type", "na_type", "empty_type", "memcpy_type"}:
        rows[1000]["Task Type"] = {
            "unknown_type": "UNKNOWN", "na_type": "N/A", "empty_type": "", "memcpy_type": "MEMCPY",
        }[mutation]
    elif mutation == "negative_duration":
        rows[1000]["Task Duration(us)"] = "-1"
    elif mutation == "zero_duration":
        rows[1000]["Task Duration(us)"] = "0"
    else:
        rows[1000]["Task Duration(us)"] = "NaN"
    with pytest.raises(ContractError):
        partition(rows, messages, names)


def test_rejects_wrong_native_launch_count_and_repeat(draft):
    _, config = draft
    messages = native(config)
    names = {"baseline": ["exp_kernel"], "candidate": ["exp_kernel"]}
    rows = task_rows(messages, names)
    with pytest.raises(ContractError):
        partition(rows, messages, {"baseline": ["a", "b"], "candidate": ["c", "d"]})
    with pytest.raises(ContractError):
        partition_task_samples(csv_text=table(rows), messages=messages, operator="synthetic_exp",
                               cycle=0, repeat=3000, role_kernel_names=names)


def test_csv_duration_units_are_explicit_and_each_tail_task_changes_mean(draft):
    _, config = draft
    messages = native(config)
    names = {"baseline": ["exp_kernel"], "candidate": ["exp_kernel"]}
    rows = task_rows(messages, names)
    before = partition(rows, messages, names)
    formal = next(group for group in before["groups"] if group["kind"] == "pair"
                  and group["phase"] == "formal")
    rows[formal["csv_row_indices"][-1]]["Task Duration(us)"] = "5"
    after = partition(rows, messages, names)
    role = formal["role"]
    assert after["values_ns_per_call"]["formal"][role][0] \
        == before["values_ns_per_call"]["formal"][role][0] + 10
    wrong_header = table(rows).replace("Task Duration(us)", "Task Duration(ms)", 1)
    with pytest.raises(ContractError):
        partition_task_samples(csv_text=wrong_header, messages=messages, operator="synthetic_exp",
                               cycle=0, role_kernel_names=names)
