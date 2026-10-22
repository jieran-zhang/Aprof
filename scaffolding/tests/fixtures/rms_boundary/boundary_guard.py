#!/usr/bin/env python3
"""Prepare independent semantic guard vectors or verify coordinator-produced outputs.

This utility never invokes an accelerator. It records only CPU dispatch/reference
checks by default. --verify consumes files from a separate coordinator hardware run.
"""
import argparse,json,math,sys
from pathlib import Path
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[7]
sys.path.insert(0,str(ROOT/'src'))
from aprof_runtime.planning import select_dispatch
sys.path.insert(0,str(ROOT/'scripts'))
from level2_adapters import workload_metadata


def norm_metadata(op,c):
 # Reuse the coordinator's semantic-only descriptor; no parallel copy of its formulas.
 raw={'dtype':c['dtype']}
 if op=='maximum':raw['input_shapes']=c['shapes']
 else:
  raw['shape']=c['shape']
  if op!='rms_norm':raw['attrs']={'dim':c['dim']}
 return workload_metadata(op,raw)


def values(c,shape,which='values'):
 n=math.prod(shape);dtype=getattr(torch,c['dtype'])
 data=c.get(which)
 if data is not None:
  data=[{'nan':float('nan'),'inf':float('inf'),'-inf':-float('inf')}.get(v,v) if isinstance(v,str) else v for v in data]
  return torch.tensor(data,dtype=dtype).reshape(shape)
 if c.get('pattern')=='argmax_boundary':
  x=torch.full((n,),-3.,dtype=dtype);x[8191]=5.;x[8192]=5.;return x.reshape(shape)
 # Deterministic nonrandom vectors independent of CANNBench generators/seeds.
 x=(torch.arange(n,dtype=torch.int64)*17%31)-15
 if dtype.is_floating_point:x=x.float()/8
 if which=='b':x=-x+1
 return x.to(dtype).reshape(shape)


def raw_write(p,x):
 x=x.contiguous().cpu()
 if x.dtype==torch.bfloat16:x.view(torch.int16).numpy().tofile(p)
 else:x.numpy().tofile(p)


def raw_read(p,dtype,shape):
 d={'float16':np.float16,'float32':np.float32,'bfloat16':np.uint16,'int8':np.int8,'int32':np.int32,'int64':np.int64}[dtype]
 a=np.fromfile(p,dtype=d)
 if a.size!=math.prod(shape):raise ValueError('output length differs')
 x=torch.from_numpy(a.copy())
 if dtype=='bfloat16':x=x.view(torch.bfloat16)
 return x.reshape(shape)


def compare(op,dtype,actual,expected):
 if op=='arg_max' or not expected.dtype.is_floating_point:return bool(torch.equal(actual,expected))
 if not (torch.equal(actual.isnan(),expected.isnan()) and torch.equal(actual.isposinf(),expected.isposinf()) and torch.equal(actual.isneginf(),expected.isneginf())):return False
 mask=expected.isfinite()
 if not mask.any():return True
 err=(actual[mask].float()-expected[mask].float()).abs();rel=err/(expected[mask].float().abs()+1e-7)
 if op=='softmax' and dtype=='float16':rel[err<=2**-24]=0
 threshold={'float16':2**-10,'float32':2**-13,'bfloat16':2**-7}[dtype]
 return bool(rel.double().mean()<threshold and rel.max()<10*threshold)


