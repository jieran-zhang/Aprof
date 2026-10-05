#!/usr/bin/env python3
"""Fresh ephemeral worker fallback when the parent collaboration thread pool is full."""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from collect_level1_traces import Campaign, ROOT
from run_aprof_job import dump, now


def run_worker(operator, candidate_target=3):
    c=Campaign(); task=c.task(operator); work=task/'isolated-worker'
    work.mkdir(exist_ok=True)
    if (work/'execution.json').exists():
        raise FileExistsError('worker already ran; do not silently duplicate a frozen search')
    prompt=f'''You are a fresh isolated AProf optimization worker for operator {operator} only.
Read {task / 'worker_context.json'} and {task / 'knowledge/manifest.json'}.
The user explicitly authorizes this optimization campaign. Read AGENTS.md if applicable.
Use the manifest's AProf workflow, diagnosis, profiling, optimization skills, relevant reference and at most one playbook. Record actual knowledge reads via {ROOT / 'scripts/prepare_level1_knowledge.py'} read_reference API/CLI. Do not read other operator source outcomes or performance; this is a split-isolated context.
Your read-only starting operator is {task / 'baseline'}. It was compiled and passed all 20 correctness cases. Actual baseline msprof CSV evidence for sentinel cases 1,8,14,20 is at {task / 'profiles/baseline'}. Read real CSVs including filenames with timestamps and retain units. Explicit (%) values are always percent, even below one. Hardware: CANN9.0, Ascend910_9392, 48 AIV / 24 AIC, measured UB 196352 bytes. No automatic graph predicate extractor is implemented; distinguish measured evidence, source reasoning and heuristics.
Your bounded assignment: implement approximately {candidate_target} independent, meaningful atomic optimization hypotheses, each derived from the identical original baseline. Copy to {task / 'candidates'}/001/op, 002/op, etc, excluding build/, results and temporary data. Never modify baseline, oracle, timer header, prepared harness or host CLI contract. You may modify actual kernel/tiling/host implementation and CMake only as required by a mechanism. All data types, shapes, attributes and special values retain the task contract. No case-ID specialization.
Do not run compilation, NPU, profiler, timing, or any hardware command. Parent controller executes and records these. Do not spawn agents. Maximum budget: 6 candidates and builds, 6 timing groups, 3 candidate full profiles. A source repair counts as a new candidate. All 20 cases get correctness; only sentinel case performance is visible during search. Freeze all candidate sources and plans before parent final 20-case performance; no source edits after freezing.
For each directory create candidate_plan.json with global candidate_id "{operator}-001" (etc), mode "exploration" unless you have a fully validated actual graph route and all transformation.required_evidence predicates. Do not synthesize a route, edge, propensity, or successful verdict. Most honest graph coverage gaps are valid exploration. Required plan fields: handler_id, handler_version("1.0.0"), intent, rationale, parameters(object), expected_effects(array of strings), alternatives(array of strings), coverage_gap(string for exploration), source_anchors(array of paths/anchors), supporting_evidence(array of existing paths), contradicting_evidence(array of strings), missing_evidence(array of strings), mechanisms(array of strings), static_review(object with precise memory/safety/semantic reasoning), parent_attempt_id(null for same-baseline independent attempts).
Write diagnosis.json summarizing performance problem, supporting and opposing raw measurements with CSV paths/fields/units, expected intervention effects and limits. Write source_freeze.json listing SHA256 of all candidate source files and frozen candidate plans. Do only these local task changes. Finish with candidate locations and concise implementation/risk notes; do not claim measured gains. Parent will execute the real gates. Source and observation rationale should be concise and reviewable; do not write private chain-of-thought transcripts into optimization summaries.
'''
    prompt_path=work/'prompt.txt'; prompt_path.write_text(prompt)
    argv=['codex','exec','--ephemeral','--json','-C',str(ROOT),'-s','danger-full-access',
          '-c','approval_policy="never"','--output-last-message',str(work/'result.md'),'-']
    report={'schema_version':'1.0.0','kind':'isolated_operator_worker','operator':operator,
            'split':c.split(operator),'argv':argv,'cwd':str(ROOT),'started_at':now(),
            'prompt_path':str(prompt_path),'prompt_sha256':'sha256:'+hashlib.sha256(prompt.encode()).hexdigest(),
            'context_policy':'fresh ephemeral CLI; only task manifest and own source/profile inputs',
            'reason':'collaboration.spawn_agent returned agent thread limit reached'}
    dump(work/'launch.json',report)
    with prompt_path.open() as stdin,(work/'worker_events.jsonl').open('w') as stdout,(work/'stderr.log').open('w') as stderr:
        result=subprocess.run(argv,stdin=stdin,stdout=stdout,stderr=stderr,cwd=ROOT)
    report.update(finished_at=now(),exit_status=result.returncode)
    dump(work/'execution.json',report)
    print(json.dumps(report,allow_nan=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('operator');parser.add_argument('--candidate-target',type=int,default=3)
    args=parser.parse_args();run_worker(args.operator,args.candidate_target)
