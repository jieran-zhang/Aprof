"""Capture the installed Codex tool inventory with a local, non-model provider."""
from __future__ import annotations

import argparse
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading

from eval_tool_broker import (BASE_INSTRUCTIONS, BUDGET_POLICY, CONFIG, REVIEW_OBLIGATIONS, REVIEW_SUBMISSION_PROTOCOL,
                              checked, digest, final_review, pointer, review_output_schema, tool_specs)


HARMLESS_BUILTINS = {"update_plan", "view_image", "request_user_input", "skills.list", "skills.read"}
CATALOG_OVERRIDES = {
    "remove": ["tool_mode", "multi_agent_version"],
    "set": {"use_responses_lite": False, "experimental_supported_tools": [], "node_repl_disabled": True},
}


def restricted_catalog(metadata):
    """Keep the exact model; disable catalog-forced orchestration interfaces.

    The installed catalog can force code_mode_only despite feature flags. Removing
    that optional preference leaves the explicit feature configuration in control.
    Actual request capture, rather than this recipe, proves the resulting tools.
    """
    result = json.loads(json.dumps(metadata))
    for item in result["models"]:
        for name in CATALOG_OVERRIDES["remove"]:
            item.pop(name, None)
        item.update(CATALOG_OVERRIDES["set"])
    return result


def names(tools, prefix=""):
    result = set()
    for item in tools:
        if item.get("type") == "namespace":
            result.update(names(item["tools"], prefix + item["name"] + "."))
        elif item.get("type") in ("function", "custom"):
            result.add(prefix + item["name"])
        else:
            result.add("builtin:" + item.get("type", "unknown"))
    return result


def sources():
    here = Path(__file__).resolve().parent
    return [pointer(here / name) for name in ("qualify_eval_tools.py", "eval_tool_broker.py", "isolated_eval_worker.py", "eval_candidate_evidence.py", "review_packet.py")]


async def probe(output, model, *, catalog, effort="max", review=False, wiki=False):
    captures = []
    answer = {"obligations": {name: {"status": "unknown", "reason": "Protocol-only local mock.",
              "anchors": [{"path": "candidate/op_kernel/probe.asc", "line": 1}]} for name in REVIEW_OBLIGATIONS}}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            data = self.rfile.read(int(self.headers["Content-Length"]))
            if self.headers.get("Content-Encoding") == "zstd":
                import zstandard
                data = zstandard.ZstdDecompressor().decompress(data)
            body = json.loads(data)
            captures.append(body)
            call = not review and len(captures) == 1
            item = ({"type": "function_call", "id": "fc_probe", "call_id": "call_probe", "name": "list_files", "arguments": '{"path":"."}', "status": "completed"}
                    if call else {"type": "message", "id": "msg_probe", "role": "assistant", "status": "completed",
                                  "content": [{"type": "output_text", "text": json.dumps(answer) if review else "Protocol probe completed."}]})
            response = {"id": "resp_probe_" + str(len(captures)), "object": "response", "status": "completed", "model": model,
                        "output": [item], "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}
            events = [{"type": "response.created", "response": {**response, "status": "in_progress", "output": []}},
                      {"type": "response.output_item.added", "output_index": 0, "item": item},
                      {"type": "response.output_item.done", "output_index": 0, "item": item},
                      {"type": "response.completed", "response": response}]
            encoded = "".join("event: " + item["type"] + "\ndata: " + json.dumps(item) + "\n\n" for item in events).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    output.mkdir(parents=True, exist_ok=False)
    events = []
    try:
        with tempfile.TemporaryDirectory(prefix="aprof-protocol-home-") as temporary:
            provider = '{name="AProf local non-model probe",base_url="http://127.0.0.1:' + str(server.server_port) + '/v1",wire_api="responses",requires_openai_auth=false,supports_websockets=false}'
            command = ["codex", "app-server", "--stdio", "--strict-config", "-c", "model_providers.aprof_probe=" + provider,
                       "-c", 'model_provider="aprof_probe"', "-c", "model_catalog_json=" + json.dumps(str(checked(catalog)))]
            for key, value in CONFIG.items():
                command += ["-c", key + "=" + json.dumps(value)]
            environment = {"PATH": os.environ["PATH"], "HOME": temporary, "CODEX_HOME": temporary, "RUST_LOG": "error"}
            process = await asyncio.create_subprocess_exec(*command, env=environment, cwd=temporary,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            async def send(value):
                process.stdin.write((json.dumps(value) + "\n").encode())
                await process.stdin.drain()
            async def receive(identifier=None, completed=False):
                while line := await process.stdout.readline():
                    event = json.loads(line)
                    events.append(event)
                    if event.get("method") == "item/tool/call":
                        if event["params"]["tool"] != "list_files":
                            raise ValueError("mock provider invoked an unexpected tool")
                        await send({"id": event["id"], "result": {"success": True, "contentItems": [{"type": "inputText", "text": '{"files":[]}'}]}})
                    if event.get("id") == identifier and identifier is not None:
                        if "error" in event:
                            raise ValueError(str(event["error"]))
                        return event["result"]
                    if completed and event.get("method") == "turn/completed":
                        return event
                raise RuntimeError("protocol server exited")
            try:
                async with asyncio.timeout(45):
                    await send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "aprof-tool-probe", "version": "1"}, "capabilities": {"experimentalApi": True}}})
                    await receive(1)
                    await send({"method": "initialized", "params": {}})
                    await send({"id": 2, "method": "thread/start", "params": {"model": model, "modelProvider": "aprof_probe",
                        "allowProviderModelFallback": False,
                        "cwd": temporary, "ephemeral": True, "sandbox": "read-only", "approvalPolicy": "never", "environments": [],
                        "baseInstructions": BASE_INSTRUCTIONS,
                        "config": {**CONFIG, "model_reasoning_effort": effort}, "dynamicTools": tool_specs(review=review, wiki=wiki)}})
                    started = await receive(2)
                    turn = {"threadId": started["thread"]["id"], "effort": effort,
                            "input": [{"type": "text", "text": "Return the final JSON review." if review else
                                       "Protocol-only probe. Use list_files once; do not execute commands."}]}
                    if review:
                        turn["outputSchema"] = review_output_schema()
                    await send({"id": 3, "method": "turn/start", "params": turn})
                    await receive(3)
                    await receive(completed=True)
            finally:
                process.terminate()
                await process.wait()
                (output / "stderr.log").write_bytes(await process.stderr.read())
    finally:
        server.shutdown()
        server.server_close()
    (output / "requests.json").write_text(json.dumps(captures, indent=2) + "\n")
    (output / "events.jsonl").write_text("".join(json.dumps(row) + "\n" for row in events))
    verify_capture(captures, events, model=model, effort=effort, review=review, wiki=wiki)
    return {"review": review, "wiki": wiki, "request_ref": pointer(output / "requests.json"),
            "events_ref": pointer(output / "events.jsonl"), "tool_names": sorted(names(captures[0]["tools"])),
            "dynamic_tools_sha256": digest(tool_specs(review=review, wiki=wiki))}


