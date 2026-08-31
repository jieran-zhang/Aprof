#!/usr/bin/env python3
"""Batch blind-diagnosis eval with GLM-5.2 + ascendc-aprof-diagnosis skill.

Loads diagnosis skill materials into the system prompt (never ground truth),
runs anonymous operators/op_XXXX cases, then offline-aligns vs .ground_truth.

Usage (repo root):
  python plugins/aprof-performance-workflow/demo/run_glm_batch_eval.py
  python plugins/aprof-performance-workflow/demo/run_glm_batch_eval.py --limit 6
  python plugins/aprof-performance-workflow/demo/run_glm_batch_eval.py \\
      --op-root benchmarks/aprof_benchmark/fast_gelu --folders op_0001,op_0002,op_0003
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
DEMO = Path(__file__).resolve().parent
DEFAULT_OP_ROOT = REPO / "benchmarks" / "aprof_benchmark" / "fast_gelu"
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
DIAG_SKILL = REPO / "skills" / "aprof" / "diagnosis"
CONTRACT = REPO / "skills" / "aprof" / "references" / "contracts.md"
SYSTEM_BASE = DEMO / "prompts" / "system.md"

# Caps keep prompt size manageable while still "calling" the skill.
SKILL_FILE_CAPS = {
    "SKILL.md": 6000,
    "references/source-hypothesis-routing.md": 8000,
    "references/tiling-diagnosis-metrics.md": 3500,
    "references/data-movement-diagnosis-metrics.md": 3500,
    "references/pipeline-parallel-diagnosis-metrics.md": 3500,
    "references/onchip-memory-diagnosis-metrics.md": 3000,
    "references/ai-core-utilization-diagnosis-metrics.md": 3000,
    "references/api-algorithm-diagnosis-metrics.md": 3000,
    "references/roofline-single-case.md": 3500,
}


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
        raise SystemExit("Missing ZHIPU_API_KEY in configs/secrets/glm.env")
    model = env.get("GLM_MODEL", "glm-5.2")
    base = env.get("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
    return key, model, base


def clip(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    return text[:n] + f"\n\n...[truncated {len(text) - n} chars]...\n"


def build_skill_system_prompt() -> str:
    """Assemble system prompt by loading ascendc-aprof-diagnosis skill files."""
    parts: list[str] = []
    if SYSTEM_BASE.is_file():
        parts.append(SYSTEM_BASE.read_text(encoding="utf-8"))

    parts.append(
        "\n\n# Loaded skill: ascendc-aprof-diagnosis\n"
        "You MUST follow the skill materials below. "
        "Do not invent msprof fields. Do not mention inject/ground-truth labels.\n"
    )
    for rel, cap in SKILL_FILE_CAPS.items():
        path = DIAG_SKILL / rel
        if not path.is_file():
            continue
        parts.append(f"\n\n## skill file: {rel}\n\n")
        parts.append(clip(path.read_text(encoding="utf-8", errors="replace"), cap))

    if CONTRACT.is_file():
        text = CONTRACT.read_text(encoding="utf-8")
        marker = "## single_case_diagnosis.json"
        idx = text.find(marker)
        if idx >= 0:
            parts.append("\n\n# Output contract\n\n")
            parts.append(clip(text[idx:], 4000))
    return "".join(parts)


def build_blind_input(case_dir: Path, out_path: Path, case_id: str) -> dict[str, Any]:
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
    return json.loads(out_path.read_text(encoding="utf-8"))


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
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GLM HTTP {exc.code}: {detail}") from exc


def extract_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError(f"empty choices: {json.dumps(payload)[:500]}")
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        content = "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("no text content")
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


def load_gt_map(op_root: Path) -> dict[str, dict[str, str]]:
    path = op_root / ".ground_truth" / "case_problem_map.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        c["folder"]: {
            "problem_family": c.get("problem_family", ""),
            "problem_id": c.get("problem_id", ""),
        }
        for c in data.get("cases", [])
        if c.get("folder")
    }


def score_case(gt: dict[str, str], diagnosis: dict[str, Any]) -> dict[str, Any]:
    preds = diagnosis.get("diagnoses") or []
    families = [str(d.get("problem_family", "")).lower() for d in preds]
    problems = [str(d.get("problem", "")).lower() for d in preds]
    gt_fam_raw = (gt.get("problem_family") or "").lower()
    # Normalize legacy inject family names used in some aprof_injected_ops maps
    legacy = {
        "blockdim": "tiling",
        "dynshape": "tiling",
        "tail": "tiling",
        "tilelen_large": "tiling",
        "tilelen_small": "tiling",
        "tilenum": "tiling",
    }
    gt_fam = legacy.get(gt_fam_raw, gt_fam_raw)
    gt_id = (gt.get("problem_id") or "").lower().replace("_", " ")

    fam_hit = any(gt_fam and gt_fam in f for f in families) if gt_fam else False
    # also accept compound families like tiling/ai_core_utilization
    if not fam_hit and gt_fam:
        fam_hit = any(gt_fam in f.split("/") for f in families)

    id_hit = False
    tokens = [t for t in re.split(r"[_\s]+", gt_id) if len(t) > 2]
    for p in problems:
        if gt_id and (gt_id in p or all(t in p for t in tokens[:2])):
            id_hit = True
            break
    # heuristic aliases
    aliases = {
        "tile_length_too_small": ["tilelength", "tile length", "tile_len"],
        "tail_inefficient": ["tail"],
        "redundant_copyin": ["copyin", "copy-in", "redundant copy"],
        "extra_copyout": ["copyout", "copy-out"],
        "serial_copy_compute_copyout": ["serial", "double buffer", "overlap"],
        "excessive_pipe_barrier": ["pipebarrier", "barrier", "pipe_all"],
        "ub_temp_overallocated": ["ub", "overalloc", "temp"],
        "gm_spill_intermediate": ["spill", "gm", "workspace"],
        "underused_blockdim": ["blockdim", "underused", "utilization"],
        "overlaunched_empty_cores": ["empty", "overlaunch", "idle"],
        "scalar_loop_redundant": ["scalar"],
        "redundant_cast_or_vector_copy": ["cast", "vector copy"],
    }
    if not id_hit:
        for key, words in aliases.items():
            if key.replace("_", " ") in gt_id or key == gt.get("problem_id"):
                blob = " ".join(problems)
                if any(w in blob for w in words):
                    id_hit = True
                    break

    return {
        "family_hit": fam_hit,
        "id_hit": id_hit,
        "top1_family": (preds[0].get("problem_family") if preds else None),
        "top1_problem": (preds[0].get("problem") if preds else None),
        "n_preds": len(preds),
    }


def assert_no_gt_leak(blind: dict[str, Any]) -> None:
    """Forbid answer fields as JSON keys; allow instructional text mentioning the words."""
    forbidden_keys = {
        "problem_id",
        "injected_label",
        "injected_problem",
        "legacy_variant",
        "case_problem_map",
    }

    def walk(obj: Any, path: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if str(k) in forbidden_keys:
                    raise SystemExit(f"blind input leak key at {path}.{k}")
                walk(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")

    walk(blind)
    # Paths must not point into ground-truth dirs
    dumped = json.dumps(blind)
    if "/.ground_truth/" in dumped or "\\.ground_truth\\" in dumped:
        raise SystemExit("blind input references .ground_truth path")


def discover_jobs(bench_root: Path | None, op_root: Path, folders_arg: str, limit: int) -> list[tuple[Path, str]]:
    """Return list of (op_root, folder) jobs."""
    jobs: list[tuple[Path, str]] = []
    if bench_root is not None:
        root = bench_root.resolve()
        for op_dir in sorted(root.iterdir()):
            if not op_dir.is_dir() or op_dir.name.startswith(".") or op_dir.name in {"common"}:
                continue
            operators = op_dir / "operators"
            if not operators.is_dir():
                continue
            if not (op_dir / ".ground_truth" / "case_problem_map.json").is_file():
                print(f"skip {op_dir.name}: no ground truth map")
                continue
            for d in sorted(operators.iterdir()):
                if d.is_dir() and re.fullmatch(r"op_\d{4}", d.name):
                    jobs.append((op_dir, d.name))
    else:
        op_root = op_root.resolve()
        operators = op_root / "operators"
        if not operators.is_dir():
            raise SystemExit(f"operators/ not found under {op_root}")
        if folders_arg.strip():
            folders = [f.strip() for f in folders_arg.split(",") if f.strip()]
        else:
            folders = sorted(
                d.name for d in operators.iterdir() if d.is_dir() and re.fullmatch(r"op_\d{4}", d.name)
            )
            if limit > 0:
                folders = folders[:limit]
        for folder in folders:
            jobs.append((op_root, folder))
    if limit > 0 and bench_root is not None:
        jobs = jobs[:limit]
    return jobs


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch GLM blind diagnosis with diagnosis skill")
    parser.add_argument("--op-root", type=Path, default=DEFAULT_OP_ROOT, help="single op root (gold layout)")
    parser.add_argument(
        "--bench-root",
        type=Path,
        default=None,
        help="multi-op root e.g. benchmarks/aprof_injected_ops (overrides --op-root)",
    )
    parser.add_argument("--folders", default="", help="comma list, e.g. op_0001,op_0002 (single op-root only)")
    parser.add_argument("--limit", type=int, default=0, help="max jobs; 0 = all")
    parser.add_argument("--out-dir", type=Path, default=DEMO / "out" / "batch_eval")
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--resume", action="store_true", help="skip cases that already have single_case_diagnosis.json")
    args = parser.parse_args()

    jobs = discover_jobs(args.bench_root, args.op_root, args.folders, args.limit)
    if not jobs:
        raise SystemExit("no jobs discovered")

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    api_key, model, url = resolve_api_config()
    print(f"loading skill ascendc-aprof-diagnosis from {DIAG_SKILL}", flush=True)
    system = build_skill_system_prompt()
    (out_dir / "system_prompt_loaded_skills.txt").write_text(system, encoding="utf-8")
    print(f"system prompt chars={len(system)} model={model} jobs={len(jobs)}", flush=True)

    rows: list[dict[str, Any]] = []
    for op_root, folder in jobs:
        operators = op_root / "operators"
        case_dir = operators / folder
        op_name = op_root.name
        case_out = out_dir / op_name / folder
        case_out.mkdir(parents=True, exist_ok=True)
        diag_path = case_out / "single_case_diagnosis.json"

        if args.resume and diag_path.is_file():
            print(f"\n===== SKIP {op_name}/{folder} (resume) =====", flush=True)
            try:
                diagnosis = json.loads(diag_path.read_text(encoding="utf-8"))
                gt = load_gt_map(op_root).get(folder, {})
                sc = score_case(gt, diagnosis)
                row = {
                    "op": op_name,
                    "folder": folder,
                    "ground_truth": gt,
                    "score": sc,
                    "error": None,
                    "resumed": True,
                    "note": "GT used only offline; not sent to GLM",
                }
                rows.append(row)
                print(f"GT={gt.get('problem_id')} fam_hit={sc['family_hit']} id_hit={sc['id_hit']}", flush=True)
                continue
            except Exception as exc:  # noqa: BLE001
                print(f"resume reload failed, re-running: {exc}", flush=True)

        if not case_dir.is_dir():
            print(f"skip missing {op_name}/{folder}", flush=True)
            continue
        if ".ground_truth" in case_dir.parts:
            raise SystemExit("refuse GT path")

        print(f"\n===== {op_name}/{folder} =====", flush=True)
        blind_path = case_out / "blind_input.json"
        blind = build_blind_input(case_dir, blind_path, f"{op_name}_{folder}")
        assert_no_gt_leak(blind)

        user = (
            "请依据已加载的 ascendc-aprof-diagnosis skill，对以下盲诊输入做单 kernel 独立诊断。"
            "只输出 single_case_diagnosis.json，不要 markdown 围栏。\n\n"
            + json.dumps(blind, ensure_ascii=False, indent=2)
        )
        try:
            raw = call_glm(api_key, model, url, system, user)
            (case_out / "glm_raw_response.json").write_text(
                json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            content = extract_content(raw)
            (case_out / "glm_raw_content.txt").write_text(content, encoding="utf-8")
            diagnosis = parse_json_loose(content)
            diag_path.write_text(json.dumps(diagnosis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            err = None
        except Exception as exc:  # noqa: BLE001
            diagnosis = {"diagnoses": []}
            err = str(exc)
            print(f"ERROR {op_name}/{folder}: {err}", flush=True)

        gt = load_gt_map(op_root).get(folder, {})
        sc = score_case(gt, diagnosis)
        row = {
            "op": op_name,
            "folder": folder,
            "ground_truth": gt,
            "score": sc,
            "error": err,
            "resumed": False,
            "note": "GT used only offline; not sent to GLM",
        }
        (case_out / "offline_alignment.json").write_text(
            json.dumps(row, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        rows.append(row)
        print(
            f"GT={gt.get('problem_id')} fam_hit={sc['family_hit']} id_hit={sc['id_hit']} "
            f"top1={sc['top1_family']}",
            flush=True,
        )
        # incremental summary for long runs
        _write_summary(out_dir, model, rows, args.bench_root or args.op_root)
        time.sleep(args.sleep)

    _write_summary(out_dir, model, rows, args.bench_root or args.op_root)
    n = len(rows)
    fam = sum(1 for r in rows if r["score"]["family_hit"])
    pid = sum(1 for r in rows if r["score"]["id_hit"])
    print(f"\n[done] family_hit={fam}/{n} id_hit={pid}/{n} out={out_dir}", flush=True)
    return 0


def _write_summary(out_dir: Path, model: str, rows: list[dict[str, Any]], root: Path) -> None:
    n = len(rows)
    fam = sum(1 for r in rows if r["score"]["family_hit"])
    pid = sum(1 for r in rows if r["score"]["id_hit"])
    summary = {
        "root": str(root),
        "model": model,
        "skill": "ascendc-aprof-diagnosis",
        "skill_files_loaded": list(SKILL_FILE_CAPS.keys()),
        "n_cases": n,
        "family_hit_rate": (fam / n) if n else 0.0,
        "id_hit_rate": (pid / n) if n else 0.0,
        "family_hits": fam,
        "id_hits": pid,
        "cases": rows,
        "policy": {
            "ground_truth_in_model_prompt": False,
            "blind_input_builder": str(BUILD_BLIND),
            "answers_only_offline": True,
        },
    }
    (out_dir / "batch_accuracy_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    md = [
        "# GLM Blind Diagnosis Batch Accuracy",
        "",
        f"- root: `{root}`",
        f"- model: `{model}`",
        f"- skill: `ascendc-aprof-diagnosis`",
        f"- cases: **{n}**",
        f"- family hit: **{fam}/{n}** ({summary['family_hit_rate']:.0%})",
        f"- problem-id hit (heuristic): **{pid}/{n}** ({summary['id_hit_rate']:.0%})",
        "",
        "| op | case | GT family | GT id | family hit | id hit | model top1 family |",
        "|----|------|-----------|-------|------------|--------|-------------------|",
    ]
    for r in rows:
        gt = r["ground_truth"]
        sc = r["score"]
        md.append(
            f"| {r.get('op','')} | {r['folder']} | {gt.get('problem_family','')} | {gt.get('problem_id','')} | "
            f"{'Y' if sc['family_hit'] else 'N'} | {'Y' if sc['id_hit'] else 'N'} | "
            f"{sc.get('top1_family') or '-'} |"
        )
    md.extend(
        [
            "",
            "## Anti-leakage",
            "",
            "- Model only sees sanitized `blind_input.json` (kernel + neutral metadata).",
            "- `.ground_truth/case_problem_map.json` is read only after inference for scoring.",
            "- Case folders are anonymous `op_XXXX` with no problem labels in names.",
            "",
        ]
    )
    (out_dir / "batch_accuracy_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
