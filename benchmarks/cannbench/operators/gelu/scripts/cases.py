#!/usr/bin/env python3
CASES = [
 (1,[1024,1024],'float16','none',[-1.,1.]),
 (2,[2048,2048],'float32','none',[-2.,2.]),
 (3,[4096,4096],'bfloat16','none',[-3.,3.]),
 (4,[8192,8192],'float16','tanh',[-10.,10.]),
 (5,[8192,8192],'float32','tanh',[-100.,100.]),
 (6,[1023,1023],'bfloat16','tanh',[-.1,.1]),
 (7,[1009,1021],'float16','none',[-1.,2.]),
 (8,[1537,769],'float32','tanh',[-5.,10.]),
 (9,[363,367,373],'bfloat16','none',[-50.,100.]),
 (10,[2049,513],'float16','tanh',[-65504.,65504.]),
 (11,[3,7,13,4001],'float32','none',[-88.,88.]),
 (12,[1000003],'bfloat16','tanh',[-float('inf'),float('inf')]),
 (13,[11,13,17,67,67],'float32','none',[float('nan'),float('nan')]),
 (14,[3,7,11,13,1009],'float16','tanh',[0.,0.]),
 (15,[512,2049],'float32','none',[-.5,.5]),
 (16,[255,8193],'bfloat16','none',[-1.,3.]),
 (17,[4097,511],'float16','tanh',[-1000.,1000.]),
 (18,[2,511,2049],'float32','none',[-.2,.2]),
 (19,[4,255,2049],'bfloat16','tanh',[-3.,6.]),
 (20,[2,3,17,1024,101],'float32','none',[-20.,40.]),
]

def get_case(case_id):
    for row in CASES:
        if row[0] == case_id:
            return dict(zip(('case_id','shape','dtype','approximate','value_range'), row))
    raise ValueError(f'unknown case {case_id}')