def verify_capture(requests, events, *, model, effort, review, wiki, base_instructions=BASE_INSTRUCTIONS):
    expected = tool_specs(review=review, wiki=wiki)
    wanted = {tool["name"] for tool in expected}
    if len(requests) != (1 if review else 2):
        raise ValueError("capture differs from the final-review or proposer round-trip protocol")
    for request in requests:
        if not isinstance(request.get("tools"), list) or any(
                item.get("type") == "additional_tools" for item in request.get("input", [])):
            raise ValueError("actual provider request does not expose the qualified finite tool interface")
        actual = names(request["tools"])
        if not wanted <= actual or actual - wanted - HARMLESS_BUILTINS:
            raise ValueError("captured worker tools contain an execution capability")
        if request.get("model") != model or request.get("reasoning", {}).get("effort") != effort:
            raise ValueError("actual provider request differs from frozen model or reasoning effort")
        if request.get("instructions") != base_instructions:
            raise ValueError("actual provider instructions differ from the frozen shared protocol")
        for tool in expected:
            found = [item for item in request["tools"] if item.get("type") == "function" and item.get("name") == tool["name"]]
            if (len(found) != 1 or found[0].get("parameters") != tool["inputSchema"]
                    or found[0].get("description") != tool["description"]):
                raise ValueError("captured dynamic tool schema differs from the broker")
    if review:
        actual = requests[0].get("text", {}).get("format", {})
        if (actual.get("type") != "json_schema" or actual.get("strict") is not True
                or actual.get("schema") != review_output_schema()
                or any(event.get("method") == "item/tool/call" for event in events)):
            raise ValueError("review capture lacks its exact single-response output schema")
        final_review(events)
        return
    calls = [event["params"] for event in events if event.get("method") == "item/tool/call"]
    completed = [event["params"]["turn"] for event in events if event.get("method") == "turn/completed"]
    if (len(calls) != 1 or calls[0]["tool"] != "list_files" or calls[0]["arguments"] != {"path": "."}
            or len(completed) != 1 or completed[0]["status"] != "completed"):
        raise ValueError("tool capture did not complete the controlled protocol round trip")


