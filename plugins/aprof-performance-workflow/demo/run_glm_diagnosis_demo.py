#!/usr/bin/env python3
"""GLM-5.2 blind diagnosis demo for aprof_benchmark/fast_gelu.

Pipeline (mirrors plugins/aprof-performance-workflow + aprof_benchmark layout):
  1. Build agent-safe blind input from a case dir (no .ground_truth).
  2. Call Zhipu GLM-5.2 with diagnosis system prompt + blind JSON.
  3. Write single_case_diagnosis.json under demo/out/.
  4. Optionally offline-compare with .ground_truth (maintainer only; never sent to the model).

Usage (from repo root):
  python plugins/aprof-performance-workflow/demo/run_glm_diagnosis_demo.py
  python plugins/aprof-performance-workflow/demo/run_glm_diagnosis_demo.py \\
      --case-dir benchmarks/aprof_benchmark/fast_gelu/operators/op_0001
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
DEMO = Path(__file__).resolve().parent
DEFAULT_CASE = REPO / "benchmarks" / "aprof_benchmark" / "fast_gelu" / "operators" / "op_0001"
BUILD_BLIND = (
    REPO
    / "skills"
    / "aprof"
    / "benchmark"
    / "ascendc-aprof-inject-problems"
    / "tools"
    / "build_blind_diagnosis_input.py"
)
SECRETS = REPO / "configs" / "secrets" / "glm.env"
HW_CTX = DEMO / "hardware_context_910b.example.json"
SYSTEM_PROMPT = DEMO / "prompts" / "system.md"
CONTRACT_SNIPPET = REPO / "skills" / "aprof" / "references" / "contracts.md"


def load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def resolve_api_config() -> tuple[str, str, str]:
    env = {**load_dotenv(SECRETS), **os.environ}
    key = env.get("ZHIPU_API_KEY") or env.get("GLM_API_KEY") or ""
    if not key or key.startswith("your_"):
        raise SystemExit(
            "Missing ZHIPU_API_KEY. Copy configs/secrets/glm.env.example -> glm.env and fill the key."
        )
    model = env.get("GLM_MODEL", "glm-5.2")
    base = env.get(
        "GLM_BASE_URL",
        "https://open.bigmodel.cn/api/paas/v4/chat/completions",
    )
    return key, model, base


def build_blind_input(case_dir: Path, out_path: Path, case_id: str) -> Path:
    cmd = [
        sys.executable,
        str(BUILD_BLIND),
        "--case-dir",
        str(case_dir),
        "--out",
        str(out_path),
        "--case-id",
        case_id,
    ]
    if HW_CTX.is_file():
        cmd.extend(["--hardware-context-json", str(HW_CTX)])
    subprocess.check_call(cmd)
    return out_path


def build_system_message() -> str:
    parts = [SYSTEM_PROMPT.read_text(encoding="utf-8")]
    # Keep contract excerpt short to control tokens
    if CONTRACT_SNIPPET.is_file():
        text = CONTRACT_SNIPPET.read_text(encoding="utf-8")
        marker = "## single_case_diagnosis.json"
        idx = text.find(marker)
        if idx >= 0:
            snippet = text[idx : idx + 3500]
            parts.append("\n\n# Contract excerpt\n\n" + snippet)
    return "\n".join(parts)


def call_glm(api_key: str, model: str, url: str, system: str, user: str) -> dict[str, Any]:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 8192,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"GLM HTTP {exc.code}: {detail}") from exc


def extract_message_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise SystemExit(f"empty choices: {json.dumps(payload, ensure_ascii=False)[:800]}")
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        # multimodal-style content blocks
        texts = [c.get("text", "") for c in content if isinstance(c, dict)]
        content = "\n".join(texts)
    if not isinstance(content, str) or not content.strip():
        raise SystemExit(f"no text content in response: {json.dumps(payload, ensure_ascii=False)[:800]}")
    return content


def parse_json_loose(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def offline_align(case_dir: Path, diagnosis: dict[str, Any]) -> dict[str, Any] | None:
    """Maintainer-only: compare predicted family/id hints with GT. Never sent to the model."""
    # case_dir = .../operators/op_0001 -> op root is parents[1]
    op_root = case_dir.parents[1] if case_dir.parent.name == "operators" else case_dir.parent
    gt_path = op_root / ".ground_truth" / "case_problem_map.json"
    if not gt_path.is_file():
        return None
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    folder = case_dir.name
    truth = next((c for c in gt.get("cases", []) if c.get("folder") == folder), None)
    if not truth:
        return None
    predicted = []
    for d in diagnosis.get("diagnoses") or []:
        predicted.append(
            {
                "problem": d.get("problem"),
                "problem_family": d.get("problem_family"),
                "confidence": d.get("confidence"),
            }
        )
    return {
        "case_folder": folder,
        "ground_truth": {
            "problem_id": truth.get("problem_id"),
            "problem_family": truth.get("problem_family"),
        },
        "model_predictions": predicted,
        "note": "Offline alignment only. Ground truth was NOT provided to the model.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run GLM-5.2 blind diagnosis demo on aprof_benchmark case")
    parser.add_argument("--case-dir", type=Path, default=DEFAULT_CASE)
    parser.add_argument("--case-id", default="fast_gelu_op_0001_demo")
    parser.add_argument("--out-dir", type=Path, default=DEMO / "out")
    parser.add_argument("--dry-run", action="store_true", help="Build blind input only; do not call API")
    args = parser.parse_args()

    case_dir = args.case_dir.resolve()
    if not case_dir.is_dir():
        raise SystemExit(f"case dir not found: {case_dir}")
    # Refuse leaking ground truth into the request path
    if ".ground_truth" in case_dir.parts or ".maintainer_artifacts" in case_dir.parts:
        raise SystemExit("Refuse to diagnose from .ground_truth / .maintainer_artifacts paths")

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    blind_path = out_dir / "blind_input.json"
    build_blind_input(case_dir, blind_path, args.case_id)
    blind = json.loads(blind_path.read_text(encoding="utf-8"))

    # Defense: strip any accidental forbidden keys
    for bad in ("problem_id", "injected_label", "injected_problem", "legacy_variant"):
        if bad in json.dumps(blind):
            print(f"warning: blind input still contains token {bad!r}; sanitizer should have removed it")

    if args.dry_run:
        print(f"[dry-run] wrote {blind_path}")
        return 0

    api_key, model, url = resolve_api_config()
    system = build_system_message()
    user = (
        "请对以下盲诊输入做单 kernel 独立诊断，只输出 single_case_diagnosis.json。\n\n"
        + json.dumps(blind, ensure_ascii=False, indent=2)
    )

    print(f"calling {model} for case={case_dir} ...")
    raw = call_glm(api_key, model, url, system, user)
    (out_dir / "glm_raw_response.json").write_text(
        json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    content = extract_message_content(raw)
    (out_dir / "glm_raw_content.txt").write_text(content, encoding="utf-8")

    diagnosis = parse_json_loose(content)
    diag_path = out_dir / "single_case_diagnosis.json"
    diag_path.write_text(json.dumps(diagnosis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {diag_path}")

    align = offline_align(case_dir, diagnosis)
    if align:
        align_path = out_dir / "offline_alignment.json"
        align_path.write_text(json.dumps(align, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {align_path} (maintainer-only; not sent to model)")
        print(
            f"GT family={align['ground_truth'].get('problem_family')} "
            f"id={align['ground_truth'].get('problem_id')}"
        )

    # Also emit a short markdown for humans
    md_lines = [
        "# GLM Diagnosis Demo Result",
        "",
        f"- case_dir: `{case_dir}`",
        f"- model: `{model}`",
        f"- output: `{diag_path}`",
        "",
        "## Top diagnoses",
        "",
    ]
    for i, d in enumerate(diagnosis.get("diagnoses") or [], 1):
        md_lines.append(
            f"{i}. **{d.get('problem')}** "
            f"(family=`{d.get('problem_family')}`, confidence=`{d.get('confidence')}`, "
            f"evidence=`{d.get('evidence_level')}`)"
        )
        if d.get("recommendation"):
            md_lines.append(f"   - recommendation: {d['recommendation']}")
    md_path = out_dir / "final_diagnosis.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
