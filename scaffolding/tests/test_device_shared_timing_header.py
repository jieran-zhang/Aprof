"""CPU-only protocol tests compiling the real header against a fake ACL.

No NPU or CANN runtime is loaded. These tests cannot qualify the measurement
method; they only check callback counts, state transitions and native receipts.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT / 'skill-libs/graph-base/0.5.1/skills/ascendc-aprof-profiling/assets/device_shared_timing.h'
PREFIX = 'APROF_SHARED_TIMING_JSON:'
FAKE_ACL = r"""
#pragma once
#include <cstring>
using aclError = int;
using aclrtContext = void*;
using aclrtStream = void*;
struct FakeEvent {};
using aclrtEvent = FakeEvent*;
constexpr int ACL_SUCCESS=0, ACL_EVENT_TIME_LINE=1, ACL_MEMCPY_DEVICE_TO_HOST=2;
inline int fake_stream_syncs=0, fake_event_syncs=0, fake_records=0;
inline int aclrtGetCurrentContext(aclrtContext* p) { *p=reinterpret_cast<void*>(0x1234); return 0; }
inline int aclrtGetDevice(int* p) { *p=0; return 0; }
inline int aclrtCreateEventWithFlag(aclrtEvent* p,int) { *p=new FakeEvent; return 0; }
inline int aclrtDestroyEvent(aclrtEvent p) { delete p; return 0; }
inline int aclrtSynchronizeStream(aclrtStream) { ++fake_stream_syncs; return 0; }
inline int aclrtRecordEvent(aclrtEvent,aclrtStream) { ++fake_records; return 0; }
inline int aclrtSynchronizeEvent(aclrtEvent) { ++fake_event_syncs; return 0; }
inline int aclrtEventElapsedTime(float* p,aclrtEvent,aclrtEvent) { *p=1.0f; return 0; }
inline int aclrtMemcpy(void* out,size_t cap,const void* in,size_t n,int) {
 if (n>cap) return 1; std::memcpy(out,in,n); return 0;
}
"""
PROGRAM = r"""
#include "device_shared_timing.h"
int main(int argc,char** argv) {
 int input=7, output=0, a=0, b=0, first_candidate_after=-1;
 const bool mutate=argc>2;
 std::vector<std::string> snapshots;
 aprof::SharedBuffers buffers{{{"x",&input,sizeof(input)}},{{"y",&output,sizeof(output)}},{}};
 auto baseline=[&](aclrtStream,const aprof::SharedBuffers& shared) {
  ++a; *static_cast<int*>(shared.outputs[0].data)=101;
 };
 auto candidate=[&](aclrtStream,const aprof::SharedBuffers& shared) {
  if (first_candidate_after < 0) first_candidate_after=a;
  ++b; *static_cast<int*>(shared.outputs[0].data)=202;
  if(mutate) *static_cast<int*>(shared.inputs[0].data)=9;
 };
 auto snapshot=[&](const char* role,aclrtStream,const aprof::SharedBuffers& shared) {
  snapshots.push_back(std::string(role)+":"+std::to_string(*static_cast<int*>(shared.outputs[0].data)));
 };
 try {
  aprof::RunShared(reinterpret_cast<void*>(0x2345),"fake_cpu_only",std::stoi(argv[1]),1,2,
    buffers,{"launch_baseline","launch_candidate"},baseline,candidate,snapshot);
  std::cout << "RESULT:{\"baseline_calls\":" << a << ",\"candidate_calls\":" << b
   << ",\"first_candidate_after\":" << first_candidate_after << ",\"input\":" << input << ",\"snapshots\":[\"" << snapshots.at(0) << "\",\"" << snapshots.at(1)
   << "\"],\"stream_syncs\":" << fake_stream_syncs << ",\"event_syncs\":" << fake_event_syncs
   << ",\"record_events\":" << fake_records << ",\"pid\":" << getpid() << "}" << std::endl;
  return 0;
 } catch(const std::exception& e) { std::cerr << e.what() << std::endl; return 2; }
}
"""


@pytest.fixture(scope='module')
def executable(tmp_path_factory):
    compiler = shutil.which('g++')
    if compiler is None:
        pytest.skip('a C++ compiler is required for the fake ACL protocol test')
    directory = tmp_path_factory.mktemp('shared-header-fake-acl')
    (directory / 'acl').mkdir()
    (directory / 'acl/acl.h').write_text(FAKE_ACL)
    (directory / 'main.cpp').write_text(PROGRAM)
    binary = directory / 'test'
    subprocess.run([compiler, '-std=c++17', '-O2', '-I', str(directory), '-I', str(HEADER.parent),
                    str(directory / 'main.cpp'), '-o', str(binary)],
                   check=True, capture_output=True, text=True)
    return binary


def commands():
    rows = []
    index = 0
    for phase in ('aa_before', 'formal', 'aa_after'):
        rows.append(f'prime {index} {phase}')
        index += 1
        for pair in range(5):
            rows.append(f'pair {index} {phase} {pair}')
            index += 1
    rows.append(f'finish {index}')
    return '\n'.join(rows) + '\n'


def run(executable, cycle=0, *, text=None, mutate=False, command_file=None, mode="confirmation", repeat=100):
    env = {k: v for k, v in os.environ.items() if not k.startswith('APROF_SHARED_')}
    if mode is not None:
        env['APROF_SHARED_MODE'] = mode
    if repeat is not None:
        env['APROF_SHARED_REPEAT'] = str(repeat)
    if command_file is not None:
        env['APROF_SHARED_COMMANDS'] = str(command_file)
    result = subprocess.run([str(executable), str(cycle)] + (['mutate'] if mutate else []),
                            input=commands() if text is None else text, capture_output=True, text=True, timeout=10, env=env)
    messages = [json.loads(line[len(PREFIX):]) for line in result.stdout.splitlines() if line.startswith(PREFIX)]
    return result, messages


@pytest.mark.parametrize('cycle', range(6))
def test_complete_cycle_dispatch_counts_same_buffers_and_untimed_outputs(executable, cycle):
    result, messages = run(executable, cycle)
    assert result.returncode == 0, result.stderr
    assert len(messages) == 20
    ready, complete = messages[0], messages[-1]
    assert ready['kind'] == 'ready' and complete['kind'] == 'complete'
    assert ready['cpu_affinity'] == sorted(os.sched_getaffinity(0))
    assert ready['warmup_finished_monotonic_ns'] >= ready['warmup_started_monotonic_ns']
    identity = ('schema_version', 'protocol', 'operator', 'cycle_index', 'pid', 'device', 'context_address',
                'stream_address', 'buffers', 'warmup', 'repeat', 'prime_repeat', 'execution_mode',
                'role_symbols', 'launches_per_operator', 'mode', 'warmup_role_counts')
    for message in messages:
        assert {key: message[key] for key in identity} == {key: ready[key] for key in identity}
    assert [item['command_index'] for item in messages[1:]] == list(range(19))
    assert ready['role_symbols'] == {'baseline': 'launch_baseline', 'candidate': 'launch_candidate'}
    assert ready['buffers']['workspaces'] == []
    assert ready['buffers']['inputs'][0]['address'] != ready['buffers']['outputs'][0]['address']
    primes = [item for item in messages if item['kind'] == 'prime']
    expected_prime = ['baseline', 'candidate', 'candidate', 'baseline']
    if cycle % 2:
        expected_prime = ['candidate', 'baseline', 'baseline', 'candidate']
    assert len(primes) == 3 and all(row['prime_order'] == expected_prime for row in primes)
    pairs = [item for item in messages if item['kind'] == 'pair']
    assert len(pairs) == 15
    for pair in pairs:
        expected_order = ['baseline', 'candidate']
        if (cycle + pair['pair_index']) % 2:
            expected_order.reverse()
        assert pair['order'] == expected_order
        assert pair['started_monotonic_ns'] <= pair[expected_order[0]]['started_monotonic_ns']
        assert pair[expected_order[0]]['finished_monotonic_ns'] <= pair[expected_order[1]]['started_monotonic_ns']
        assert pair[expected_order[1]]['finished_monotonic_ns'] <= pair['finished_monotonic_ns']
        for role in ('baseline', 'candidate'):
            sample = pair[role]
            implementation = role if pair['phase'] == 'formal' else 'baseline'
            assert sample['implementation'] == implementation
            assert sample['launches_per_operator'] == (2 if implementation == 'candidate' else 1)
            assert sample['elapsed_ms'] == 1 and sample['elapsed_ns'] == 10000
            assert sample['cpu_before'] in ready['cpu_affinity'] and sample['cpu_after'] in ready['cpu_affinity']
    assert complete['input_bytes_unchanged'] is True
    assert [item['role'] for item in complete['untimed_verifications']] == ['baseline', 'candidate']
    assert all(item['scope'] == 'untimed_callback_verification' for item in complete['untimed_verifications'])
    counters = json.loads(next(line[len('RESULT:'):] for line in result.stdout.splitlines() if line.startswith('RESULT:')))
    assert counters == {'baseline_calls': 3511, 'candidate_calls': 711, 'first_candidate_after': 0 if cycle % 2 else 10, 'input': 7,
                        'snapshots': ['baseline:101', 'candidate:202'], 'stream_syncs': 11,
                        'event_syncs': 30, 'record_events': 60, 'pid': ready['pid']}


def test_modified_input_cannot_emit_a_successful_complete_receipt(executable):
    result, messages = run(executable, mutate=True)
    assert result.returncode == 2 and 'modified input bytes' in result.stderr
    assert len([row for row in messages if row['kind'] == 'pair']) == 15
    assert not any(row['kind'] == 'complete' for row in messages)


def test_explicit_file_runs_identical_protocol_without_stdin(executable, tmp_path):
    path = tmp_path / 'commands.txt'
    path.write_text(commands())
    result, messages = run(executable, text='', command_file=path)
    assert result.returncode == 0, result.stderr
    assert len(messages) == 20 and messages[-1]['kind'] == 'complete'
    assert [item['command_index'] for item in messages[1:]] == list(range(19))
    counts = json.loads(next(line[len('RESULT:'):] for line in result.stdout.splitlines() if line.startswith('RESULT:')))
    assert counts['baseline_calls'] == 3511 and counts['candidate_calls'] == 711
    assert counts['snapshots'] == ['baseline:101', 'candidate:202']


@pytest.mark.parametrize('contents', [None, '', 'prime 0 formal\n'])
def test_bad_explicit_command_file_never_falls_back_to_stdin(executable, tmp_path, contents):
    path = tmp_path / 'commands.txt'
    if contents is not None:
        path.write_text(contents)
    result, messages = run(executable, text=commands(), command_file=path)
    assert result.returncode == 2
    assert not any(row['kind'] == 'complete' for row in messages)


@pytest.mark.parametrize('text,reason', [
    ('prime 0 aa_before\npair 0 aa_before 0\n', 'command index'),
    ('prime 0 formal\n', 'phase differs'),
    ('prime 0 aa_before\npair 1 aa_before 0\n', 'ended before finish'),
    ('finish 0\n', 'incomplete cycle'),
])
def test_repeated_or_missing_protocol_steps_are_rejected(executable, text, reason):
    result, messages = run(executable, text=text)
    assert result.returncode == 2 and reason in result.stderr
    assert not any(row['kind'] == 'complete' for row in messages)


def pilot_commands():
    return "prime 0 pilot\nsample 1 pilot 0\nsample 2 pilot 1\nsample 3 pilot 2\nfinish 4\n"


def test_pilot_only_uses_baseline_until_separate_untimed_candidate_snapshot(executable):
    result, messages = run(executable, mode="pilot", text=pilot_commands())
    assert result.returncode == 0, result.stderr
    assert len(messages) == 6
    assert [m["kind"] for m in messages] == ["ready", "prime", "pilot_sample", "pilot_sample", "pilot_sample", "complete"]
    assert all(m["mode"] == "pilot" and m["repeat"] == 100 and m["warmup_role_counts"] == {"baseline": 20, "candidate": 0} for m in messages)
    assert messages[1]["prime_order"] == ["baseline"] * 4
    assert [m["sample_index"] for m in messages[2:5]] == [0, 1, 2]
    assert all(m["baseline"]["implementation"] == "baseline" for m in messages[2:5])
    assert messages[-1]["pilot_samples"] == 3
    counts = json.loads(next(line[len("RESULT:"):] for line in result.stdout.splitlines() if line.startswith("RESULT:")))
    assert counts["baseline_calls"] == 721 and counts["candidate_calls"] == 1
    assert counts["first_candidate_after"] == 721
    assert counts["snapshots"] == ["baseline:101", "candidate:202"]
    assert counts["event_syncs"] == 3 and counts["record_events"] == 6


@pytest.mark.parametrize("repeat", [200, 7900, 100000])
def test_confirmation_uses_one_frozen_repeat_for_both_roles_all_phases(executable, repeat):
    result, messages = run(executable, repeat=repeat)
    assert result.returncode == 0, result.stderr
    assert all(m["mode"] == "confirmation" and m["repeat"] == repeat and m["warmup_role_counts"] == {"baseline": 10, "candidate": 10} for m in messages)
    pairs = [m for m in messages if m["kind"] == "pair"]
    assert all(m[r]["elapsed_ns"] == 1e6 / repeat for m in pairs for r in ("baseline", "candidate"))
    counts = json.loads(next(line[len("RESULT:"):] for line in result.stdout.splitlines() if line.startswith("RESULT:")))
    assert counts["baseline_calls"] == 1011 + 25 * repeat
    assert counts["candidate_calls"] == 211 + 5 * repeat


@pytest.mark.parametrize("mode,repeat,cycle", [(None,100,0),("confirmation",None,0),("bad",100,0),("pilot",200,0),("pilot",100,1),("confirmation",0,0),("confirmation",101,0),("confirmation",100100,0)])
def test_missing_or_out_of_bounds_calibration_environment_rejected(executable, mode, repeat, cycle):
    result, messages = run(executable, mode=mode, repeat=repeat, cycle=cycle)
    assert result.returncode == 2 and not messages


@pytest.mark.parametrize("text", ["sample 0 pilot 0\n", "prime 0 pilot\nsample 1 pilot 1\n", "prime 0 pilot\nfinish 1\n"])
def test_pilot_cannot_skip_duplicate_or_reorder_samples(executable, text):
    result, messages = run(executable, mode="pilot", text=text)
    assert result.returncode == 2 and not any(m["kind"] == "complete" for m in messages)
