#!/usr/bin/env python3
"""One source-only evaluation worker, with a private filesystem and usage receipt."""
from __future__ import annotations

import argparse
import asyncio
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from eval_tool_broker import (BASE_INSTRUCTIONS, BUDGET_POLICY, Broker, CONFIG, checked, final_review,
                              pointer, review_output_schema, tool_specs)


def sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_worker_build_budget_enforcement(reference=None, *, model=None, effort=None):
    if reference is None:
        raise ValueError("worker build-budget enforcement requires an authoritative tool-capture qualification")
    from qualify_eval_tools import verify_qualification
    return verify_qualification(reference, model=model, effort=effort)


def mount(source, target, *, readonly=False):
    target = Path(target)
    if Path(source).is_dir():
        target.mkdir(parents=True, exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
    subprocess.run(["mount", "--rbind" if Path(source).is_dir() else "--bind", str(source), str(target)], check=True)
    if readonly:
        mounts = [line.split()[4].replace("\\040", " ") for line in Path("/proc/self/mountinfo").read_text().splitlines()]
        for path in sorted({str(target), *(p for p in mounts if p.startswith(str(target) + "/"))}, reverse=True):
            subprocess.run(["mount", "-o", "remount,bind,ro", path], check=True)


def namespace_child(root, argv):
    """Only system binaries/libraries and explicitly staged inputs enter the root."""
    subprocess.run(["mount", "--make-rprivate", "/"], check=True)
    for name in ("usr", "bin", "sbin", "lib", "lib64", "etc"):
        if Path("/" + name).exists():
            mount("/" + name, root / name, readonly=True)
    # The host disallows new proc mounts. Keep /proc empty; binding the host's
    # proc would expose /proc/<host-pid>/root and defeat corpus isolation.
    (root / "proc/self").mkdir(parents=True, exist_ok=True)
    (root / "proc/self/exe").symlink_to("/aprof-bin/codex")
    for name in ("null", "zero", "random", "urandom"):
        mount("/dev/" + name, root / "dev" / name)
    # Only the parent file broker may mutate implementation sources. Even a
    # built-in file tool inside app-server sees the entire workspace read-only.
    mount(root / "work", root / "work", readonly=True)
    last_capability = int(Path("/proc/sys/kernel/cap_last_cap").read_text())
    os.chroot(root)
    os.chdir("/work")
    # Dropping capabilities makes the staged root and read-only binds persistent.
    libc = ctypes.CDLL(None, use_errno=True)
    for capability in range(last_capability + 1):
        if libc.prctl(24, capability, 0, 0, 0) != 0:  # PR_CAPBSET_DROP
            raise OSError(ctypes.get_errno(), "cannot drop capability")
    if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
        raise OSError(ctypes.get_errno(), "cannot set no_new_privs")
    header = (ctypes.c_uint32 * 2)(0x20080522, 0)
    values = (ctypes.c_uint32 * 6)(0, 0, 0, 0, 0, 0)
    if libc.capset(ctypes.byref(header), ctypes.byref(values)) != 0:
        raise OSError(ctypes.get_errno(), "cannot clear capabilities")
    os.execv(argv[0], argv)


def make_root(workspace, destination):
    root = destination / "root"
    root.mkdir()
    shutil.copytree(workspace, root / "work")
    for name in ("tmp", "dev", "proc", "root", "aprof-bin"):
        (root / name).mkdir(exist_ok=True)
    binary = Path(shutil.which("codex")).resolve(strict=True)
    shutil.copy2(binary, root / "aprof-bin/codex")
    host = binary.parent / "codex-code-mode-host"
    if host.exists():
        shutil.copy2(host, root / "aprof-bin/codex-code-mode-host")
    for relative in ("codex-resources/bwrap", "codex-path/rg"):
        source = binary.parent.parent / relative
        if source.exists():
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, root / relative)
    # Preserve the configured home path; copy authentication only, never histories,
    # memories, user skills, plugins, config, or other evaluation runs.
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    if not home.is_absolute():
        raise ValueError("CODEX_HOME must be absolute")
    local_home = root / str(home).lstrip("/")
    local_home.mkdir(parents=True, exist_ok=True)
    auth = home / "auth.json"
    if auth.exists():
        shutil.copy2(auth, local_home / "auth.json")
        (local_home / "auth.json").chmod(0o600)
    return root, local_home


