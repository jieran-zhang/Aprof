#!/usr/bin/env python3
CASES = [
 (1,[1048576],'float16',[0],[524288],[2],{} ,[-1,1]),
 (2,[2048,2048],'float32',[0,0],[-1,-1],[1,1],{},[-2,2]),
 (3,[4096,4096],'bfloat16',[0,0],[2048,2048],[2,2],{},[-3,3]),
 (4,[8192,8192],'int32',[0,0],[-1,-1],[1,2],{},[-10000,10000]),
 (5,[4096,8192],'int64',[0,0],[8192,8192],[2,2],{},[-100000,100000]),
 (6,[8192,8192],'float32',[0,0],[-1,-1],[2,4],{},[-1000,1000]),
 (7,[1023,1023],'float16',[0,0],[-1,-1],[1,1],{},[-.1,.1]),
 (8,[1009,1021],'float32',[0,0],[500,500],[2,2],{},[-1,2]),
 (9,[1537,769],'bfloat16',[0,0],[-1,-1],[1,3],{},[-5,10]),
 (10,[363,367,373],'int32',[0,0,0],[100,100,100],[1,1,1],{},[-50,100]),
 (11,[1024,1024],'float16',[512,256],[1024,1024],[1,1],{'begin_mask':1},[-1,1]),
 (12,[2048,2048],'float32',[1024,512],[2048,2048],[2,2],{'begin_mask':3},[-2,2]),
 (13,[1024,1024],'bfloat16',[0,0],[512,256],[1,1],{'end_mask':1},[-3,3]),
 (14,[1024,1024],'float16',[512,0],[513,1024],[1,1],{'shrink_axis_mask':1},[-1,1]),
 (15,[2048,2048],'float32',[0,1024],[2048,1025],[1,1],{'shrink_axis_mask':2},[-2,2]),
 (16,[512,512],'bfloat16',[0,0],[512,512],[1,1],{'new_axis_mask':1},[-3,3]),
 (17,[1024,1024],'int32',[0,0],[1024,1024],[1,1],{'new_axis_mask':2},[-1000,1000]),
 (18,[1024,1024],'float16',[512,0],[513,512],[1,1],{'shrink_axis_mask':1,'end_mask':2},[-1,1]),
 (19,[512,512],'float32',[256,0],[257,512],[1,1],{'shrink_axis_mask':1,'new_axis_mask':2},[-2,2]),
 (20,[64,128,128,128],'bfloat16',[0,0,0,0],[64,-1,-1,-1],[1,1,1,1],{'ellipsis_mask':1},[-3,3]),
]

def get_case(case_id):
    names=('case_id','shape','dtype','begin','end','strides','masks','value_range')
    for row in CASES:
        if row[0] == case_id:
            c=dict(zip(names,row))
            for key in ('begin_mask','end_mask','ellipsis_mask','shrink_axis_mask','new_axis_mask'):
                c[key]=c['masks'].get(key,0)
            return c
    raise ValueError(f'unknown case {case_id}')

def layout(c):
    shape=c['shape']; begin=c['begin']; end=c['end']; strides=c['strides']
    xstep=[0]*len(shape); step=1
    for d in range(len(shape)-1,-1,-1): xstep[d]=step; step*=shape[d]
    new_count=sum((c['new_axis_mask']>>p)&1 for p in range(len(begin)))
    ep=next((p for p in range(32) if (c['ellipsis_mask']>>p)&1),None)
    ellipsis_dims=max(0,len(shape)-(len(begin)-new_count-1)) if ep is not None else 0
    out_shape=[]; source_step=[]; base=0; inp=0; param=0
    while inp<len(shape) or param<len(begin):
        if param<len(begin) and ((c['new_axis_mask']>>param)&1):
            out_shape.append(1); source_step.append(0); param+=1; continue
        if ep is not None and param==ep:
            for _ in range(ellipsis_dims):
                out_shape.append(shape[inp]); source_step.append(xstep[inp]); inp+=1
            param+=1; continue
        if inp<len(shape) and param<len(begin):
            dim=shape[inp]; s=strides[param]; b=begin[param]; e=end[param]
            if b<0: b+=dim
            if e<0: e+=dim
            if (c['begin_mask']>>param)&1: b=0 if s>0 else dim-1
            if (c['end_mask']>>param)&1: e=dim if s>0 else -1
            if (c['shrink_axis_mask']>>param)&1:
                base += b*xstep[inp]
            else:
                start,stop,stride=slice(b,e,s).indices(dim)
                size=len(range(start,stop,stride))
                if not size: raise ValueError('zero-sized output unsupported')
                base += start*xstep[inp]
                out_shape.append(size); source_step.append(stride*xstep[inp])
            inp+=1; param+=1
        elif inp<len(shape):
            out_shape.append(shape[inp]); source_step.append(xstep[inp]); inp+=1
        else: param+=1
    return out_shape,source_step,base
