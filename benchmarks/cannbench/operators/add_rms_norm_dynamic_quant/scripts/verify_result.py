#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np,torch

NP={'float16':np.float16,'bfloat16':np.uint16}
def torch_from(raw,dtype,shape):
    t=torch.from_numpy(raw.copy());return (t.view(torch.bfloat16) if dtype=='bfloat16' else t).reshape(shape)
def rel_stats(actual,expected):
    special=bool(torch.equal(torch.isnan(actual),torch.isnan(expected)) and torch.equal(torch.isposinf(actual),torch.isposinf(expected)) and torch.equal(torch.isneginf(actual),torch.isneginf(expected)))
    finite=torch.isfinite(actual)&torch.isfinite(expected)
    if finite.any():
        rel=(actual[finite].float()-expected[finite].float()).abs()/(expected[finite].float().abs()+1e-7)
        return special,float(rel.double().sum()),int(rel.numel()),float(rel.max())
    return special,0.,0,0.
def main():
    p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text())
    dt=m['dtype'];D=m['shape'][-1];rows=m['rows'];gamma_raw=np.fromfile(m['gamma'],dtype=NP[dt]);gamma=torch_from(gamma_raw,dt,[D]).float()
    chunk_rows=max(1,2_000_000//D);xout_rel_sum=scale_rel_sum=0.;xout_count=scale_count=0;xout_mare=scale_mare=0.;xout_special=scale_special=True
    y_bad=0;y_max=0;y_count=0
    with open(m['x1'],'rb') as f1,open(m['x2'],'rb') as f2,open(m['output_y'],'rb') as fy,open(m['output_xout'],'rb') as fxout,open(m['output_scale'],'rb') as fs:
      done=0
      while done<rows:
        r=min(chunk_rows,rows-done);count=r*D
        x1=torch_from(np.fromfile(f1,dtype=NP[dt],count=count),dt,[r,D]).float()
        x2=torch_from(np.fromfile(f2,dtype=NP[dt],count=count),dt,[r,D]).float()
        actual_y=torch.from_numpy(np.fromfile(fy,dtype=np.int8,count=count).copy()).reshape(r,D)
        actual_xout=torch_from(np.fromfile(fxout,dtype=NP[dt],count=count),dt,[r,D])
        actual_scale=torch.from_numpy(np.fromfile(fs,dtype=np.float32,count=r).copy())
        xsum=x1+x2;variance=xsum.pow(2).mean(-1,keepdim=True);ynorm=xsum/torch.sqrt(variance+m['epsilon'])*gamma
        scale=ynorm.abs().amax(-1,keepdim=True).clamp(min=1e-12)/127.;expected_y=torch.clamp(torch.round(ynorm/scale),-128,127).to(torch.int8)
        expected_xout=xsum.to(torch.bfloat16 if dt=='bfloat16' else torch.float16);expected_scale=scale.squeeze(-1).float()
        diff=(actual_y.to(torch.int16)-expected_y.to(torch.int16)).abs();y_bad+=int((diff>1).sum());y_max=max(y_max,int(diff.max())) if diff.numel() else y_max;y_count+=count
        s,rs,c,mx=rel_stats(actual_xout,expected_xout);xout_special &= s;xout_rel_sum+=rs;xout_count+=c;xout_mare=max(xout_mare,mx)
        s,rs,c,mx=rel_stats(actual_scale,expected_scale);scale_special &= s;scale_rel_sum+=rs;scale_count+=c;scale_mare=max(scale_mare,mx)
        done+=r
    xout_threshold={'float16':2**-10,'bfloat16':2**-7}[dt];scale_threshold=2**-13
    xout_mere=xout_rel_sum/max(1,xout_count);scale_mere=scale_rel_sum/max(1,scale_count)
    passed=bool(y_count==m['numel'] and y_bad==0 and xout_special and scale_special and xout_mere<xout_threshold and xout_mare<10*xout_threshold and scale_mere<scale_threshold and scale_mare<10*scale_threshold)
    result={'case_id':m['case_id'],'shape':m['shape'],'dtype':dt,'epsilon':m['epsilon'],'numel':m['numel'],'y_max_abs_error':y_max,'y_elements_over_tolerance':y_bad,'y_tolerance':1,
            'xout_mere':xout_mere,'xout_mare':xout_mare,'xout_special_values_match':xout_special,'xout_threshold':xout_threshold,'scale_mere':scale_mere,'scale_mare':scale_mare,'scale_special_values_match':scale_special,'scale_threshold':scale_threshold,'passed':passed}
    (mp.parent/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));
    if not passed:raise SystemExit(1)
if __name__=='__main__':main()
