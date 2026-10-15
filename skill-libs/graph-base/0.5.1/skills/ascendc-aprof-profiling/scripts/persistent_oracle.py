#!/usr/bin/env python3
"""Serial execution of frozen Python oracles, with a fresh script namespace per request.

This is a trusted collector helper, not a sandbox for arbitrary Python. Only the
reviewed scripts in the frozen request plan may run; their mathematics is unchanged.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import runpy
import signal
import socket
import subprocess
import sys
import time
import traceback
import uuid

PROTOCOL = "persistent_python_oracle_v1"
MAX_MESSAGE = 1 << 20


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def loads(text):
    def reject(value):
        raise ValueError("nonfinite JSON: " + value)
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(text, parse_constant=reject, object_pairs_hook=unique)


def save(path, value):
    with Path(path).open("x") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def canonical_path(value):
    if not isinstance(value, str) or not Path(value).is_absolute() or str(Path(value).resolve()) != value:
        raise ValueError("path must be absolute and canonical: " + str(value))
    return Path(value)


def validate_plan(value):
    plan = loads(json.dumps(value, allow_nan=False))
    if set(plan) != {"schema_version", "protocol", "run_id", "session_id", "requests"} or plan["schema_version"] != 1 or plan["protocol"] != PROTOCOL:
        raise ValueError("invalid persistent oracle plan")
    if any(not isinstance(plan[k], str) or not plan[k] for k in ("run_id", "session_id")):
        raise ValueError("run and session identities are required")
    if not isinstance(plan["requests"], list) or not plan["requests"]:
        raise ValueError("nonempty frozen request roster required")
    artifacts, slots = set(), set()
    protected = {p for item in plan["requests"] for p in item.get("prepared_refs", {})}
    for index, item in enumerate(plan["requests"]):
        fields = {"request_index", "stage", "case_id", "cycle", "role", "argv", "cwd", "script_ref", "prepared_refs", "output_paths", "result_path", "log_path", "stderr_path"}
        if set(item) != fields or type(item["request_index"]) is not int or item["request_index"] != index:
            raise ValueError("invalid request fields or order")
        if item["stage"] not in ("calibration", "confirmation") or item["role"] not in ("baseline", "candidate") or type(item["case_id"]) is not int or item["case_id"] < 1:
            raise ValueError("invalid request scope")
        if (item["stage"] == "calibration" and item["cycle"] is not None) or (item["stage"] == "confirmation" and (type(item["cycle"]) is not int or not 0 <= item["cycle"] < 6)):
            raise ValueError("invalid request cycle")
        slot = (item["stage"], item["case_id"], item["cycle"], item["role"])
        if slot in slots:
            raise ValueError("duplicate request slot")
        slots.add(slot)
        argv = item["argv"]
        if not isinstance(argv, list) or len(argv) < 2 or any(not isinstance(v, str) or not v or "\0" in v for v in argv):
            raise ValueError("invalid original Python argv")
        if canonical_path(argv[0]) != Path(sys.executable).resolve() or canonical_path(argv[1]).suffix != ".py" or not Path(argv[1]).is_file():
            raise ValueError("only the current Python and a frozen .py script are supported")
        if not canonical_path(item["cwd"]).is_dir() or digest(argv[1]) != item["script_ref"]:
            raise ValueError("oracle directory or source hash differs")
        if not isinstance(item["prepared_refs"], dict) or not item["prepared_refs"]:
            raise ValueError("frozen prepared inputs are required")
        for path, reference in item["prepared_refs"].items():
            canonical_path(path)
            if not isinstance(reference, str) or len(reference) != 71 or not reference.startswith("sha256:") or any(c not in "0123456789abcdef" for c in reference[7:]):
                raise ValueError("invalid prepared input reference")
        outputs = item["output_paths"]
        if not isinstance(outputs, list) or not outputs:
            raise ValueError("output scope is required")
        paths = [*outputs, item["result_path"], item["log_path"], item["stderr_path"]]
        for path in paths:
            canonical_path(path)
            if path in artifacts or path in protected or path in argv[:2]:
                raise ValueError("oracle artifacts overlap")
            artifacts.add(path)
    return plan


def send(channel, message):
    payload = json.dumps(message, sort_keys=True, allow_nan=False).encode() + b"\n"
    if len(payload) > MAX_MESSAGE:
        raise ValueError("oracle IPC message too large")
    channel.sendall(payload)


def receive(channel):
    payload = bytearray()
    # No read-ahead: the serial protocol has exactly one message in flight.
    while True:
        value = channel.recv(1)
        if not value:
            raise RuntimeError("oracle worker closed IPC")
        if value == b"\n":
            return loads(payload)
        payload.extend(value)
        if len(payload) > MAX_MESSAGE:
            raise ValueError("oracle IPC message too large")


def run_script(item, worker_id):
    response = {"kind": "result", "protocol": PROTOCOL, "worker_id": worker_id,
                "pid": os.getpid(), "request_index": item["request_index"], "started_at": time.time(),
                "finished_at": None, "exit_status": 1, "state_restored": False,
                "script_ref": item["script_ref"], "output_refs_before": {}, "output_refs_after": {},
                "log_hash": None, "stderr_hash": None, "result_hash": None, "error": None}
    argv, search, cwd, environment = sys.argv, list(sys.path), os.getcwd(), dict(os.environ)
    stdout, stderr = sys.stdout, sys.stderr
    saved_fds = []
    try:
        if digest(item["argv"][1]) != item["script_ref"]:
            raise ValueError("oracle source changed before request")
        if any(Path(item[key]).exists() for key in ("result_path", "log_path", "stderr_path")):
            raise ValueError("oracle result/log artifacts must be fresh")
        response["output_refs_before"] = {p: digest(p) for p in item["output_paths"]}
        sys.stdout.flush(); sys.stderr.flush()
        saved_fds = [os.dup(1), os.dup(2)]
        with open(item["log_path"], "x") as out, open(item["stderr_path"], "x") as err:
            os.dup2(out.fileno(), 1); os.dup2(err.fileno(), 2)
            sys.argv = item["argv"][1:]
            sys.path[:] = [str(Path(sys.argv[0]).parent), *search[1:]]
            os.chdir(item["cwd"])
            try:
                namespace = runpy.run_path(sys.argv[0], run_name="__main__")
                namespace.clear()
                response["exit_status"] = 0
            except SystemExit as error:
                code = error.code
                response["exit_status"] = 0 if code is None else int(code) if isinstance(code, int) else 1
                if code is not None and not isinstance(code, int):
                    print(code, file=sys.stderr)
            except BaseException as error:
                traceback.print_exc()
                response["error"] = {"type": type(error).__name__, "message": str(error)}
            finally:
                sys.stdout.flush(); sys.stderr.flush()
    except BaseException as error:
        response["error"] = {"type": type(error).__name__, "message": str(error)}
        response["exit_status"] = 1
    finally:
        for original, duplicate in zip((1, 2), saved_fds):
            os.dup2(duplicate, original); os.close(duplicate)
        sys.argv = argv
        sys.stdout, sys.stderr = stdout, stderr
        sys.path[:] = search
        os.chdir(cwd)
        os.environ.clear(); os.environ.update(environment)
        gc.collect()
        response["state_restored"] = True
    try:
        if digest(item["argv"][1]) != item["script_ref"]:
            raise ValueError("oracle source changed during request")
        response["output_refs_after"] = {p: digest(p) for p in item["output_paths"]}
        if response["output_refs_after"] != response["output_refs_before"]:
            raise ValueError("oracle modified a callback output")
    except BaseException as error:
        response["error"] = {"type": type(error).__name__, "message": str(error)}
        response["exit_status"] = 1
    for field, key in (("log_hash", "log_path"), ("stderr_hash", "stderr_path"), ("result_hash", "result_path")):
        if Path(item[key]).is_file():
            response[field] = digest(item[key])
    response["finished_at"] = time.time()
    return response


def serve(plan_path, worker_id, fd):
    plan = validate_plan(loads(Path(plan_path).read_text()))
    with socket.socket(fileno=fd) as channel:
        send(channel, {"kind": "ready", "protocol": PROTOCOL, "worker_id": worker_id,
                       "pid": os.getpid(), "request_plan_ref": digest(plan_path)})
        index, failed = 0, False
        while True:
            request = receive(channel)
            if set(request) == {"kind", "abort"} and request["kind"] == "close" and type(request["abort"]) is bool:
                if not request["abort"] and (failed or index != len(plan["requests"])):
                    raise ValueError("cannot successfully close an incomplete oracle roster")
                send(channel, {"kind": "closed", "completed_requests": index})
                return
            if failed or request != {"kind": "verify", "request_index": index} or index >= len(plan["requests"]):
                raise ValueError("oracle request is not the next frozen slot")
            response = run_script(plan["requests"][index], worker_id)
            send(channel, response)
            index += 1
            failed = response["exit_status"] != 0 or response["error"] is not None


class PersistentOracle:
    def __init__(self, plan, *, directory, store, deadline):
        self.plan = validate_plan(plan)
        self.directory, self.store, self.deadline = Path(directory).resolve(), store, deadline
        self.process = self.channel = None
        self.events, self.request_refs = [], []
        self.failed, self.last_receipt, self.reference = False, None, None
        self.report = {"schema_version": 1, "protocol": PROTOCOL, "run_id": self.plan["run_id"],
                       "session_id": self.plan["session_id"], "worker_id": str(uuid.uuid4()), "pid": None,
                       "started_at": None, "ready_at": None, "finished_at": None, "exit_status": None,
                       "status": "failed", "request_refs": self.request_refs}

    def artifact(self, name, value):
        path = self.directory / name
        save(path, value)
        return self.store.register_artifact(path)

    def remaining(self):
        value = self.deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError("oracle trial budget exhausted")
        return value

    def exchange(self, message=None):
        self.channel.settimeout(self.remaining())
        if message is not None:
            self.events.append({"direction": "send", "at": time.time(), "monotonic_ns": time.monotonic_ns(), "message": message})
            send(self.channel, message)
        answer = receive(self.channel)
        self.events.append({"direction": "receive", "at": time.time(), "monotonic_ns": time.monotonic_ns(), "message": answer})
        return answer

    def start(self):
        if self.process is not None or self.report["started_at"] is not None:
            raise ValueError("oracle worker cannot restart")
        self.remaining()
        self.directory.mkdir(parents=True, exist_ok=False)
        self.report["request_plan_ref"] = self.artifact("request-plan.json", self.plan)
        self.report["worker_source_ref"] = self.store.register_artifact(Path(__file__).resolve())
        self.report["interpreter_ref"] = self.store.register_artifact(Path(sys.executable).resolve())
        parent, child = socket.socketpair()
        self.channel = parent
        self.report["started_at"] = time.time()
        try:
            with (self.directory / "process-stdout.log").open("x") as out, (self.directory / "process-stderr.log").open("x") as err:
                self.process = subprocess.Popen([str(Path(sys.executable).resolve()), str(Path(__file__).resolve()),
                    "--plan", str(self.directory / "request-plan.json"), "--worker-id", self.report["worker_id"],
                    "--ipc-fd", str(child.fileno())], pass_fds=(child.fileno(),), stdout=out, stderr=err,
                    stdin=subprocess.DEVNULL, start_new_session=True)
            self.report["pid"] = self.process.pid
            child.close()
            ready = self.exchange()
            expected = {"kind": "ready", "protocol": PROTOCOL, "worker_id": self.report["worker_id"],
                        "pid": self.process.pid, "request_plan_ref": self.report["request_plan_ref"]}
            if ready != expected:
                raise ValueError("oracle worker identity differs")
            self.report["ready_at"] = time.time()
        except BaseException:
            child.close()
            self.failed = True
            self.finish(abort=True)
            raise
        return self

    def verify(self, request_index):
        if self.process is None or self.report["ready_at"] is None or self.reference is not None or self.failed:
            raise ValueError("oracle worker is not available")
        if type(request_index) is not int or request_index != len(self.request_refs) or request_index >= len(self.plan["requests"]):
            self.failed = True
            raise ValueError("oracle request is not the next frozen slot")
        item = self.plan["requests"][request_index]
        receipt = {"protocol": PROTOCOL, "worker_id": self.report["worker_id"], "request_index": request_index,
                   "argv": item["argv"], "cwd": item["cwd"], "log_path": item["log_path"],
                   "started_at": time.time(), "finished_at": None, "exit_status": None,
                   "log_hash": None, "log_ref": None, "output_refs": {}, "request_ref": None,
                   "result_ref": None, "stderr_ref": None}
        self.last_receipt = receipt
        try:
            if digest(item["argv"][1]) != item["script_ref"]:
                raise ValueError("oracle source changed")
            for key in ("log_path", "stderr_path", "result_path"):
                path = canonical_path(item[key]); path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    raise ValueError("oracle result/log artifacts must be fresh")
            answer = self.exchange({"kind": "verify", "request_index": request_index})
            receipt["request_ref"] = self.artifact(f"request-{request_index:04d}.json", answer)
            self.request_refs.append(receipt["request_ref"])
            if any(answer.get(k) != v for k, v in {"kind": "result", "protocol": PROTOCOL,
                    "worker_id": self.report["worker_id"], "pid": self.process.pid,
                    "request_index": request_index, "script_ref": item["script_ref"]}.items()):
                raise ValueError("oracle response identity differs")
            receipt["exit_status"] = answer["exit_status"]
            artifact_paths = [item[key] for key in ("log_path", "stderr_path", "result_path")
                              if Path(item[key]).is_file()]
            artifact_paths.extend(item["output_paths"])
            try:
                artifact_refs = dict(zip(artifact_paths, self.store.register_artifacts(artifact_paths), strict=True))
            except BaseException:
                # A vanished later file must not discard earlier failure logs.
                # Successful requests still use exactly one batch transaction.
                for key, ref, expected in (("log_path", "log_ref", "log_hash"),
                                           ("stderr_path", "stderr_ref", "stderr_hash"),
                                           ("result_path", "result_ref", "result_hash")):
                    try:
                        if Path(item[key]).is_file():
                            receipt[ref] = self.store.register_artifact(item[key])
                        if receipt[ref] != answer[expected]:
                            break
                    except BaseException:
                        break
                receipt["log_hash"] = receipt["log_ref"]
                raise
            for key, ref, expected in (("log_path", "log_ref", "log_hash"), ("stderr_path", "stderr_ref", "stderr_hash"), ("result_path", "result_ref", "result_hash")):
                receipt[ref] = artifact_refs.get(item[key])
                if receipt[ref] != answer[expected]:
                    raise ValueError("oracle response file hash differs")
            receipt["log_hash"] = receipt["log_ref"]
            receipt["output_refs"] = {p: artifact_refs[p] for p in item["output_paths"]}
            if (answer["output_refs_before"] != receipt["output_refs"] or answer["output_refs_after"] != receipt["output_refs"]
                    or answer["error"] is not None or answer["state_restored"] is not True or answer["exit_status"] != 0):
                raise ValueError("oracle execution failed or modified an output")
            result = loads(Path(item["result_path"]).read_text())
            values = [loads(line) for line in Path(item["log_path"]).read_text().splitlines() if line.lstrip().startswith("{")]
            values = [value for value in values if isinstance(value, dict) and "passed" in value]
            if len(values) != 1 or result != values[0] or result.get("passed") is not True:
                raise ValueError("oracle stdout and result do not uniquely pass")
            self.remaining()
        except BaseException as error:
            receipt["error"] = {"type": type(error).__name__, "message": str(error)}
            self.failed = True
            raise
        finally:
            receipt["finished_at"] = time.time()
            self.artifact(f"receipt-{request_index:04d}.json", receipt)
        return receipt

    def finish(self, *, abort=False):
        if self.reference is not None:
            return self.reference
        complete = not abort and not self.failed and len(self.request_refs) == len(self.plan["requests"])
        try:
            if self.process is not None and self.process.poll() is None:
                closed = self.exchange({"kind": "close", "abort": not complete})
                if closed != {"kind": "closed", "completed_requests": len(self.request_refs)}:
                    raise ValueError("oracle close receipt differs")
                self.process.wait(timeout=self.remaining())
        except BaseException as error:
            self.failed = True
            self.report["error"] = {"type": type(error).__name__, "message": str(error)}
        finally:
            if self.process is not None and self.process.poll() is None:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()
            if self.channel is not None:
                self.channel.close()
        self.report.update(finished_at=time.time(), exit_status=None if self.process is None else self.process.returncode,
                           status="complete" if complete and not self.failed and self.process.returncode == 0 else "failed" if self.failed else "aborted")
        self.report["transcript_ref"] = self.artifact("transcript.json", {"schema_version": 1, "events": self.events})
        for role in ("stdout", "stderr"):
            path = self.directory / ("process-" + role + ".log")
            self.report["process_" + role + "_ref"] = self.store.register_artifact(path) if path.exists() else None
        self.reference = self.artifact("worker-receipt.json", self.report)
        return self.reference


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--ipc-fd", type=int, required=True)
    args = parser.parse_args()
    serve(args.plan, args.worker_id, args.ipc_fd)
