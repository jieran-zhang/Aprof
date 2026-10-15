import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time

import pytest
from aprof_runtime.store import EpisodeStore


REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "skill-libs/graph-base/0.5.1/skills/ascendc-aprof-profiling/scripts/persistent_oracle.py"
SPEC = importlib.util.spec_from_file_location("tested_persistent_oracle", SOURCE)
oracle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oracle)


class Files:
    def __init__(self, directory):
        self.directory = directory
        directory.mkdir()

    def register_artifact(self, path):
        reference = oracle.digest(path)
        destination = self.directory / reference[7:]
        if not destination.exists():
            shutil.copyfile(path, destination)
        return reference

    def register_artifacts(self, paths):
        return tuple(self.register_artifact(path) for path in paths)

    def value(self, reference):
        return json.loads((self.directory / reference[7:]).read_text())


SCRIPT = '''import argparse,json,os,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output');p.add_argument('--result');p.add_argument('--behavior');a=p.parse_args()
if a.behavior=='sleep': time.sleep(30)
if a.behavior=='crash': os._exit(9)
if a.behavior=='exception': raise RuntimeError('oracle exception')
if a.behavior=='modify': Path(a.output).write_bytes(b'changed')
if a.behavior=='source': Path(__file__).write_text('# modified')
if a.behavior=='str_exit': raise SystemExit('not success')
count=globals().get('count',0)+1
result={'passed':Path(a.output).read_bytes()==b'good','counter':count,'pid':os.getpid(),'leaked_environment':os.environ.get('ORACLE_TEST_LEAK'),'cwd':os.getcwd()}
if a.behavior=='no_result': print(json.dumps(result));raise SystemExit(0)
Path(a.result).write_text(json.dumps(result))
print(json.dumps(dict(result, passed=False) if a.behavior=='mismatch' else result))
os.write(2,b'actual stderr\\n')
os.environ['ORACLE_TEST_LEAK']='should not persist';os.chdir('/');sys.path.append('/not-persistent');sys.argv.append('not-persistent')
raise SystemExit(0 if result['passed'] else 1)
'''


def plan(tmp_path, behaviors=("pass", "pass")):
    script = tmp_path / "verify.py"
    script.write_text(SCRIPT)
    prepared = tmp_path / "metadata.json"
    prepared.write_text('{"immutable": true}')
    requests = []
    for index, behavior in enumerate(behaviors):
        directory = tmp_path / f"request-{index}"
        directory.mkdir()
        output = directory / "output.bin"
        output.write_bytes(b"good")
        result = directory / "result.json"
        requests.append({"request_index": index, "stage": "calibration" if index < 2 else "confirmation",
                         "case_id": 1, "cycle": None if index < 2 else (index - 2) // 2,
                         "role": "baseline" if index % 2 == 0 else "candidate",
                         "argv": [str(Path(sys.executable).resolve()), str(script), "--output", str(output),
                                  "--result", str(result), "--behavior", behavior],
                         "cwd": str(tmp_path), "script_ref": oracle.digest(script),
                         "prepared_refs": {str(prepared): oracle.digest(prepared)}, "output_paths": [str(output)],
                         "result_path": str(result), "log_path": str(directory / "stdout.log"),
                         "stderr_path": str(directory / "stderr.log")})
    return {"schema_version": 1, "protocol": oracle.PROTOCOL, "run_id": "test-run", "session_id": "test-session", "requests": requests}


def start(tmp_path, value, seconds=10):
    store = Files(tmp_path / "cas")
    worker = oracle.PersistentOracle(value, directory=tmp_path / "worker", store=store, deadline=time.monotonic() + seconds)
    return worker.start(), store


