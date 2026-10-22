import pathlib,json,math
base=pathlib.Path(__file__).resolve().parents[2]/'selection-regression-15/cases';n=0
for i in [6,8,9,10]:
 p=base/f'case-{i:02d}';ms=json.loads((p/'source/matrix-20.json').read_text())['cases'];rs=json.loads((p/'case-metrics-r1.json').read_text())['rows']
 for m,r in zip(ms,rs):
  if i==6:
   x,idx=m['input_shapes'];assert r['N']==math.prod(idx) and r['rank']==len(x) and r['inner']==idx[-1]
   assert r['source_shape']==x and r['index_shape']==idx
  if i==8:
   x,g=m['input_shapes'];assert r['N']==x[0] and r['C']==x[1] and r['S']==math.prod(g[1:-1])
   assert r['K']==(8 if m['interpolation_mode']=='bilinear' else 1)
  if i in [9,10]:
   N=math.prod(m['shape']);b=4 if m['dtype']=='float32' else 2;T=1024 if i==9 else 4096
   assert r['N']==N and r['useful_cores']==math.ceil(N/4096)
   assert r['explicit_ub_bytes']==((2*b+32)*T+256 if i==9 else (8 if b==4 else 12)*T)
  n+=1
p=base/'case-07';rs=json.loads((p/'case-metrics-r1.json').read_text())['rows'];r={x['case_id']:x for x in rs}
assert r['15']['base']==1024 and r['15']['source_steps']==[2048] and r['15']['N']==2048
assert r['14']['base']==512*1024 and r['14']['source_steps']==[1]
assert r['16']['output_shape']==[1,512,512] and r['16']['source_steps']==[0,512,1]
print('Verified',n,'B matrix-derived rows plus Slice shrink/new-axis boundary examples; no seed execution')