def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path);p.add_argument('--verify',action='store_true');p.add_argument('--plan',type=Path);a=p.parse_args()
 agent=Path(__file__).resolve().parent;spec=json.loads((agent/'boundary_cases.json').read_text());op=spec['operator'];plan=json.loads((a.plan or agent/'dispatch_plan.proposed.json').read_text());out=a.output or agent/'boundary_inputs';out.mkdir(parents=True,exist_ok=True)
 results=[];commands=[]
 for c in spec['cases']:
  folder=out/c['name'];folder.mkdir(exist_ok=True);meta=norm_metadata(op,c);selected=select_dispatch(plan,meta)
  expected_keys={'maximum':{'int64_extremes':2,'half_general_broadcast':0,'nan_both_operands':1,'tail_before_tile':1,'tail_after_tile':1},'rms_norm':{'hidden_127':10,'hidden_128':10,'hidden_129':11,'zero_row':10,'special_short_row':10,'capacity_edge':11},'arg_max':{'int64_upper_bits':0,'int32_float_rounding':0,'integer_strided':0,'first_nan_and_tie':31,'chunk_boundary_tie_nan':31,'strided_mask_tail':32},'softmax':{'inner_below_lanes':0,'inner_lane_tail':21,'short_threshold_before':22,'short_threshold_after':20,'special_rows':22,'underflow_half':22}}
  expected_key=expected_keys[op].get(c['name'])
  if op=='rms_norm' and c['shape'][-1]==2:expected_key=12 if any(e['tiling_key']==12 for e in plan['entries']) else 10
  assert selected['tiling_key']==expected_key,(op,c['name'],selected)
  # Tensor contents, generator/range and benchmark identity cannot enter metadata.
  c2={**c,'case_id':98765,'value_range':['secret'], 'seed':0};assert norm_metadata(op,c2)==meta
  if op=='maximum':
   x=values(c,c['shapes'][0],'a');y=values(c,c['shapes'][1],'b');expected=torch.maximum(x,y)
   raw_write(folder/'x1.bin',x);raw_write(folder/'x2.bin',y)
   args=['--x1-shape',','.join(map(str,c['shapes'][0])),'--x2-shape',','.join(map(str,c['shapes'][1])),'--x1',str(folder/'x1.bin'),'--x2',str(folder/'x2.bin')]
  else:
   x=values(c,c['shape']);raw_write(folder/'input.bin',x)
   args=['--shape',','.join(map(str,c['shape']))]
   if op=='rms_norm':
    gamma=torch.linspace(.75,1.25,c['shape'][-1]).to(x.dtype);raw_write(folder/'gamma.bin',gamma)
    expected=(x.float()*torch.rsqrt((x.float()*x.float()).mean(dim=-1,keepdim=True)+c['epsilon'])*gamma.float()).to(x.dtype)
    args+=['--x',str(folder/'input.bin'),'--gamma',str(folder/'gamma.bin'),'--epsilon',str(c['epsilon'])]
   elif op=='softmax':
    expected=torch.softmax(x,dim=c['dim']);args+=['--input',str(folder/'input.bin'),'--dim',str(c['dim'])]
   else:
    expected=torch.argmax(x,dim=c['dim']);args+=['--input',str(folder/'input.bin'),'--dim',str(c['dim']),'--keepdim','0']
  raw_write(folder/'expected.bin',expected)
  args+=['--dtype',c['dtype'],'--output',str(folder/'output.bin'),'--device','0']
  result={'name':c['name'],'dispatch':selected,'expected_shape':list(expected.shape),'status':'cpu_reference_prepared_not_hardware_verified'}
  if op=='arg_max' and c['name']=='int64_upper_bits':assert expected.tolist()==[3,2]
  if op=='arg_max' and c['name']=='int32_float_rounding':assert expected.tolist()==[1,2] and torch.argmax(x.float(),dim=-1).tolist()!=expected.tolist()
  if a.verify:
   actual=raw_read(folder/'output.bin','int64' if op=='arg_max' else c['dtype'],list(expected.shape));result['passed']=compare(op,c['dtype'],actual,expected);result['status']='hardware_output_verified' if result['passed'] else 'hardware_output_failed'
  commands.append({'name':c['name'],'argv':args,'expected_key':selected['tiling_key'],'reference':str(folder/'expected.bin')});results.append(result)
 # Threshold neighbors beyond benchmark matrix, with fallback on missing attributes.
 fallback=select_dispatch(plan,{'shape':[3,5],'dtype':'float32','layout':'ND','attributes':{}});assert fallback['fallback']
 (out/'coordinator_commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 (out/('verification.json' if a.verify else 'cpu_preparation.json')).write_text(json.dumps({'operator':op,'hardware_executed_by_this_script':False,'results':results},indent=2)+'\n')
 print(json.dumps({'operator':op,'cases':len(results),'mode':'verify_existing_outputs' if a.verify else 'cpu_only','passed':all(r.get('passed',True) for r in results)}))
 if any(not r.get('passed',True) for r in results):raise SystemExit(1)
if __name__=='__main__':main()
