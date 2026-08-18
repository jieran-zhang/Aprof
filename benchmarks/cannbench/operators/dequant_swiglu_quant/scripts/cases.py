CASES=[
([512,2048],'float16',True,False),([1024,4096],'float16',False,False),([2048,8192],'float16',True,True),([4096,4096],'bfloat16',False,True),([127,1024],'bfloat16',False,False),([8192,1024],'float16',False,True),([1023,4098],'bfloat16',True,False),([255,8194],'bfloat16',False,False),
([512,2048],'int32',True,False),([1024,4096],'int32',False,False),([2048,8192],'int32',True,True),([4096,4096],'int32',False,True),([127,1024],'int32',False,False),([8192,1024],'int32',False,True),([1023,4098],'int32',True,False),([255,8194],'int32',False,True),([10007,64],'int32',False,False),([32768,256],'int32',False,False),([4001,2048],'int32',True,True),([16384,512],'int32',False,False)]
def get_case(i):
 s,d,a,q=CASES[i-1];return {'case_id':i,'shape':s,'dtype':d,'activate_left':a,'has_quant_scale':q}