def verify_qualification(reference, *, model=None, effort=None, retained=None):
    if retained is not None:
        from retained_source_review import _RetainedReview
        if type(retained) is not _RetainedReview:
            raise ValueError("retained qualification requires a verified archive context")
    checked_ref = checked if retained is None else retained.checked
    receipt = json.loads(checked_ref(reference).read_text())
    if retained is not None:
        retained.check_qualification(reference, receipt)
    if (receipt.get("schema_version") != 1 or receipt.get("kind") != "local_mock_provider_tool_capture"
            or receipt.get("review_submission_protocol") != REVIEW_SUBMISSION_PROTOCOL
            or receipt.get("budget_policy") != BUDGET_POLICY
            or receipt["config"] != CONFIG or receipt["producers"] != (sources() if retained is None else retained.producers)
            or receipt["binary"] != (pointer(Path(shutil.which("codex")).resolve()) if retained is None else retained.binary)
            or model is not None and receipt["model"] != model
            or effort is not None and receipt["reasoning_effort"] != effort):
        raise ValueError("tool-only worker qualification is absent or stale")
    catalog = json.loads(checked_ref(receipt["model_catalog"]).read_text())
    original = json.loads(checked_ref(receipt["installed_model_metadata"]).read_text())
    if receipt.get("catalog_overrides") != CATALOG_OVERRIDES or catalog != restricted_catalog(original):
        raise ValueError("frozen model catalog differs from the declared interface-only overrides")
    if ([item["slug"] for item in catalog["models"]] != [receipt["model"]]
            or receipt["reasoning_effort"] not in {level["effort"] for level in catalog["models"][0]["supported_reasoning_levels"]}):
        raise ValueError("frozen model catalog does not support the selected model and effort")
    if {(row["review"], row["wiki"]) for row in receipt["probes"]} != {(False, False), (False, True), (True, False)} or len(receipt["probes"]) != 3:
        raise ValueError("all worker/reviewer tool inventories must be qualified")
    for row in receipt["probes"]:
        requests = json.loads(checked_ref(row["request_ref"]).read_text())
        events = [json.loads(line) for line in checked_ref(row["events_ref"]).read_text().splitlines() if line]
        if row["dynamic_tools_sha256"] != digest(tool_specs(review=row["review"], wiki=row["wiki"])):
            raise ValueError("captured broker schema changed")
        verify_capture(requests, events, model=receipt["model"], effort=receipt["reasoning_effort"], review=row["review"], wiki=row["wiki"],
                       base_instructions=BASE_INSTRUCTIONS if retained is None else retained.base_instructions)
    return receipt


async def qualify(output, model, effort="max"):
    output.mkdir(parents=True, exist_ok=False)
    cache = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "models_cache.json"
    metadata = [item for item in json.loads(cache.read_text())["models"] if item["slug"] == model]
    if len(metadata) != 1 or effort not in {level["effort"] for level in metadata[0]["supported_reasoning_levels"]}:
        raise ValueError("installed model metadata does not support the frozen model/effort")
    original = {"models": metadata}
    (output / "installed-model-metadata.json").write_text(json.dumps(original, indent=2) + "\n")
    (output / "model-catalog.json").write_text(json.dumps(restricted_catalog(original), indent=2) + "\n")
    catalog = pointer(output / "model-catalog.json")
    probes = []
    try:
        for role, review, wiki in (("proposer", False, False), ("wiki-proposer", False, True), ("reviewer", True, False)):
            probes.append(await probe(output / role, model, catalog=catalog, effort=effort, review=review, wiki=wiki))
    except Exception as error:
        failure = {"schema_version": 1, "status": "rejected", "kind": "local_mock_provider_tool_capture",
                   "model": model, "reasoning_effort": effort, "error": str(error),
                   "producers": sources(), "captures": [pointer(path) for path in sorted(output.glob("*/requests.json"))]}
        (output / "qualification-failure.json").write_text(json.dumps(failure, indent=2) + "\n")
        raise
    value = {"schema_version": 1, "kind": "local_mock_provider_tool_capture", "model": model, "reasoning_effort": effort, "config": CONFIG,
             "review_submission_protocol": REVIEW_SUBMISSION_PROTOCOL, "budget_policy": BUDGET_POLICY,
             "binary": pointer(Path(shutil.which("codex")).resolve()), "model_catalog": catalog,
             "installed_model_metadata": pointer(output / "installed-model-metadata.json"), "catalog_overrides": CATALOG_OVERRIDES,
             "metadata_source_sha256": pointer(cache)["sha256"], "producers": sources(), "probes": probes}
    (output / "qualification.json").write_text(json.dumps(value, indent=2) + "\n")
    return pointer(output / "qualification.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", default="gpt-6-sol")
    parser.add_argument("--effort", default="max")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(qualify(args.output.resolve(), args.model, args.effort))))
