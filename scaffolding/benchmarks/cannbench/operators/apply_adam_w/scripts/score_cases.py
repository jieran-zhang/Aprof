#!/usr/bin/env python3
import argparse, json, pathlib


ROOT=pathlib.Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(); p.add_argument("--perf",default="docs/perf/round_001")
    p.add_argument("--metadata",default="../../../../third_party/cann-bench/tasks/metadata/910b2.json"); p.add_argument("--output",default="results.json")
    args=p.parse_args(); metadata=json.loads((ROOT/args.metadata).resolve().read_text())["level2"]["apply_adam_w"]
    cases=[]; passed=0; perf_count=0
    for cid in range(1,21):
        precision_path=ROOT/"build/cases"/f"case_{cid:02d}"/"precision.json"
        precision=json.loads(precision_path.read_text()) if precision_path.exists() else None
        perf_path=(ROOT/args.perf).resolve()/f"case_{cid:02d}"/"performance.json"
        perf=json.loads(perf_path.read_text()) if perf_path.exists() else None
        baseline=metadata[str(cid)]["baseline_perf_us"]; hw=metadata[str(cid)]["t_hw_us"]
        candidate=perf["task_duration_us"] if perf else None; score=None; status="pending"
        if candidate is not None:
            denom=(candidate-hw)+(baseline-hw)
            if denom>0: score=(baseline-hw)/denom; status="scored"; perf_count+=1
            else: status="invalid_denominator"
        if precision and precision["precision_pass"]: passed+=1
        cases.append({"case_id":cid,"precision":precision,"task_duration_us":candidate,"baseline_perf_us":baseline,
                      "t_hw_us":hw,"perf_score":score,"performance_status":status,
                      "profiler_source":perf.get("profiler_source") if perf else None})
    complete=passed==20 and perf_count==20
    torch_path=ROOT/"build/torch_results.json"
    torch_results=json.loads(torch_path.read_text()) if torch_path.exists() else []
    torch_passed=sum(bool(x.get("passed")) for x in torch_results)
    result={"operator":"apply_adam_w","environment":{"device":"Ascend 910","npu_arch":"dav-2201","cann":"9.0.0"},
      "build":{"status":"pass","command":"cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TORCH_EXTENSION=ON && cmake --build build -j4"},
      "correctness":{"status":"pass" if passed==20 else "pending_npu","passed":passed,"total":20,
                     "pytorch":{"passed":torch_passed,"total":20,"status":"pass" if torch_passed==20 else "pending"}},
      "performance":{"status":"measured_on_npu" if perf_count==20 else "pending_npu","measured_cases":perf_count,"total":20,
                     "operator_score":(0.2 + sum(0.3 + 0.5*c["perf_score"] for c in cases)/20)*100 if complete else None},
      "cases":cases}
    (ROOT/args.output).write_text(json.dumps(result,indent=2,ensure_ascii=False))
    perf_root=(ROOT/args.perf).resolve(); perf_root.mkdir(parents=True,exist_ok=True)
    lines=[f"apply_adam_w real-NPU performance: {perf_count}/20 measured",
           f"operator_score={result['performance']['operator_score']}",
           "device=0, npu_arch=dav-2201, CANN=9.0.0, warmup=3, repeat=5, aggregate=median"]
    for case in cases:
        lines.append(f"case {case['case_id']:02d}: task_duration_us={case['task_duration_us']} "
                     f"perf_score={case['perf_score']} source={case['profiler_source']}")
    (perf_root/"summary.txt").write_text("\n".join(lines)+"\n")
    print(json.dumps(result["performance"]))


if __name__=="__main__": main()