def test_same_pid_fresh_namespace_state_restoration_and_exact_cas_transcript(tmp_path):
    value = plan(tmp_path, ("pass",) * 4)
    worker, store = start(tmp_path, value)
    try:
        receipts = [worker.verify(i) for i in range(4)]
        reference = worker.finish()
    finally:
        worker.finish(abort=True)
    report = store.value(reference)
    assert report["status"] == "complete" and report["exit_status"] == 0
    assert worker.finish() == reference
    assert report["worker_source_ref"] == oracle.digest(SOURCE)
    assert report["request_plan_ref"] == oracle.digest(tmp_path / "worker/request-plan.json")
    events = store.value(report["transcript_ref"])["events"]
    assert len(events) == 11
    assert [e["message"]["kind"] for e in events] == ["ready", "verify", "result", "verify", "result", "verify", "result", "verify", "result", "close", "closed"]
    assert report["request_refs"] == [r["request_ref"] for r in receipts]
    for item, receipt in zip(value["requests"], receipts):
        response = store.value(receipt["request_ref"])
        result = store.value(receipt["result_ref"])
        assert result["pid"] == report["pid"]
        assert result["counter"] == 1 and result["leaked_environment"] is None
        assert result["cwd"] == str(tmp_path)
        assert receipt["started_at"] <= response["started_at"] <= response["finished_at"] <= receipt["finished_at"]
        assert response["state_restored"] is True
        assert receipt["log_path"] == item["log_path"]
        assert receipt["log_hash"] == receipt["log_ref"] == oracle.digest(item["log_path"])
        assert Path(item["stderr_path"]).read_text() == "actual stderr\n"
        assert receipt["output_refs"] == response["output_refs_before"] == response["output_refs_after"]


@pytest.mark.parametrize("behavior", ["exception", "modify", "source", "str_exit", "no_result", "mismatch", "crash"])
def test_failed_oracle_retains_failure_and_forbids_followup(tmp_path, behavior):
    worker, store = start(tmp_path, plan(tmp_path, (behavior, "pass")))
    with pytest.raises((ValueError, RuntimeError, OSError)):
        worker.verify(0)
    assert worker.last_receipt["error"]
    with pytest.raises(ValueError, match="not available"):
        worker.verify(1)
    reference = worker.finish(abort=True)
    assert store.value(reference)["status"] == "failed"
    assert not (tmp_path / "request-1/result.json").exists()


def test_timeout_kills_worker_records_cost_and_does_not_restart(tmp_path):
    worker, store = start(tmp_path, plan(tmp_path, ("sleep", "pass")), seconds=1)
    begin = time.monotonic()
    with pytest.raises(TimeoutError):
        worker.verify(0)
    reference = worker.finish(abort=True)
    assert 0.5 < time.monotonic() - begin < 3
    report = store.value(reference)
    assert report["status"] == "failed" and report["exit_status"] == -9
    assert report["finished_at"] > report["started_at"]
    with pytest.raises(ValueError, match="cannot restart"):
        worker.start()


def test_out_of_order_request_stops_without_executing(tmp_path):
    worker, store = start(tmp_path, plan(tmp_path))
    with pytest.raises(ValueError, match="next frozen slot"):
        worker.verify(1)
    report = store.value(worker.finish(abort=True))
    assert report["status"] == "failed" and not report["request_refs"]
    assert not (tmp_path / "request-0/result.json").exists()


def test_valid_prefix_can_only_finish_aborted(tmp_path):
    worker, store = start(tmp_path, plan(tmp_path))
    worker.verify(0)
    report = store.value(worker.finish())
    assert report["status"] == "aborted"
    assert len(report["request_refs"]) == 1


def test_source_changed_after_start_is_rejected_before_execution(tmp_path):
    value = plan(tmp_path)
    worker, store = start(tmp_path, value)
    Path(value["requests"][0]["argv"][1]).write_text("raise SystemExit(0)")
    with pytest.raises(ValueError, match="source changed"):
        worker.verify(0)
    assert store.value(worker.finish(abort=True))["status"] == "failed"


@pytest.mark.parametrize("mutation", ["shell", "duplicate_slot", "overlap", "nonfinite", "source_hash"])
def test_plan_rejects_unfrozen_or_ambiguous_requests(tmp_path, mutation):
    value = plan(tmp_path)
    item = value["requests"][0]
    if mutation == "shell": item["argv"] = ["/bin/sh", "-c", "true"]
    if mutation == "duplicate_slot": value["requests"][1]["role"] = "baseline"
    if mutation == "overlap": item["result_path"] = item["output_paths"][0]
    if mutation == "nonfinite": item["cycle"] = float("nan")
    if mutation == "source_hash": item["script_ref"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError): oracle.validate_plan(value)


def test_actual_incorrect_output_is_not_cached_as_previous_success(tmp_path):
    value = plan(tmp_path)
    Path(value["requests"][1]["output_paths"][0]).write_bytes(b"bad")
    worker, store = start(tmp_path, value)
    worker.verify(0)
    with pytest.raises(ValueError, match="execution failed"):
        worker.verify(1)
    assert worker.last_receipt["exit_status"] == 1
    assert store.value(worker.last_receipt["result_ref"])["passed"] is False
    assert store.value(worker.finish(abort=True))["status"] == "failed"


