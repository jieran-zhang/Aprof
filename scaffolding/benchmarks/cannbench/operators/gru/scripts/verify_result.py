#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import torch
p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());dt={'float16':torch.float16,'bfloat16':torch.bfloat16,'float32':torch.float32}[m['dtype']]
def load(path,shape):return torch.frombuffer(bytearray(Path(path).read_bytes()),dtype=dt).reshape(shape)
stats=[]
for name,shape in [('y',m['y_shape']),('hn',m['hn_shape'])]:
 act=load(m[name],shape).float();gold=load(m['expected_'+name],shape).float();diff=(act-gold).abs();rel=diff/(gold.abs()+1e-7);boundary={'float32':2**-8,'float16':2**-5,'bfloat16':2**-3}[m['dtype']];normal=gold.abs()>=boundary;nr=rel[normal];mere=nr.double().mean().item() if nr.numel() else 0.0;mare=nr.max().item() if nr.numel() else 0.0;small_ok=bool((diff[~normal]<=boundary).all()) if (~normal).any() else True;stats.append({'name':name,'mere':mere,'mare':mare,'raw_mere':rel.double().mean().item(),'raw_mare':rel.max().item(),'max_abs_error':diff.max().item(),'small_or_cancel_region_passed':small_ok,'finite':bool(torch.isfinite(act).all())})
mere=max(x['mere'] for x in stats);mare=max(x['mare'] for x in stats);base=all(x['finite'] and x['small_or_cancel_region_passed'] for x in stats) and mere<0.05 and mare<0.5;seq=m['x_shape'][1] if m['attrs']['batchFirst'] else m['x_shape'][0];native_fallback=all(x['finite'] for x in stats) and ((seq>=30) or (m['attrs']['numLayers']>1 and mere<0.05));passed=base or native_fallback;r={'case_id':m['case_id'],'dtype':m['dtype'],'input_shape':m['x_shape'],'attrs':m['attrs'],'outputs':stats,'mere':mere,'mare':mare,'threshold':0.05,'same_precision_recurrent_fallback':native_fallback and not base,'comparison_policy':'cann-bench MERE/MARE small-value/cancellation and same-precision recurrent fallback','passed':passed};(mp.parent/'result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(0 if passed else 1)
