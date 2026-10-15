"""CPU protocol checks only: compile the diagnostic header against fake ACL.

The fake event duration is not hardware evidence or measurement admission.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT / "scaffolding/benchmarks/cannbench/harness/device_submission_diagnostic_v2.h"
PROTOCOL = "shared_buffer_submission_diagnostic_v2"
PREFIX = "APROF_SHARED_TIMING_JSON:"
spec = importlib.util.spec_from_file_location(
    "long_enqueue_header_test_support",
    Path(__file__).with_name("test_device_shared_timing_header.py"),
)
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    compiler = shutil.which("g++")
    if compiler is None:
        pytest.skip("C++ compiler required for fake ACL protocol checks")
    directory = tmp_path_factory.mktemp("submission-v2-fake-acl")
    (directory / "acl").mkdir()
    (directory / "acl/acl.h").write_text(support.FAKE_ACL)
    program = support.PROGRAM.replace(
        '"device_shared_timing.h"', '"device_submission_diagnostic_v2.h"'
    ).replace('"fake_cpu_only"', "argv[2]").replace(
        ",1,2,", ",1,1,"
    ).replace("const bool mutate=argc>2;", "const bool mutate=argc>3;")
    (directory / "main.cpp").write_text(program)
    binary = directory / "native"
    subprocess.run(
        [compiler, "-std=c++17", "-O2", "-I", str(directory), "-I", str(HEADER.parent),
         str(directory / "main.cpp"), "-o", str(binary)],
        check=True, capture_output=True, text=True,
    )
    return binary


def run(native, *, operator="exp", mode="confirmation", repeat=7300, mutate=False):
    env = {key: value for key, value in os.environ.items() if not key.startswith("APROF_")}
    env.update(APROF_SHARED_MODE=mode, APROF_SHARED_REPEAT=str(repeat))
    result = subprocess.run(
        [str(native), "0", operator] + (["mutate"] if mutate else []),
        input=support.commands(), capture_output=True, text=True, timeout=15, env=env,
    )
    messages = [json.loads(line[len(PREFIX):]) for line in result.stdout.splitlines()
                if line.startswith(PREFIX)]
    return result, messages


def check_observations(sample):
    diagnostic = sample["submission_diagnostic"]
    assert diagnostic["schema_version"] == 1
    assert diagnostic["checkpoint_interval"] == 100
    segments = diagnostic["segments"]
    names = ("start_record", "enqueue", "end_record", "sync")
    assert set(segments) == set(names)
    observations = [segments[name][edge] for name in names for edge in ("before", "after")]
    walls = [point["wall_ns"] for point in observations]
    cpus = [point["thread_cpu_ns"] for point in observations]
    assert sample["started_monotonic_ns"] <= walls[0]
    assert walls == sorted(walls) and walls[-1] <= sample["finished_monotonic_ns"]
    assert cpus == sorted(cpus)
    usage_fields = {"utime_ns", "stime_ns", "minflt", "majflt", "nvcsw", "nivcsw"}
    for point in observations:
        assert set(point) == {"wall_ns", "thread_cpu_ns", "rusage"}
        assert set(point["rusage"]) == usage_fields
        assert all(type(value) is int and value >= 0 for value in point["rusage"].values())
    for field in usage_fields:
        counters = [point["rusage"][field] for point in observations]
        assert counters == sorted(counters)
    checkpoints = diagnostic["enqueue_checkpoints"]
    assert len(checkpoints) == 73
    assert [point["completed_launches"] for point in checkpoints] == list(range(100, 7301, 100))
    for clock in ("wall_ns", "thread_cpu_ns"):
        values = [segments["enqueue"]["before"][clock]]
        values.extend(point[clock] for point in checkpoints)
        values.append(segments["enqueue"]["after"][clock])
        assert values == sorted(values)
    # Clocks are read sequentially: never assert thread-CPU delta <= wall delta.


def test_one_complete_cycle_has_exact_calls_checkpoints_outputs_and_identity(native):
    result, messages = run(native)
    assert result.returncode == 0, result.stderr
    assert len(support.commands().splitlines()) == 19
    assert len(messages) == 20
    ready, complete = messages[0], messages[-1]
    assert ready["kind"] == "ready" and complete["kind"] == "complete"
    assert [message["command_index"] for message in messages[1:]] == list(range(19))
    identity = ("schema_version", "protocol", "operator", "cycle_index", "pid", "device",
                "context_address", "stream_address", "buffers", "warmup", "repeat", "prime_repeat",
                "execution_mode", "mode", "warmup_role_counts", "role_symbols", "launches_per_operator",
                "diagnostic_only", "measurement_admission_eligible")
    for message in messages:
        assert {key: message[key] for key in identity} == {key: ready[key] for key in identity}
    assert ready["protocol"] == PROTOCOL
    assert ready["diagnostic_only"] is True and ready["measurement_admission_eligible"] is False
    assert ready["operator"] == "exp" and ready["cycle_index"] == 0
    assert ready["repeat"] == 7300 and ready["execution_mode"] == "direct_enqueue"
    assert ready["mode"] == "confirmation" and ready["warmup_role_counts"] == {"baseline": 10, "candidate": 10}
    assert ready["role_symbols"] == {"baseline": "launch_baseline", "candidate": "launch_candidate"}
    assert ready["launches_per_operator"] == {"baseline": 1, "candidate": 1}
    assert ready["cpu_affinity"] == sorted(os.sched_getaffinity(0))
    assert ready["warmup_finished_monotonic_ns"] >= ready["warmup_started_monotonic_ns"]
    assert ready["buffers"]["inputs"][0]["address"] != ready["buffers"]["outputs"][0]["address"]
    primes = [message for message in messages if message["kind"] == "prime"]
    assert [prime["phase"] for prime in primes] == ["aa_before", "formal", "aa_after"]
    assert all(prime["prime_order"] == ["baseline", "candidate", "candidate", "baseline"] for prime in primes)
    pairs = [message for message in messages if message["kind"] == "pair"]
    assert len(pairs) == 15
    assert [(pair["phase"], pair["pair_index"]) for pair in pairs] == [
        (phase, index) for phase in ("aa_before", "formal", "aa_after") for index in range(5)
    ]
    samples = []
    for pair in pairs:
        order = ["baseline", "candidate"] if pair["pair_index"] % 2 == 0 else ["candidate", "baseline"]
        assert pair["order"] == order
        assert pair["started_monotonic_ns"] <= pair[order[0]]["started_monotonic_ns"]
        assert pair[order[0]]["finished_monotonic_ns"] <= pair[order[1]]["started_monotonic_ns"]
        assert pair[order[1]]["finished_monotonic_ns"] <= pair["finished_monotonic_ns"]
        for role in ("baseline", "candidate"):
            sample = pair[role]
            assert sample["implementation"] == (role if pair["phase"] == "formal" else "baseline")
            assert sample["launches_per_operator"] == 1
            assert sample["elapsed_ms"] == 1.0
            assert sample["elapsed_ns"] == pytest.approx(1e6 / 7300)
            assert sample["cpu_before"] in ready["cpu_affinity"]
            assert sample["cpu_after"] in ready["cpu_affinity"]
            check_observations(sample)
            samples.append(sample)
    assert len(samples) == 30
    assert sum(len(sample["submission_diagnostic"]["enqueue_checkpoints"]) for sample in samples) == 30 * 73
    assert complete["input_bytes_unchanged"] is True
    assert [item["role"] for item in complete["untimed_verifications"]] == ["baseline", "candidate"]
    assert all(item["scope"] == "untimed_callback_verification" for item in complete["untimed_verifications"])
    counters = json.loads(next(line[len("RESULT:"):] for line in result.stdout.splitlines()
                               if line.startswith("RESULT:")))
    assert counters == {"baseline_calls": 183511, "candidate_calls": 36711, "first_candidate_after": 10,
                        "input": 7, "snapshots": ["baseline:101", "candidate:202"], "stream_syncs": 11,
                        "event_syncs": 30, "record_events": 60, "pid": ready["pid"]}
    assert counters["baseline_calls"] + counters["candidate_calls"] == 220222


@pytest.mark.parametrize("overrides", [{"operator": "sigmoid"}, {"mode": "pilot"}, {"repeat": 100}])
def test_non_exp_pilot_or_short_repeat_rejected_before_ready(native, overrides):
    result, messages = run(native, **overrides)
    assert result.returncode == 2 and result.stderr
    assert messages == [] and "RESULT:" not in result.stdout


def test_input_mutation_cannot_emit_successful_complete(native):
    result, messages = run(native, mutate=True)
    assert result.returncode == 2 and "modified input bytes" in result.stderr
    assert len([message for message in messages if message["kind"] == "pair"]) == 15
    assert not any(message["kind"] == "complete" for message in messages)
