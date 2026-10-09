#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());boxes=np.fromfile(m['boxes'],np.float32).reshape(m['n'],4);scores=np.fromfile(m['scores'],np.float32);order=np.argsort(-scores,kind='stable');areas=(boxes[:,2]-boxes[:,0])*(boxes[:,3]-boxes[:,1]);suppressed=np.zeros(m['n'],bool);keep=[]
for i in order:
 if suppressed[i]:continue
 keep.append(int(i));xx1=np.maximum(boxes[i,0],boxes[:,0]);yy1=np.maximum(boxes[i,1],boxes[:,1]);xx2=np.minimum(boxes[i,2],boxes[:,2]);yy2=np.minimum(boxes[i,3],boxes[:,3]);inter=np.maximum(xx2-xx1,0)*np.maximum(yy2-yy1,0);iou=inter/(areas[i]+areas-inter+np.float32(1e-6));suppressed|=~(iou<=m['iou_threshold'])
gold=np.array(keep,np.int64);actual=np.fromfile(m['output'],np.int64);exact=np.array_equal(actual,gold);r={'case_id':m['case_id'],'n':m['n'],'iou_threshold':m['iou_threshold'],'expected_count':int(gold.size),'actual_count':int(actual.size),'exact_match':bool(exact),'mismatch_count':0 if exact else int(max(gold.size,actual.size)),'passed':bool(exact)};(mp.parent/'result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(0 if exact else 1)
