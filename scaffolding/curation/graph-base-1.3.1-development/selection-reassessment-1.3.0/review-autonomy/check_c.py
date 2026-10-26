import pathlib,json,math
base=pathlib.Path(__file__).resolve().parents[2]/'selection-regression-15/cases';n=0
for i in range(11,16):
 p=base/f'case-{i}';ms=json.loads((p/'source/matrix-20.json').read_text())['cases'];rs=json.loads((p/'r2-new-static-evidence.json').read_text())['static_derived_table']
 for m,r in zip(ms,rs):
  if i==11:
   assert r['total_elements']==sum(math.prod(s) for s in m['shapes'])
   assert r['host_chunks']==sum(math.ceil(math.prod(s)/(8*1024*1024)) for s in m['shapes'])
   assert r['physical_data_UB']['2048']==(16 if m['dtype']=='float32' else 24)*2048
  if i==12:
   a,b=m['input_shapes'];rank=max(len(a),len(b));a=[1]*(rank-len(a))+a;b=[1]*(rank-len(b))+b;o=[max(x,y) for x,y in zip(a,b)]
   assert r['output_elements']==math.prod(o) and r['inner_length']==o[-1]
   assert r['x2_inner_zero_stride']==(b[-1]==1)
   assert r['scalar_dispatch']==(m['dtype']=='int64' or (a!=b and m['dtype']!='float16'))
  if i==13:
   shape=m['shape'];B=shape[0];S,H=(shape[1],shape[2]) if m['layout']==0 else (shape[2],shape[1]);D=shape[3]
   assert r['rows']==B*S*H and r['head_count']==H
   assert r['physical_data_UB']==D*(20 if m['dtype']=='float32' else 30)
   assert r['head_reuse_distance_rows']==(1 if m['layout']==0 else S)
  if i==14:
   sh=m['shape'];per=m['perm'];E=1
   for d in range(len(sh)-1,-1,-1):
    if per[d]!=d:break
    E*=sh[d]
   assert r['elements']==math.prod(sh) and r['preserved_suffix_elements']==E
  if i==15:
   sh=m['shape'];out=m['output_size'] or [math.floor(sh[2]*m['scale_factor'][0]),math.floor(sh[3]*m['scale_factor'][1])];S=math.prod(out);NC=math.prod(sh[:2]);N=S*NC
   assert r['output_elements']==N and r['unique_geometry_points']==S and r['logical_neighbor_requests']==4*N
  n+=1
print('Verified',n,'C matrix-derived rows against independent source formula calculations')
