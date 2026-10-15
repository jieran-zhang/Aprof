#!/usr/bin/env python3
"""CPU-only setup or verification of coordinator-produced boundary outputs."""
from pathlib import Path
import argparse,json,sys,shutil
import numpy as np
ROOT=Path(__file__).resolve().parents[7]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from aprof_runtime.planning import select_dispatch
from level2_adapters import workload_metadata

def read(p,dtype):
 raw={'float16':np.float16,'float32':np.float32,'bfloat16':np.uint16,'int8':np.int8}
 v=np.fromfile(p,dtype=raw[dtype])
 return (v.astype(np.uint32)<<16).view(np.float32) if dtype=='bfloat16' else v

def compare(actual,expected,threshold,integer=False):
 if actual.shape!=expected.shape:return dict(passed=False,reason='output shape differs')
 if integer:
  error=np.abs(actual.astype(np.int16)-expected.astype(np.int16));return dict(passed=bool(np.all(error<=1)),max_absolute_error=int(error.max(initial=0)),threshold=1)
 special=bool(np.array_equal(np.isnan(actual),np.isnan(expected)) and np.array_equal(np.isposinf(actual),np.isposinf(expected)) and np.array_equal(np.isneginf(actual),np.isneginf(expected)))
 finite=np.isfinite(actual)&np.isfinite(expected);rel=np.abs(actual[finite].astype(np.float32)-expected[finite].astype(np.float32))/(np.abs(expected[finite].astype(np.float32))+1e-7)
 mere=float(rel.mean(dtype=np.float64)) if rel.size else 0.;mare=float(rel.max(initial=0))
 return dict(passed=bool(special and mere<threshold and mare<10*threshold),special_values_match=special,mere=mere,mare=mare,threshold=threshold)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);parser.add_argument('--verify',action='store_true');parser.add_argument('--plan',type=Path);args=parser.parse_args()
 agent=Path(__file__).resolve().parent;spec=json.loads((agent/'boundary_cases.json').read_text());op=spec['operator'];out=(args.output or agent/'boundary_inputs').resolve();out.mkdir(parents=True,exist_ok=True)
 plan=json.loads((args.plan or agent/'dispatch_plan.proposed.json').read_text());commands=[];results=[]
 for case in spec['cases']:
  source=agent/'boundary_inputs'/case['name'];dest=out/case['name'];dest.mkdir(exist_ok=True)
  guard=json.loads((source/'guard.json').read_text());descriptor=case['metadata'];rawmeta={**descriptor['attributes'],'shape':descriptor['shape'],'dtype':descriptor['dtype'],'attrs':descriptor['attributes']}
  meta=workload_metadata(op,rawmeta);selected=select_dispatch(plan,meta)
  assert selected['tiling_key']==case['expected_key'],(case['name'],meta,selected)
  assert workload_metadata(op,{**rawmeta,'case_id':987,'seed':123,'value_range':['unused']})==meta
  for item in source.glob('*.bin'):
   if item.name.startswith('output'):continue
   if item.resolve()!=(dest/item.name).resolve():shutil.copyfile(item,dest/item.name)
  argv=[value.replace(str(source),str(dest)).replace('{device}','0') for value in guard['native_arguments']]
  commands.append(dict(name=case['name'],argv=argv,expected_key=selected['tiling_key'],expected_entry=selected['kernel_entry'],reference=str(dest/'expected.bin'),metadata=meta))
  result=dict(name=case['name'],dispatch=selected,reference_status=guard['reference_status'],oracle=guard['oracle'],status='cpu_reference_prepared_not_hardware_verified')
  if args.verify:
   d=descriptor['dtype'];dt='int8' if op=='dynamic_quant' else d
   threshold=({'float32':.005,'float16':.01,'bfloat16':.01} if op=='apply_adam_w' else {'float32':.005,'float16':.005,'bfloat16':.01} if op=='group_norm' else {'float32':2**-13,'float16':2**-10,'bfloat16':2**-7})[d]
   result['output']=compare(read(dest/'output.bin',dt),read(dest/'expected.bin',dt),threshold,integer=op=='dynamic_quant')
   if op=='dynamic_quant':result['scale']=compare(read(dest/'output_scale.bin','float32'),read(dest/'expected_scale.bin','float32'),2**-13)
   result['passed']=result['output']['passed'] and result.get('scale',{'passed':True})['passed'];result['status']='coordinator_output_verified' if result['passed'] else 'coordinator_output_failed'
  results.append(result)
 (out/'coordinator_commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 (out/('verification.json' if args.verify else 'cpu_preparation.json')).write_text(json.dumps(dict(operator=op,hardware_executed_by_this_script=False,results=results),indent=2,allow_nan=False)+'\n')
 print(json.dumps(dict(operator=op,cases=len(results),mode='verify_existing_outputs' if args.verify else 'cpu_only',passed=all(r.get('passed',True) for r in results))))
 if any(not r.get('passed',True) for r in results):raise SystemExit(1)
if __name__=='__main__':main()
