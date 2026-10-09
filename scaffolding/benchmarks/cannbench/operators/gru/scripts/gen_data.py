#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
import torch
from cases import get_case
p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case);d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);torch.manual_seed(20260812+a.case);attrs=c['attrs'];dtype={'float16':torch.float16,'bfloat16':torch.bfloat16,'float32':torch.float32}[c['dtype'][0]];sh=c['input_shape'];vr=c['value_range']
def make(name,shape,r):
 t=torch.empty(shape,dtype=torch.float32).uniform_(float(r[0]),float(r[1])).to(dtype).contiguous();path=(d/f'{name}.bin').resolve();path.write_bytes(t.view(torch.uint8).numpy().tobytes());return t,str(path)
x,xp=make('x',sh[0],vr[0]);wis=[];wips=[];whs=[];whps=[]
for j,s in enumerate(sh[1]):t,q=make(f'weight_ih_{j}',s,vr[1][j]);wis.append(t);wips.append(q)
for j,s in enumerate(sh[2]):t,q=make(f'weight_hh_{j}',s,vr[2][j]);whs.append(t);whps.append(q)
bis=[];bips=[];bhs=[];bhps=[]
if attrs['bias']:
 for j,s in enumerate(sh[3]):t,q=make(f'bias_ih_{j}',s,vr[3][j]);bis.append(t);bips.append(q)
 for j,s in enumerate(sh[4]):t,q=make(f'bias_hh_{j}',s,vr[4][j]);bhs.append(t);bhps.append(q)
h0=h0p=None
if len(sh)>5 and sh[5] is not None:h0,h0p=make('h0',sh[5],vr[5])
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'third_party/cann-bench/tasks/level4/gru'));from golden import gru
with torch.no_grad():y,hn=gru(x,wis,whs,bias_ih=bis or None,bias_hh=bhs or None,h0=h0,**attrs)
yp=(d/'expected_y.bin').resolve();hp=(d/'expected_hn.bin').resolve();yp.write_bytes(y.contiguous().view(torch.uint8).numpy().tobytes());hp.write_bytes(hn.contiguous().view(torch.uint8).numpy().tobytes());S=(sh[0][1] if attrs['batchFirst'] else sh[0][0]);B=(sh[0][0] if attrs['batchFirst'] else sh[0][1]);D=2 if attrs['bidirectional'] else 1;yshape=([B,S,D*attrs['hiddenSize']] if attrs['batchFirst'] else [S,B,D*attrs['hiddenSize']]);m={'case_id':a.case,'dtype':c['dtype'][0],'note':c['note'],'attrs':attrs,'x_shape':sh[0],'y_shape':yshape,'hn_shape':[attrs['numLayers']*D,B,attrs['hiddenSize']],'x':xp,'weight_ih':wips,'weight_hh':whps,'bias_ih':bips,'bias_hh':bhps,'h0':h0p,'expected_y':str(yp),'expected_hn':str(hp),'y':str((d/'y.bin').resolve()),'hn':str((d/'hn.bin').resolve())};(d/'metadata.json').write_text(json.dumps(m,indent=2));print(d/'metadata.json')
