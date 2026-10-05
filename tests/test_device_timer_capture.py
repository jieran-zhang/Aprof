"""CPU-only compilation against ACL stubs; no SDK library or device is loaded."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]

ACL_STUB = r'''
#pragma once
#include <cstddef>
#include <cstdint>
using aclError = int;
using aclrtStream = void *;
using aclrtEvent = void *;
using aclmdlRI = void *;
enum aclmdlRICaptureMode {
    ACL_MODEL_RI_CAPTURE_MODE_GLOBAL = 0,
    ACL_MODEL_RI_CAPTURE_MODE_THREAD_LOCAL,
    ACL_MODEL_RI_CAPTURE_MODE_RELAXED,
};
constexpr int ACL_SUCCESS = 0;
constexpr int ACL_MEM_MALLOC_HUGE_FIRST = 0;
constexpr unsigned ACL_EVENT_TIME_LINE = 1;
aclError aclrtMalloc(void **, size_t, int);
aclError aclrtFree(void *);
aclError aclrtCreateEventWithFlag(aclrtEvent *, unsigned);
aclError aclrtDestroyEvent(aclrtEvent);
aclError aclrtSynchronizeStream(aclrtStream);
aclError aclrtRecordEvent(aclrtEvent, aclrtStream);
aclError aclrtSynchronizeEvent(aclrtEvent);
aclError aclrtEventElapsedTime(float *, aclrtEvent, aclrtEvent);
aclError aclmdlRICaptureBegin(aclrtStream, aclmdlRICaptureMode);
aclError aclmdlRICaptureEnd(aclrtStream, aclmdlRI *);
aclError aclmdlRIExecuteAsync(aclmdlRI, aclrtStream);
aclError aclmdlRIDestroy(aclmdlRI);
'''

PROGRAM = r'''
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include "device_timer.h"

std::vector<std::string> operations;
int launch_calls = 0, captured_calls = 0, begins = 0, ends = 0, replays = 0;
int models_destroyed = 0, events_created = 0, events_destroyed = 0, stream_syncs = 0;
bool capturing = false;
std::string failure = std::getenv("STUB_FAIL") ? std::getenv("STUB_FAIL") : "";
void note(const char *name) { operations.push_back(name); }
aclError aclrtMalloc(void **p, size_t bytes, int) { *p = std::malloc(bytes); return 0; }
aclError aclrtFree(void *p) { std::free(p); return 0; }
aclError aclrtCreateEventWithFlag(aclrtEvent *event, unsigned) {
    note("create_event");
    ++events_created;
    if (failure == "second_event" && events_created == 2) return 91;
    *event = reinterpret_cast<void *>(static_cast<uintptr_t>(events_created));
    return 0;
}
aclError aclrtDestroyEvent(aclrtEvent) { note("destroy_event"); ++events_destroyed; return 0; }
aclError aclrtSynchronizeStream(aclrtStream) { note("stream_sync"); ++stream_syncs; return 0; }
aclError aclrtRecordEvent(aclrtEvent event, aclrtStream) {
    bool start = event == reinterpret_cast<void *>(1);
    note(start ? "record_start" : "record_end");
    return failure == (start ? "record_start" : "record_end") ? 92 : 0;
}
aclError aclrtSynchronizeEvent(aclrtEvent) { note("event_sync"); return failure == "event_sync" ? 93 : 0; }
aclError aclrtEventElapsedTime(float *ms, aclrtEvent, aclrtEvent) {
    note("elapsed"); *ms = 2.0f; return failure == "elapsed" ? 94 : 0;
}
aclError aclmdlRICaptureBegin(aclrtStream, aclmdlRICaptureMode mode) {
    note("capture_begin"); ++begins;
    if (mode != ACL_MODEL_RI_CAPTURE_MODE_GLOBAL) throw std::runtime_error("wrong capture mode");
    if (failure == "begin") return 95;
    capturing = true; return 0;
}
aclError aclmdlRICaptureEnd(aclrtStream, aclmdlRI *model) {
    note("capture_end"); ++ends;
    if ((failure == "end" || failure == "end_with_handle") && ends == 1) {
        if (failure == "end_with_handle") *model = reinterpret_cast<void *>(1234);
        return 96;
    }
    capturing = false;
    *model = failure == "null_model" ? nullptr : reinterpret_cast<void *>(1234);
    return 0;
}
aclError aclmdlRIExecuteAsync(aclmdlRI model, aclrtStream) {
    note("replay"); ++replays;
    if (model != reinterpret_cast<void *>(1234) || capturing) throw std::runtime_error("invalid replay");
    return failure == "replay" ? 97 : 0;
}
aclError aclmdlRIDestroy(aclmdlRI model) {
    note("destroy_model"); ++models_destroyed;
    if (model != reinterpret_cast<void *>(1234)) throw std::runtime_error("invalid model cleanup");
    return 0;
}
int main() {
    int status = 0;
    try {
        aprof::Run(reinterpret_cast<void *>(99), 0, "foreach_norm", 3, [] {
            note("launch"); ++launch_calls;
            if (capturing) {
                ++captured_calls;
                if (failure == "launch") throw std::runtime_error("capture launch failed");
            }
            // A whole TensorList operator includes every partial and finalize.
            note("partial_1"); note("partial_2"); note("finalize");
        });
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n'; status = 2;
    }
    std::cout << "STUB_STATS:{\"launch_calls\":" << launch_calls
              << ",\"captured_calls\":" << captured_calls << ",\"begins\":" << begins
              << ",\"ends\":" << ends << ",\"replays\":" << replays
              << ",\"models_destroyed\":" << models_destroyed
              << ",\"events_created\":" << events_created << ",\"events_destroyed\":" << events_destroyed
              << ",\"stream_syncs\":" << stream_syncs << ",\"operations\":[";
    for (size_t i = 0; i < operations.size(); ++i) {
        if (i) std::cout << ',';
        std::cout << '"' << operations[i] << '"';
    }
    std::cout << "]}" << std::endl;
    return status;
}
'''


@pytest.fixture(scope='module')
def stub_binary(tmp_path_factory):
    compiler = shutil.which('c++') or shutil.which('g++')
    if not compiler:
        pytest.skip('a host C++ compiler is required for the ACL stub test')
    directory = tmp_path_factory.mktemp('device-timer-acl-stub')
    (directory / 'acl').mkdir()
    (directory / 'acl/acl.h').write_text(ACL_STUB)
    (directory / 'stub.cpp').write_text(PROGRAM)
    binary = directory / 'stub'
    subprocess.run([
        compiler, '-std=c++14', '-Wall', '-Wextra', '-Werror',
        '-I', str(directory), '-I', str(ROOT / 'benchmarks/cannbench/harness'),
        str(directory / 'stub.cpp'), '-o', str(binary),
    ], check=True, capture_output=True, text=True, timeout=30)
    return binary


def run_stub(binary, *, capture='1', failure=None, interactive=False, timing=True):
    env = {key: value for key, value in os.environ.items() if not key.startswith('APROF_') and key != 'STUB_FAIL'}
    if timing:
        env['APROF_TIMING_INTERACTIVE' if interactive else 'APROF_TIMING'] = '1'
    env['APROF_SAMPLES'] = '2'
    if capture is not None:
        env['APROF_CAPTURE_REPLAY'] = capture
    if failure:
        env['STUB_FAIL'] = failure
    result = subprocess.run([str(binary)], env=env, input='sample\nsample\nquit\n' if interactive else '',
                            capture_output=True, text=True, timeout=10)
    samples = [json.loads(line.removeprefix('APROF_TIMING_JSON:')) for line in result.stdout.splitlines()
               if line.startswith('APROF_TIMING_JSON:')]
    stats = next(json.loads(line.removeprefix('STUB_STATS:')) for line in result.stdout.splitlines()
                 if line.startswith('STUB_STATS:'))
    return result, samples, stats


@pytest.mark.parametrize('capture', [None, '0'])
def test_default_direct_path_keeps_legacy_sample_schema_and_launch_count(stub_binary, capture):
    result, samples, stats = run_stub(stub_binary, capture=capture)
    assert result.returncode == 0, result.stderr
    expected = [{
        'schema_version': '1.0.0', 'operator': 'foreach_norm', 'device': 0,
        'source': 'acl_event', 'unit': 'ns', 'sample_index': index,
        'warmup': 10, 'repeat': 100, 'launches_per_operator': 3, 'elapsed_ns': 20000,
    } for index in range(2)]
    assert samples == expected
    assert stats['launch_calls'] == 210
    assert stats['begins'] == stats['ends'] == stats['replays'] == stats['models_destroyed'] == 0
    assert stats['events_destroyed'] == 2


@pytest.mark.parametrize('interactive', [False, True])
def test_capture_once_includes_every_operator_launch_and_replays_once_per_sample(stub_binary, interactive):
    result, samples, stats = run_stub(stub_binary, interactive=interactive)
    assert result.returncode == 0, result.stderr
    assert len(samples) == 2
    assert stats['launch_calls'] == 110 and stats['captured_calls'] == 100
    assert stats['begins'] == stats['ends'] == stats['models_destroyed'] == 1
    assert stats['replays'] == 2 and stats['events_destroyed'] == 2
    for index, sample in enumerate(samples):
        assert sample['sample_index'] == index
        assert sample['execution_mode'] == 'acl_graph_replay'
        assert sample['captured_operator_calls'] == sample['repeat'] == 100
        assert sample['launches_per_operator'] == 3
        assert sample['elapsed_ns'] == 20000
    operations = stats['operations']
    begin, end = operations.index('capture_begin'), operations.index('capture_end')
    assert operations[:begin].count('launch') == 10
    assert operations.index('stream_sync') < begin
    assert operations[begin + 1:end] == ['launch', 'partial_1', 'partial_2', 'finalize'] * 100
    assert end < operations.index('record_start')
    for index, value in enumerate(operations):
        if value == 'record_start':
            assert operations[index:index + 6] == ['record_start', 'replay', 'record_end', 'event_sync', 'elapsed',
                                                  'record_start' if index == operations.index('record_start') else 'destroy_model']
    assert operations[-3:] == ['destroy_model', 'destroy_event', 'destroy_event']
    assert ('APROF_TIMING_READY\n' in result.stdout) == interactive


@pytest.mark.parametrize('failure,ends,models', [
    ('begin', 0, 0), ('launch', 1, 1), ('end', 2, 1), ('end_with_handle', 2, 1), ('null_model', 1, 0),
])
def test_capture_errors_fail_without_fallback_and_clean_resources(stub_binary, failure, ends, models):
    result, samples, stats = run_stub(stub_binary, failure=failure)
    assert result.returncode == 2 and result.stderr
    assert samples == [] and stats['replays'] == 0
    assert stats['ends'] == ends and stats['models_destroyed'] == models
    assert stats['events_destroyed'] == 2
    assert stats['launch_calls'] <= 110


@pytest.mark.parametrize('failure,stream_syncs', [
    ('record_start', 1), ('replay', 2), ('record_end', 2), ('event_sync', 2), ('elapsed', 1),
])
def test_sample_errors_drain_submitted_replay_before_destroying_model_and_events(stub_binary, failure, stream_syncs):
    result, samples, stats = run_stub(stub_binary, failure=failure)
    assert result.returncode == 2 and result.stderr
    assert samples == []
    assert stats['models_destroyed'] == 1 and stats['events_destroyed'] == 2
    assert stats['stream_syncs'] == stream_syncs
    assert stats['operations'][-3:] == ['destroy_model', 'destroy_event', 'destroy_event']
    if stream_syncs == 2:
        assert stats['operations'][-4] == 'stream_sync'


def test_event_allocation_failure_releases_the_first_event(stub_binary):
    result, samples, stats = run_stub(stub_binary, failure='second_event')
    assert result.returncode == 2
    assert samples == [] and stats['events_destroyed'] == 1 and stats['begins'] == 0


def test_capture_flag_alone_preserves_untimed_single_execution(stub_binary):
    result, samples, stats = run_stub(stub_binary, timing=False)
    assert result.returncode == 0
    assert samples == [] and stats['launch_calls'] == 1
    assert stats['begins'] == stats['events_created'] == 0


def test_invalid_capture_setting_cannot_silently_fall_back(stub_binary):
    result, samples, stats = run_stub(stub_binary, capture='2')
    assert result.returncode == 2 and 'APROF_CAPTURE_REPLAY' in result.stderr
    assert samples == [] and stats['launch_calls'] == 0
