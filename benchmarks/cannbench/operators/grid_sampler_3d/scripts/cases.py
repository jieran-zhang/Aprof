#!/usr/bin/env python3
CASES = [
 (1,[[2,32,32,32,32],[2,32,32,32,3]],'float16','bilinear','zeros',False,[[-1,1],[-1,1]]),
 (2,[[4,64,16,16,16],[4,16,16,16,3]],'float32','bilinear','zeros',False,[[-2,2],[-1,1]]),
 (3,[[2,128,8,8,8],[2,8,8,8,3]],'float16','nearest','zeros',True,[[-3,3],[-1,1]]),
 (4,[[4,64,32,32,32],[4,32,32,32,3]],'float32','bilinear','border',True,[[-10,10],[-1,1]]),
 (5,[[2,128,64,64,64],[2,64,64,64,3]],'float16','nearest','reflection',False,[[-100,100],[-1,1]]),
 (6,[[4,256,32,32,32],[4,32,32,32,3]],'float32','bilinear','border',False,[[-1000,1000],[-1,1]]),
 (7,[[3,31,31,31,31],[3,31,31,31,3]],'float16','bilinear','zeros',False,[[-.1,.1],[-1,1]]),
 (8,[[2,63,15,15,15],[2,15,15,15,3]],'float32','nearest','zeros',True,[[-1,2],[-1,1]]),
 (9,[[3,47,23,23,23],[3,23,23,23,3]],'float16','bilinear','reflection',False,[[-5,10],[-1,1]]),
 (10,[[5,97,43,43,43],[5,43,43,43,3]],'float32','bilinear','zeros',True,[[-50,100],[-1,1]]),
 (11,[[2,33,33,33,33],[2,33,33,33,3]],'float16','bilinear','border',True,[[-65504,65504],[-1,1]]),
 (12,[[3,7,13,17,4001],[3,7,13,17,3]],'float32','nearest','zeros',False,[[-88,88],[-1,1]]),
 (13,[[2,31,31,31,31],[2,31,31,31,3]],'float16','bilinear','zeros',False,[[-float('inf'),float('inf')],[-1,1]]),
 (14,[[2,11,13,17,19],[2,11,13,17,3]],'float32','bilinear','zeros',False,[[float('nan'),float('nan')],[-1,1]]),
 (15,[[4,63,31,31,31],[4,31,31,31,3]],'float16','nearest','zeros',False,[[0,0],[0,0]]),
 (16,[[2,16,63,63,63],[2,16,63,63,3]],'float32','bilinear','zeros',False,[[-.5,.5],[-1,1]]),
 (17,[[3,63,63,127,127],[3,127,63,127,3]],'float16','bilinear','reflection',True,[[-1,3],[-1,1]]),
 (18,[[2,32,15,15,15],[2,15,15,15,3]],'float32','nearest','border',True,[[-1000,1000],[-1,1]]),
 (19,[[4,31,31,31,31],[4,31,31,31,3]],'float16','bilinear','zeros',True,[[-.2,.2],[-1,1]]),
 (20,[[2,63,63,127,127],[2,63,63,127,3]],'float32','bilinear','border',True,[[-3,6],[-1,1]]),
]

def get_case(case_id):
    for row in CASES:
        if row[0] == case_id:
            keys=('case_id','input_shapes','dtype','interpolation_mode','padding_mode','align_corners','value_ranges')
            return dict(zip(keys,row))
    raise ValueError(f'unknown case {case_id}')