class CountedEpisodeStore(EpisodeStore):
    def __init__(self, path):
        super().__init__(path)
        self.batches = []

    def register_artifacts(self, paths):
        paths = tuple(paths)
        self.batches.append(paths)
        return super().register_artifacts(paths)


def test_real_episode_store_batches_each_successful_request_once(tmp_path):
    value = plan(tmp_path, ("pass", "pass"))
    with CountedEpisodeStore(tmp_path / "episodes.sqlite") as store:
        worker = oracle.PersistentOracle(value, directory=tmp_path / "worker", store=store,
                                         deadline=time.monotonic() + 20).start()
        try:
            receipts = [worker.verify(index) for index in range(2)]
            reference = worker.finish()
        finally:
            worker.finish(abort=True)
        assert len(store.batches) == 2
        assert all(len(paths) == 4 for paths in store.batches)
        report = json.loads(store.verify_artifact(reference).read_text())
        assert report["status"] == "complete" and report["request_refs"] == [r["request_ref"] for r in receipts]
        for item, receipt in zip(value["requests"], receipts):
            assert receipt["log_hash"] == receipt["log_ref"] == oracle.digest(item["log_path"])
            assert receipt["result_ref"] == oracle.digest(item["result_path"])
            assert receipt["stderr_ref"] == oracle.digest(item["stderr_path"])
            assert receipt["output_refs"] == {item["output_paths"][0]: oracle.digest(item["output_paths"][0])}
            assert json.loads(store.verify_artifact(receipt["request_ref"]).read_text())["state_restored"] is True
            for artifact in (receipt["log_ref"], receipt["stderr_ref"], receipt["result_ref"],
                             *receipt["output_refs"].values()):
                store.verify_artifact(artifact)


def test_real_episode_store_keeps_tamper_response_and_failed_receipt(tmp_path):
    value = plan(tmp_path, ("modify", "pass"))
    with CountedEpisodeStore(tmp_path / "episodes.sqlite") as store:
        worker = oracle.PersistentOracle(value, directory=tmp_path / "worker", store=store,
                                         deadline=time.monotonic() + 20).start()
        with pytest.raises(ValueError, match="execution failed or modified"):
            worker.verify(0)
        receipt = worker.last_receipt
        assert len(store.batches) == 1 and receipt["error"]
        assert receipt["output_refs"][value["requests"][0]["output_paths"][0]] == oracle.digest(
            value["requests"][0]["output_paths"][0])
        answer = json.loads(store.verify_artifact(receipt["request_ref"]).read_text())
        assert answer["output_refs_before"] != answer["output_refs_after"]
        assert store.verify_artifact(oracle.digest(tmp_path / "worker/receipt-0000.json"))
        assert json.loads(store.verify_artifact(worker.finish(abort=True)).read_text())["status"] == "failed"
        assert not Path(value["requests"][1]["result_path"]).exists()


def test_batch_partial_file_failure_salvages_logs_and_stops_roster(tmp_path):
    class VanishingResultStore(CountedEpisodeStore):
        def register_artifacts(self, paths):
            paths = tuple(paths)
            Path(paths[2]).unlink()
            return super().register_artifacts(paths)

    value = plan(tmp_path, ("pass", "pass"))
    with VanishingResultStore(tmp_path / "episodes.sqlite") as store:
        worker = oracle.PersistentOracle(value, directory=tmp_path / "worker", store=store,
                                         deadline=time.monotonic() + 20).start()
        with pytest.raises(Exception):
            worker.verify(0)
        receipt = worker.last_receipt
        assert len(store.batches) == 1 and receipt["error"] and receipt["request_ref"]
        answer = json.loads(store.verify_artifact(receipt["request_ref"]).read_text())
        assert answer["kind"] == "result" and answer["state_restored"] is True
        assert receipt["log_hash"] == receipt["log_ref"] == answer["log_hash"]
        assert receipt["stderr_ref"] == answer["stderr_hash"]
        assert receipt["result_ref"] is None and receipt["output_refs"] == {}
        store.verify_artifact(receipt["log_ref"])
        store.verify_artifact(receipt["stderr_ref"])
        with pytest.raises(ValueError, match="not available"):
            worker.verify(1)
        assert json.loads(store.verify_artifact(worker.finish(abort=True)).read_text())["status"] == "failed"
        assert not Path(value["requests"][1]["result_path"]).exists()
