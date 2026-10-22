CASES = [
 (1,[1024,16],'float16',2,[-1,1],False),(2,[16384,32],'float32',4,[-2,2],False),
 (3,[131072,64],'bfloat16',8,[-3,3],False),(4,[4,1024,128],'float16',16,[-10,10],False),
 (5,[8192,256],'float32',32,[-100,100],False),(6,[1024,16],'float16',2,[-1,1],True),
 (7,[4,1024,32],'float32',4,[-2,2],True),(8,[65536,64],'bfloat16',8,[-3,3],True),
 (9,[4096,512],'float16',64,[-1000,1000],False),(10,[2048,1024],'bfloat16',128,[-1,1],False),
 (11,[1009,32],'float16',4,[-10,10],False),(12,[2048,511],'float32',8,[-2,2],False),
 (13,[8,1009,127],'bfloat16',16,[-100,100],False),(14,[64,8],'float16',2,[-1,1],False),
 (15,[1024,4],'float32',2,[-.1,.1],False),(16,[512,16],'bfloat16',1,[-1,1],False),
 (17,[2048,256],'float16',8,[-65504,65504],False),(18,[4096,128],'float32',16,[-88,88],False),
 (19,[1024,32],'float16',4,[-.01,.01],False),(20,[512,64],'bfloat16',8,[0,0],False),
]
def get_case(case_id):
    for row in CASES:
        if row[0] == case_id:
            return dict(zip(('case_id','shape','dtype','k','value_range','has_finished'), row))
    raise ValueError(case_id)
