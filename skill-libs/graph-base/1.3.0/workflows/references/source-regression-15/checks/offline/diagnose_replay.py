import argparse,json,pathlib,sys
p=argparse.ArgumentParser();p.add_argument('--root');p.add_argument('--out');a=p.parse_args();root=pathlib.Path(a.root);out=pathlib.Path(a.out)
sys.path.insert(0,str(root/'runtime/src'))
from aprof_runtime import diagnosis
from aprof_runtime.diagnosis_retrieval import validate_expansion

def read(p):return json.loads(p.read_text())
def diffs(old,new,path='$'):
 if type(old)!=type(new):return [{'path':path,'saved':old,'replayed':new}]
 if isinstance(old,dict):
  result=[]
  for k in sorted(old.keys()|new.keys()):
   if k not in old or k not in new:result.append({'path':path+'/'+k,'saved':old.get(k),'replayed':new.get(k)})
   else:result+=diffs(old[k],new[k],path+'/'+k)
  return result
 if isinstance(old,list):
  if len(old)!=len(new):return [{'path':path,'saved':old,'replayed':new}]
  return [d for i,(x,y) in enumerate(zip(old,new)) for d in diffs(x,y,path+'/'+str(i))]
 return [] if old==new else [{'path':path,'saved':old,'replayed':new}]
base=root/'workflows/references/source-regression-15';inv=read(base/'inventory.json');graph=diagnosis.verify(root);results=[]
for task in inv['tasks']:
 if task['case'] not in {'case-01','case-08','case-14'}:continue
 td=base/task['path'];saved=read(td/task['retrieval_ref']['path']);exp=read(td/task['expansion_ref']['path'])
 for rnd in task['rounds']:
  dec=read(td/rnd['decision_ref']['path']);rea=read(td/dec['reasoning_ref']['path']);actual=diagnosis.retrieve(graph,rea['context_snapshot'],root);ds=diffs(saved,actual)
  try:validate_expansion(graph,rea['context_snapshot'],exp,root);estate='pass'
  except Exception as e:estate=repr(e)
  row={'case':task['case'],'round':dec['round'],'task_path':str(td),'retrieval_ref':task['retrieval_ref'],'decision_ref':rnd['decision_ref'],'context_hash':rea['context_hash'],'differences':ds,'expansion_validation':estate};results.append(row)
  print(json.dumps({'case':row['case'],'round':row['round'],'context_hash':row['context_hash'],'difference_count':len(ds),'differences':ds[:12],'expansion_validation':estate},ensure_ascii=False),flush=True)
(out/'replay-differences.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