def wiki_reply(wiki, page_id, reads, elapsed):
    entries = json.loads((wiki / "index.json").read_text())["entries"]
    if page_id not in entries:
        raise ValueError("unknown Wiki page")
    page = (wiki / entries[page_id]["page"]).resolve(strict=True)
    if not page.is_relative_to(wiki.resolve()) or page.suffix != ".md":
        raise ValueError("Wiki page escapes the frozen library")
    text = page.read_text()
    import tiktoken
    reads.append({"page_id": page_id, "sha256": sha(page), "bytes": len(text.encode()),
                  "estimated_tokens": len(tiktoken.get_encoding("o200k_base").encode(text)),
                  "token_estimator": "o200k_base; actual model tokens recorded separately",
                  "elapsed_seconds": elapsed})
    return {"contentItems": [{"type": "inputText", "text": text}], "success": True}


async def run(workspace, output, model, effort, token_limit, seconds, wiki=None, probe=False,
              *, qualification=None, review=False, route_registry=None, release=None, deadline_monotonic=None):
    started = time.monotonic()
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds:
        raise ValueError("worker requires finite positive remaining time within the original shared task deadline")
    if deadline_monotonic is not None:
        if (type(deadline_monotonic) not in (int, float) or not math.isfinite(deadline_monotonic)
                or deadline_monotonic <= started):
            raise TimeoutError("original model task deadline expired")
        seconds = min(seconds, deadline_monotonic - started)
    if not probe:
        if token_limit is not None:
            raise ValueError("time_only_v1 records token costs without a token limit")
        require_worker_build_budget_enforcement(qualification, model=model, effort=effort)
    output.mkdir(parents=True, exist_ok=False)
    try:
        return await _run(workspace, output, model, effort, token_limit,
                          seconds - (time.monotonic() - started), wiki, probe,
                          qualification=qualification, review=review, route_registry=route_registry, release=release)
    finally:
        # Startup and transport exceptions must also remove staged credentials.
        home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        if home.is_absolute():
            auth_home = output / "root" / str(home).lstrip("/")
            if auth_home.is_dir():
                shutil.rmtree(auth_home)


