"""CPU-only lifecycle and unchanged-callback checks; no CANN library is loaded."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

import test_device_shared_timing_header as shared


ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT / "scaffolding/benchmarks/cannbench/harness/device_task_profile.h"
SCRIPTS = ROOT / "scaffolding/collection/scripts"
sys.path.insert(0, str(SCRIPTS))
import task_profile_native as adapter


FAKE_PROFILE = r'''
#pragma once
#include "acl.h"
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <vector>
struct aclprofConfig {};
struct aclprofAicoreEvents {};
enum aclprofAicoreMetrics { ACL_AICORE_NONE=0xFF };
constexpr uint64_t ACL_PROF_TASK_TIME=2;
inline std::vector<std::string> calls;
inline aclprofConfig configuration;
inline int status(const char* operation) {
 calls.emplace_back(operation);
 const char* failure=std::getenv("FAKE_PROFILE_FAILURE");
 return failure && std::string(failure).find(operation)!=std::string::npos ? 7 : 0;
}
inline aclError aclprofInit(const char* path,size_t size) {
 if (std::string(path).size()!=size) throw std::runtime_error("bad init length");
 return status("init");
}
inline aclprofConfig* aclprofCreateConfig(uint32_t* devices,uint32_t count,
 aclprofAicoreMetrics metrics,const aclprofAicoreEvents* events,uint64_t flags) {
 if(!devices || *devices!=0 || count!=1 || metrics!=ACL_AICORE_NONE || events || flags!=ACL_PROF_TASK_TIME)
  throw std::runtime_error("not task-only profiling");
 return status("create") ? nullptr : &configuration;
}
inline aclError aclprofStart(const aclprofConfig* p) {
 if(p!=&configuration) throw std::runtime_error("bad configuration");
 return status("start");
}
inline aclError aclprofStop(const aclprofConfig*) { return status("stop"); }
inline aclError aclprofDestroyConfig(const aclprofConfig*) { return status("destroy"); }
inline aclError aclprofFinalize() { return status("finalize"); }
'''

PROGRAM = r'''
#include "device_task_profile.h"
#include "device_shared_timing.h"
int main() {
 int result=0, input=7, output=0, a=0, b=0;
 std::vector<std::string> snapshots;
 try {
  calls.emplace_back("aclInit");
  aprof::TaskProfile profile;
  aprof::SharedBuffers buffers{{{"x",&input,sizeof(input)}},{{"y",&output,sizeof(output)}},{}};
  auto baseline=[&](aclrtStream,const aprof::SharedBuffers&) {
   if(std::getenv("FAKE_WORK_FAILURE")) throw std::runtime_error("original callback failed");
   ++a; output=101;
  };
  auto candidate=[&](aclrtStream,const aprof::SharedBuffers&) { ++b; output=202; };
  auto snapshot=[&](const char* role,aclrtStream,const aprof::SharedBuffers&) {
   snapshots.push_back(std::string(role)+":"+std::to_string(output));
  };
  profile.Start(0);
  aprof::RunShared(reinterpret_cast<void*>(0x2345),"fake_cpu_only",0,1,1,
   buffers,{"launch_baseline","launch_candidate"},baseline,candidate,snapshot);
  profile.Finish();
 } catch(const std::exception& e) { std::cerr << e.what() << '\n'; result=2; }
 calls.emplace_back("aclFinalize");
 std::cout << "RESULT:{\"calls\":[";
 for(size_t i=0;i<calls.size();++i) std::cout << (i?",":"") << '"' << calls[i] << '"';
 std::cout << "],\"baseline_calls\":" << a << ",\"candidate_calls\":" << b << ",\"snapshots\":[";
 for(size_t i=0;i<snapshots.size();++i) std::cout << (i?",":"") << '"' << snapshots[i] << '"';
 std::cout << "]}" << '\n';
 return result;
}
'''


@pytest.fixture(scope="module")
def executable(tmp_path_factory):
    compiler = shutil.which("g++")
    if compiler is None:
        pytest.skip("C++ compiler is required for the CPU lifecycle test")
    directory = tmp_path_factory.mktemp("native-task-profile-fake-acl")
    (directory / "acl").mkdir()
    (directory / "acl/acl.h").write_text(shared.FAKE_ACL)
    (directory / "acl/acl_prof.h").write_text(FAKE_PROFILE)
    (directory / "main.cpp").write_text(PROGRAM)
    binary = directory / "test"
    subprocess.run([compiler, "-std=c++17", "-O2", "-I", str(directory), "-I", str(HEADER.parent),
                    "-I", str(shared.HEADER.parent), str(directory / "main.cpp"), "-o", str(binary)],
                   check=True, capture_output=True, text=True)
    return binary


def run(executable, directory=None, *, failure=None, work_failure=False):
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("APROF_", "FAKE_"))}
    environment.update(APROF_SHARED_MODE="confirmation", APROF_SHARED_REPEAT="100")
    if directory is not None:
        environment["APROF_TASK_PROFILE_DIR"] = str(directory)
    if failure:
        environment["FAKE_PROFILE_FAILURE"] = failure
    if work_failure:
        environment["FAKE_WORK_FAILURE"] = "1"
    process = subprocess.run([str(executable)], input=shared.commands(), capture_output=True,
                             text=True, timeout=10, env=environment)
    receipt = json.loads(next(line.removeprefix("RESULT:") for line in process.stdout.splitlines()
                             if line.startswith("RESULT:")))
    messages = [json.loads(line.removeprefix(shared.PREFIX)) for line in process.stdout.splitlines()
                if line.startswith(shared.PREFIX)]
    return process, receipt, messages


@pytest.mark.parametrize("enabled", [False, True])
def test_full_cycle_same_tasks_and_protocol_with_optional_profile(executable, tmp_path, enabled):
    process, receipt, messages = run(executable, tmp_path if enabled else None)
    assert process.returncode == 0, process.stderr
    expected = ["init", "create", "start", "stop", "destroy", "finalize"] if enabled else []
    assert receipt["calls"] == ["aclInit", *expected, "aclFinalize"]
    assert receipt["baseline_calls"] == 3511 and receipt["candidate_calls"] == 711
    assert receipt["snapshots"] == ["baseline:101", "candidate:202"]
    assert len(messages) == 20 and messages[-1]["kind"] == "complete"
    assert [row["command_index"] for row in messages[1:]] == list(range(19))
    assert len([row for row in messages if row["kind"] == "pair"]) == 15
    assert messages[-1]["input_bytes_unchanged"] is True


@pytest.mark.parametrize(("failure", "calls"), [
    ("init", ["init"]),
    ("create", ["init", "create", "finalize"]),
    ("start", ["init", "create", "start", "destroy", "finalize"]),
    ("stop", ["init", "create", "start", "stop", "destroy", "finalize"]),
    ("destroy", ["init", "create", "start", "stop", "destroy", "finalize"]),
    ("finalize", ["init", "create", "start", "stop", "destroy", "finalize"]),
    ("stop,destroy,finalize", ["init", "create", "start", "stop", "destroy", "finalize"]),
])
def test_api_failure_is_terminal_and_remaining_cleanup_runs(executable, tmp_path, failure, calls):
    process, receipt, _ = run(executable, tmp_path, failure=failure)
    assert process.returncode == 2 and process.stderr
    assert receipt["calls"] == ["aclInit", *calls, "aclFinalize"]


def test_callback_exception_keeps_original_failure_and_cleans_profile(executable, tmp_path):
    process, receipt, _ = run(executable, tmp_path, work_failure=True, failure="stop")
    assert process.returncode == 2
    assert "original callback failed" in process.stderr and "aclprofStop cleanup failed" in process.stderr
    assert receipt["calls"] == ["aclInit", "init", "create", "start", "stop", "destroy", "finalize", "aclFinalize"]


@pytest.mark.parametrize("kind", ["empty", "relative", "missing", "file", "nonempty", "symlink"])
def test_invalid_present_output_directory_never_initializes_profiler(executable, tmp_path, kind):
    directory = tmp_path / "profile"
    if kind == "empty":
        directory = ""
    elif kind == "relative":
        directory = "relative-profile"
    elif kind == "file":
        directory.write_text("file")
    elif kind == "nonempty":
        directory.mkdir()
        (directory / "old-evidence").write_text("preserve")
    elif kind == "symlink":
        directory.symlink_to(tmp_path, target_is_directory=True)
    process, receipt, messages = run(executable, directory)
    assert process.returncode == 2 and "APROF_TASK_PROFILE_DIR" in process.stderr
    assert receipt["calls"] == ["aclInit", "aclFinalize"] and messages == []


def original_source(tmp_path, operator):
    source = tmp_path / "original"
    (source / "op_host").mkdir(parents=True)
    (source / "op_kernel").mkdir()
    (source / "scripts").mkdir()
    (source / "op_host" / f"{operator}.asc").write_text(
        '#include "device_shared_timing.h"\n'
        '        Check(aclInit(nullptr), "aclInit");\n'
        f'        aprof::RunShared(stream, "{operator}", cycle_text[0] - \'0\', 1, 1, buffers,\n'
        '                         {"launch_baseline", "launch_candidate"}, launch_baseline, launch_candidate, snapshot);\n')
    (source / "CMakeLists.txt").write_text(
        f"target_link_libraries({operator} PRIVATE tiling_api register platform unified_dlog "
        "dl m graph_base ascendcl ascendc_runtime)\n")
    (source / "op_host/device_shared_timing.h").write_bytes(b"frozen shared timer\n")
    (source / "op_host/tiling.h").write_bytes(b"frozen tiling\n")
    (source / "op_kernel/kernel.h").write_bytes(b"frozen kernel\n")
    (source / "scripts/verify_result.py").write_bytes(b"# frozen original math\n")
    return source


@pytest.mark.parametrize("operator", ["exp", "sigmoid"])
def test_mechanical_adapter_preserves_all_other_source_bytes(tmp_path, operator):
    source = original_source(tmp_path, operator)
    before = adapter.source_files(source)
    output = tmp_path / "adapted"
    proof = adapter.prepare(source, output, operator)
    assert adapter.source_files(source) == before
    assert proof["original_files"] == before
    assert set(proof["patches"]) == {"CMakeLists.txt", f"op_host/{operator}.asc"}
    assert set(proof["new_files"]) == {"op_host/device_task_profile.h"}
    for relative in proof["unchanged_files"]:
        assert (source / relative).read_bytes() == (output / "source" / relative).read_bytes()
    host = (output / "source/op_host" / f"{operator}.asc").read_text()
    original_call = (source / "op_host" / f"{operator}.asc").read_text().split("        aprof::RunShared")[1]
    assert "        aprof::RunShared" + original_call in host
    assert host.index("task_profile.Start") < host.index("aprof::RunShared") < host.index("task_profile.Finish")
    with pytest.raises(FileExistsError):
        adapter.prepare(source, output, operator)
    with pytest.raises(ValueError, match="already contains"):
        adapter.adapt_host(host, operator)


def test_mechanical_adapter_rejects_ambiguous_call_anchor(tmp_path):
    source = original_source(tmp_path, "exp")
    text = (source / "op_host/exp.asc").read_text()
    with pytest.raises(ValueError, match="anchor must occur exactly once"):
        adapter.adapt_host(text + text, "exp")