async def _run(workspace, output, model, effort, token_limit, seconds, wiki=None, probe=False,
               *, qualification=None, review=False, route_registry=None, release=None):
    started = time.monotonic()
    deadline = started + seconds
    if time.monotonic() >= deadline:
        raise TimeoutError("worker deadline exhausted before startup")
    root, auth_home = make_root(workspace, output)
    if time.monotonic() >= deadline:
        raise TimeoutError("worker deadline exhausted during isolated filesystem setup")
    command = ["unshare", "--user", "--map-root-user", "--mount", "--pid", "--fork", "--kill-child",
               sys.executable, str(Path(__file__).resolve()), "--namespace-child", str(root),
               "/aprof-bin/codex", "app-server", "--stdio", "--strict-config"]
    if not probe:
        catalog = json.loads(checked(qualification).read_text())["model_catalog"]
        shutil.copy2(checked(catalog), root / "aprof-bin/model-catalog.json")
        command += ["-c", 'model_catalog_json="/aprof-bin/model-catalog.json"']
    for key, value in CONFIG.items():
        command += ["-c", key + "=" + json.dumps(value)]
    broker = Broker(root / "work", output / "broker.jsonl", review=review, wiki=wiki,
                    route_registry=route_registry, release=release)
    broker.log.write_text("")
    # Do not inherit model, MCP, or agent config. The staged home has only auth.json.
    environment = {k: v for k, v in os.environ.items() if k in
                   {"PATH", "HOME", "CODEX_HOME", "OPENAI_API_KEY", "CODEX_API_KEY",
                    "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NO_PROXY", "SSL_CERT_FILE"}}
    reads, usage, final, status = [], None, [], "incomplete"
    review_submission = None
    stderr = (output / "stderr.log").open("wb")
    process = await asyncio.create_subprocess_exec(*command, stdin=asyncio.subprocess.PIPE,
                                                   stdout=asyncio.subprocess.PIPE, stderr=stderr,
                                                   env=environment, start_new_session=True, limit=16 * 1024 * 1024)
    sequence = 0
    pending = {}
    done = asyncio.Event()
    log = (output / "events.jsonl").open("w")

    async def send(value):
        process.stdin.write((json.dumps(value, ensure_ascii=False) + "\n").encode())
        await process.stdin.drain()

    async def request(method, params):
        nonlocal sequence
        sequence += 1
        future = asyncio.get_running_loop().create_future()
        pending[sequence] = future
        await send({"id": sequence, "method": method, "params": params})
        return await future

    async def listen():
        nonlocal usage, status
        while line := await process.stdout.readline():
            event = json.loads(line)
            log.write(json.dumps(event, ensure_ascii=False) + "\n")
            log.flush()
            method, params = event.get("method"), event.get("params", {})
            if "id" in event and method is None:
                future = pending.pop(event["id"], None)
                if future is not None:
                    if "error" in event:
                        future.set_exception(RuntimeError(str(event["error"])))
                    else:
                        future.set_result(event.get("result"))
            elif method == "thread/tokenUsage/updated":
                usage = params["tokenUsage"]["total"]
            elif method == "item/tool/call":
                try:
                    result = broker.call(params["tool"], params["arguments"])
                    if params["tool"] == "read_wiki":
                        import tiktoken
                        reads.append({key: result[key] for key in ("page_id", "sha256", "bytes")} | {
                            "estimated_tokens": len(tiktoken.get_encoding("o200k_base").encode(result["text"])),
                            "elapsed_seconds": time.monotonic() - started})
                    response = {"contentItems": [{"type": "inputText", "text": json.dumps(result, ensure_ascii=False)}], "success": True}
                except Exception as error:
                    response = {"contentItems": [{"type": "inputText", "text": str(error)}], "success": False}
                await send({"id": event["id"], "result": response})
            elif method == "item/completed" and params.get("item", {}).get("type") == "agentMessage":
                final.append(params["item"].get("text", ""))
            elif method == "turn/completed":
                if status == "incomplete":
                    status = params["turn"]["status"]
                done.set()
            elif "id" in event and method:
                await send({"id": event["id"], "error": {"code": -32601, "message": "Unavailable in frozen evaluation"}})
        for future in pending.values():
            if not future.done():
                future.set_exception(RuntimeError("Codex app-server exited"))
        done.set()

    reader = asyncio.create_task(listen())
    try:
        async with asyncio.timeout(deadline - time.monotonic()):
            await request("initialize", {"clientInfo": {"name": "aprof-release-eval", "version": "1.0.0"},
                                         "capabilities": {"experimentalApi": True}})
            await send({"method": "initialized", "params": {}})
            if probe:
                response = await request("command/exec", {"command": ["/bin/sh", "-c",
                    "test ! -e /mnt/tidalfs-hwwh01/dataset/dots_infra/workspace/jieran/APROF && test ! -e /dev/davinci0 && ! touch /work/.aprof-readonly-probe 2>/dev/null && printf isolated"],
                    "cwd": "/work", "sandboxPolicy": {"type": "externalSandbox", "networkAccess": "enabled"}})
                if response["exitCode"] != 0 or response["stdout"] != "isolated":
                    raise RuntimeError(f"isolated command probe failed: {response}")
                status = "protocol_probe_passed"
            else:
                params = {"model": model, "allowProviderModelFallback": False, "cwd": "/work",
                          "approvalPolicy": "never", "sandbox": "read-only", "ephemeral": True, "environments": [],
                          "baseInstructions": BASE_INSTRUCTIONS,
                          "config": {**CONFIG, "model_reasoning_effort": effort},
                          "dynamicTools": tool_specs(review=review, wiki=wiki is not None)}
                thread = await request("thread/start", params)
                if thread["model"] != model or thread["reasoningEffort"] != effort:
                    raise ValueError("model or effort fallback violates frozen identity")
                turn = {"threadId": thread["thread"]["id"], "effort": effort,
                        "input": [{"type": "text", "text": (workspace / "prompt.txt").read_text()}]}
                if review:
                    turn["outputSchema"] = review_output_schema()
                await request("turn/start", turn)
                await done.wait()
    except TimeoutError:
        status = "over_wall_time_budget"
    except (ValueError, RuntimeError, OSError) as error:
        status = "worker_error"
        final.append(f"Worker failed before a valid candidate: {type(error).__name__}: {error}")
    finally:
        if process.returncode is None:
            import signal
            os.killpg(process.pid, signal.SIGTERM)
            try:
                await asyncio.wait_for(process.wait(), 5)
            except TimeoutError:
                os.killpg(process.pid, signal.SIGKILL)
                await process.wait()
        await reader
        stderr.close()
        log.close()
        # Credentials never form part of the evaluation artifact.
        shutil.rmtree(auth_home)
    if not probe and usage is None:
        status = "missing_usage_receipt"
    elif not probe and status == "completed":
        if review:
            try:
                events = [json.loads(line) for line in (output / "events.jsonl").read_text().splitlines() if line]
                decision, review_submission = final_review(events)
                broker.validate_review(decision["obligations"])
                broker.submitted = decision
            except Exception as error:
                status = "invalid_review_submission"
                review_submission = None
                final.append(f"Invalid final review: {type(error).__name__}: {error}")
        elif broker.submitted is None:
            status = "missing_submission"
    if not probe and time.monotonic() > deadline:
        status = "over_wall_time_budget"
    receipt = {"schema_version": 1, "status": status, "model": model, "reasoning_effort": effort,
               "duration_seconds": time.monotonic() - started, "usage": usage, "wiki_reads": reads,
               "budget_policy": BUDGET_POLICY,
               "token_budget_enforcement": "none; authoritative usage recorded as cost only",
               "isolation": "user/mount/pid namespace, chroot, read-only workspace, capabilities dropped, no NPU or archive mounts",
               "role": "reviewer" if review else "proposer", "qualification_ref": qualification,
               "events_ref": pointer(output / "events.jsonl"), "broker_ref": pointer(broker.log),
               "submission": broker.submitted, "config": CONFIG, "worker_builds": 0}
    if review:
        receipt["review_submission"] = review_submission
    (output / "worker.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (output / "result.md").write_text("\n".join(final))
    return receipt


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--namespace-child":
        namespace_child(Path(sys.argv[2]), sys.argv[3:])
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--probe", action="store_true", required=True)
        parser.add_argument("--probe-output", type=Path, help="Preserve the namespace-only probe and raw protocol events")
        args = parser.parse_args()
        def probe_at(directory):
            (directory / "workspace").mkdir()
            receipt = asyncio.run(run(directory / "workspace", directory / "output", "unused", "unused", 0, 30, probe=True))
            (directory / "probe.json").write_text(json.dumps(receipt, indent=2) + "\n")
            print(json.dumps(receipt))
        if args.probe_output:
            directory = args.probe_output.resolve()
            directory.mkdir(parents=True, exist_ok=False)
            probe_at(directory)
        else:
            with tempfile.TemporaryDirectory(prefix="aprof-eval-probe-") as temporary:
                probe_at(Path(temporary))
