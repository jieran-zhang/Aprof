import copy,json,sys
from pathlib import Path
D=Path(__file__).parent; P=D.parent
R=Path('/mnt/tidalfs-hwwh01/dataset/dots_infra/workspace/jieran/APROF/aprof-maintenance-soft-targets-20261019/skill-libs/graph-base/1.3.0')
sys.path.insert(0,str(R/'runtime/src'))
from aprof_runtime import jsonio,bindings,action_decision,knowledge
A=json.loads((P/'runtime-artifacts.json').read_text()); G=A['diagnosis']; routing=bindings.load_routing(R,artifacts=A)
def read(n): return json.loads((D/n).read_text())
def dump(n,x): (D/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def ref(n): return {'path':n,'sha256':jsonio.file_hash(D/n)}
doc='skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/compare-select-tail.md'
maxdoc='skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/basic_arithmetic/Max.md'
PLAN='保留action.restructure_broadcast：按zero-stride位图合轴，每个owner与行交集只解码一次外轴并递增内轴地址。int32广播使用A3文档支持的int32 Max(count)，不走GT Compare/Select；FP32广播保留av>bv?av:bv条件，优先GT Compare(c)+Select模式2(n)，不预设Max等价。FP32输入只补[n,c)，predicate按32B分配，预留8192B Select临时区，只回写4n有效字节；短行同时比较按行解码后scalar条件选择。其它dtype/同形/既有half广播原样保留。'
SEM='已知原FP32条件是GT，false分支选择bv：相等及±0选择第二输入；任一NaN令GT为false，故av=NaN,bv有限时取bv，bv=NaN时取bv。FP32 Max的数学名称不能证明这些选择规则等价。GT+Select仅在实际SDK同重载支持、有效predicate与数据位保持、特殊值和原oracle一致性检查闭合后实施。原oracle调用torch.maximum并检查NaN/Inf掩码；NaN输入的原条件与oracle可能冲突，不能通过改oracle或宣称整个API已正确来消除。int32最大值无此浮点分支差异，A3 Max支持int32；A3 Compare int32仅EQ且Select仅half/float，禁止int32 GT+Select。'
CAP='FP32单槽保守峰值U=max_j(12*c_j+M_j+8192)+Bresident+Bother，c_j=64*ceil(n_j/64)，M_j=32*ceil(ceil(c_j/8)/32)。三个数据区独立且各c_j个float；predicate独立；8192B按非重叠生命周期复用。int32 U=3*A(4*T)+Bresident+Bother。实际UB容量与SDK未知，以U<=Uavailable为条件；多槽须重新计数，不默认alias。'
ALT='最强已注册替代仍为action.vectorize_scalar_loop：同样分别用FP32 GT+Select与int32 Max，减少N次scalar比较，但泛化逐元素收集仍保留N*rank地址解码和可能的Boffset/gather代价。它也必须支付FP32的padding、predicate、8192B及同步，不能因称为vectorize而免计。广播重构额外减少重复解码并复用zero-stride输入，故仍优先；短行是否批量化由新增成本决定，可保持广播重构但使用每行scalar条件选择。'
WORK='在所选广播子域减少N次scalar比较（有条件批量化路线）；新增Lbatch=sum_owner,row ceil(valid_owner_row/T)个批次。FP32每批Compare和Select各1次，Compare执行sum_j(c_j/64)个repeat；Select消费N个有效元素，逻辑repeat组sum_j ceil(n_j/64)另计。int32每批1次Max；各项不能与N相减或混合成时间。'
PROBE='反事实纸面probe，非实测：保持FP32输出总量近似不变，把完整行n=513改成37。独立单槽段预算由15200B变8992B，但每有效元素padding写由126/513变54/37，API批次数每元素约增513/37倍，固定8192B并未随有效数据缩小。Compare/Select可能失去对按行scalar条件选择的优势；仍可保留广播重构消除外轴解码，调整其计算路线。若合法压紧多行合并能减少发射，则重审pitch、predicate位偏移与owner后才采用，不以case ID设阈值。'
R2='R2按矩阵与dispatch新增区分：11/12/20为FP32广播，内轴513/37/101；13为int32广播，内轴256；18是已有half Vector，5/19为int64。完整行且未被owner截断时，FP32 c分别576/64/128，predicate M分别96/32/32B，单槽三数据区加predicate加Select8192B分别15200/8992/9760B，缺口padding写上界126/54/54元素，Compare repeats为9/1/2。上述均是纸面下界构造、未含额外驻留/其它区，不是实际容量或成绩。新增事实使37/101短行的按行scalar分支成为必须比较的实现参数；保留广播重构与其地址收益，撤回FP32无条件Max和统一UB公式。'
before={str(f.relative_to(P)):jsonio.file_hash(f) for i in [11,13,14,15] for f in (P/f'case-{i}').rglob('*') if f.is_file()}
receipt={'task_id':'autonomy-c-12','kind':'static_api_and_numeric_review','source_refs':[ref('source/op_kernel/maximum_kernel.asc'),ref('source/scripts/verify_result.py'),ref('source/scripts/gen_data.py'),ref('source/matrix-20.json')],'actual_readings':[{'document_ref':{'path':doc,'sha256':jsonio.file_hash(R/doc)},'locator':'lines:88-143','role':'FP32 GT Compare/Select tail, predicate, API scratch and semantic boundary'},{'document_ref':{'path':maxdoc,'sha256':jsonio.file_hash(R/maxdoc)},'locator':'lines:1-177','role':'A3 int32 Max support, count API; does not establish FP32 exceptional-value equivalence'}],'numeric_boundary':SEM,'budget':CAP,'plan_change':PLAN,'strongest_alternative':ALT,'counterfactual_probe':PROBE,'implemented':False,'measured':False}
# Exact locator for the full body actually read; no registration of a source extract as a knowledge record.
lines=(R/doc).read_text().splitlines(); receipt['actual_readings'][0]['locator']=f'lines:{lines.index("---",1)+2}-{len(lines)}'
dump('compare-select-review.json',receipt)
ev=read('r2-new-static-evidence.json'); ev['finding']=R2; ev['counterfactual_probe']=PROBE; ev['api_review_ref']=ref('compare-select-review.json')
ev['fp32_whole_row_paper_budgets']=[dict(case_id=k,n=n,c=((n+63)//64)*64,M=(((((n+63)//64)*64+7)//8+31)//32)*32,UB_base_bytes=12*(((n+63)//64)*64)+(((((n+63)//64)*64+7)//8+31)//32)*32+8192,padding_input_writes_upper=2*((((n+63)//64)*64)-n),compare_repeats=(n+63)//64,select_valid_elements=n,select_logical_repeat_groups=(n+63)//64) for k,n in [('11',513),('12',37),('20',101)]]
dump('r2-new-static-evidence.json',ev)
fs=['source.kernel','source.tiling','source.workload','source.api_review']
symbols={
 'N':('当前dtype子域全部输出元素数','elements'),'rank':('广播维数','axes'),'Rowner':('非空owner与行交集数；可能大于完整行数R','row-owner intersections'),
 'n_j':('第j个非空owner内行段的有效元素数，n_j<=T','elements'),'c_j':('FP32第j段Compare长度64*ceil(n_j/64)','elements'),'M_j':('predicate分配32*ceil(ceil(c_j/8)/32)','bytes'),
 'T':('候选最大有效段长，n=0跳过','elements'),'valid_owner_row':('一个owner与一行交集的有效长度','elements'),
 'Lbatch':('sum_owner,row ceil(valid_owner_row/T)，当前dtype子域的批次数','batches'),'Bresident':('额外独立广播源驻留区，不重复计算三数据区中展开的b','bytes'),'Bother':('其它真实分配/对齐和scratch；已列8192不重复计','bytes'),'Boffset':('泛化逐元素收集的额外偏移/索引区，若采用','bytes'),'A':('A(x)=32*ceil(x/32)字节对齐函数','bytes')}
def qty(expr,unit,names): return dict(mode='symbolic',expression=expr,unit=unit,symbols=[dict(name=n,meaning=symbols[n][0],unit=symbols[n][1]) for n in names],basis='inference',fact_ids=fs)
def work(id,expr,unit,names,why,change='added'): return dict(id=id,stage_id='kernel',domain_ids=['broadcast-scalar'],change=change,quantity=qty(expr,unit,names),explanation=why)
def cost(id,expr,names,why): return dict(id=id,domain_ids=['broadcast-scalar'],dimension='UB allocated bytes',change=qty(expr,'bytes',names),consequence=why)
def replace_refs(x):
 if isinstance(x,list): return [replace_refs(y) for y in x]
 if isinstance(x,dict):
  x={k:replace_refs(v) for k,v in x.items()}
  if x.get('path') in ['r2-new-static-evidence.json','compare-select-review.json']: x['sha256']=jsonio.file_hash(D/x['path'])
  return x
 return x
for rnd in [1,2]:
 rs=replace_refs(read(f'reasoning-r{rnd}.json'));dec=replace_refs(read(f'decision-r{rnd}.json'))
 fact=copy.deepcopy(rs['facts']['source.kernel']);fact['evidence_id']='compare-select-review.json@numeric_boundary,budget';fact['ref']={**ref('compare-select-review.json'),'locator':'numeric_boundary,budget'};rs['facts']['source.api_review']=fact
 for ins in rs['action_instances']:
  ins['parameters']['plan']=PLAN if ins['instance_id']=='I-primary' else ALT
  ins['parameters']['capacity_formula']=CAP+(' 泛化收集另加Boffset。' if ins['instance_id']=='I-alternative' else '')
  ins['parameters']['numeric_boundary']=SEM
 for cand in rs['candidates']:
  cand['reason']=PLAN if cand['hypothesis_id']=='H-primary' else ALT
  cand['mechanism']='每个非空owner与行交集一次rank解码，减少(N-Rowner)*rank轴处理；zero-stride源按行或窗口复用。' if cand['hypothesis_id']=='H-primary' else WORK
  if 'source.api_review' not in cand['support']: cand['support'].append('source.api_review')
 if rnd==2: rs['predecessor_ref']=ref('reasoning-r1.json')
 for op in dec['opportunities']:
  name=op['id']; primary=name=='primary';op['source_fact_ids']=fs;op['comparison']=ALT;op['reason']=PLAN if primary else ALT
  op['cost_mechanism']=('每个非空owner与行交集一次rank解码，减少(N-Rowner)*rank轴解码迭代，保留段内递增；zero-stride源按行/窗口复用。' if primary else WORK)
  op['predictions'][0]['statement']=op['cost_mechanism'];op['predictions'][1]['statement']='减少的源码工作能否抵消'+CAP+' 以及批次、padding、predicate、同步；未测。'
  for u in op['unknowns']:
   if u['fact']=='constraint.semantic_equivalence': u['statement']=SEM;u['affects']='FP32选择GT+Select或保留scalar；禁止未经证明的Max替换。int32独立Max路径。'
   elif u['fact']=='constraint.capacity':u['statement']=CAP;u['affects']='决定有效T、单槽能否成立、是否选择按行scalar，不推定设备容量。'
   elif u['fact']=='constraint.broadcast_semantics':u['statement']='逐行证明zero-stride地址、输入复用窗口、owner交集与尾写有效域；不能把带padding多行直接当有效连续数组。';u['affects']=PLAN
  retained=op['analysis']['work_delta'][-1]
  wd=[work(name+'-reduced','(N-Rowner)*rank' if primary else 'N','axis decode iterations' if primary else 'scalar comparisons',['N','Rowner','rank'] if primary else ['N'],'主方案减少每元素rank解码；owner切行按Rowner计，不假定核数。' if primary else '减少的是N次scalar比较；新增批次/API/repeat另列，绝不以N-Lbatch混减。','reduced')]
  if primary: wd.append(work(name+'-scalar-compares','N','scalar comparisons',['N'],'仅采用批量算术的dtype子域；短行scalar参数分支保留该项工作。','reduced'))
  wd += [
   work(name+'-batches','sum_owner,row ceil(valid_owner_row/T)','batches',['valid_owner_row','T'],'逐dtype统计Lbatch，不跨owner或行隐式拼接。'),
   work(name+'-fp32-calls','2*Lbatch','API calls',['Lbatch'],'仅FP32：每批GT Compare与Select模式2各一次。'),
   work(name+'-int32-calls','Lbatch','API calls',['Lbatch'],'仅int32：每批Max(count)一次；不适用Compare/Select成本。'),
   work(name+'-compare-repeats','sum_j(c_j/64)','Compare repeats',['c_j'],'仅FP32：256B=64 float的完整Compare执行组；不是运行测量。'),
   work(name+'-select-repeats','sum_j ceil(n_j/64)','Select logical repeat groups',['n_j'],'仅FP32：有效元素的256B逻辑分组；Select count=n_j，编译指令数未测。'),
   work(name+'-select-elements','N','selected elements',['N'],'仅FP32有效元素；不把c_j个padding元素写出。'),
   work(name+'-padding','2*sum_j(c_j-n_j)','input padding element writes upper bound',['c_j','n_j'],'仅FP32，最多补两个输入缺口；DataCopyPad32B不保证256B，已初始化缺口可扣除。'),
   work(name+'-predicate-produce','sum_j c_j','predicate bits produced',['c_j'],'仅FP32每个比较元素一bit；物理分配另计M_j，不能按元素字节误算。'),
   work(name+'-predicate-consume','N','valid predicate bits consumed',['N'],'仅FP32模式2逐repeat消费不同bit；实际物理读取不据此声称。'),
   work(name+'-tail-write','4*sum_j n_j','valid output bytes',['n_j'],'FP32与int32均4B，按所属子域统计；依赖完成后只写有效字节，padding不写GM。','retained'),retained]
  op['analysis']['work_delta']=wd
  op['analysis']['tradeoffs']=[cost(name+'-cost','max_j(12*c_j+M_j+8192)+Bresident+Bother'+(' + Boffset' if not primary else ''),['c_j','M_j','Bresident','Bother']+(['Boffset'] if not primary else []),'仅FP32、三个独立单槽数据区、一个predicate、非重叠段共用8192B临时区；必须<=Uavailable，实际容量未知。'+ALT),cost(name+'-int32-cost','3*A(4*T)+Bresident+Bother'+(' + Boffset' if not primary else ''),['A','T','Bresident','Bother']+(['Boffset'] if not primary else []),'仅int32 Max(count)，不移植FP32 predicate和8192B Select费用；具体API额外区与alignment仍需核对。')]
  # Cost of dependencies is structural, not an invented latency estimate.
  op['analysis']['tradeoffs'].append({'id':name+'-dependencies','domain_ids':['broadcast-scalar'],'dimension':'dependency and padding legality','change':{'mode':'qualitative','expression':'MTE2→V；Compare→Select predicate写读（同V管线依赖）；V→MTE3；如scalar填padding另闭合Scalar→Vector','unit':'ordering constraints','symbols':[],'basis':'inference','fact_ids':fs},'consequence':'不能无条件Duplicate(a[n],...,c-n)到未对齐尾址；选对齐尾片/合法mask/scalar填缺口。短行准备与同步成本可能支持按行scalar路线，未测耗时。'})
  for c in op['analysis']['coverage']:
   if c['domain_id']=='broadcast-scalar':c['region']='FP32 cases11/12/20：GT+Select条件计划；int32 case13：独立Max条件计划。只涵盖相应广播地址/数值域；短行scalar仍是计划参数，不计其比较已消除。';c['fact_ids']=fs
  op['analysis']['residuals'][0]['remaining_work']='同形Vector、既有half广播与int64原路径保持。FP32 exceptional-value/oracle边界未闭合；短行scalar分支保留比较，批量分支保留predicate、padding和依赖。泛化替代保留N*rank逐元素地址处理。'
 for req in dec['evidence_requests']:
  uid=req['unknown_ids'][0];u=next(u for op in dec['opportunities'] for u in op['unknowns'] if u['id']==uid)
  req['method']=u['statement'];req['finding']='已实际读取固定A3文档并定位原GT条件，具体结论见compare-select-review.json；实际SDK/UB与设备语义未核验。'
  req['discriminating_results']=[{'outcome':'实际SDK、地址、容量及原oracle特殊值边界闭合','decision_effect':'按FP32 GT+Select或int32 Max具体路线推进；不允许无证明FP32 Max'},{'outcome':'短行批量费用或合法性不成立','decision_effect':'保留广播重构，调整到每行scalar条件选择或合法压紧多行；不得放宽oracle'}]
 ku={'opportunity_ids':['primary','alternative'],'owner':'optimization','document_ref':{'path':doc,'sha256':jsonio.file_hash(R/doc)},'locator':receipt['actual_readings'][0]['locator'],'effect_kind':'plan','before':'原方案把FP32/int32统称Vector Max，且只算三数据区，遗漏Compare尾部和Select临时区。','after':PLAN+' '+CAP+' '+ALT,'applicability':'partial：完整采用A2/A3 memory-vector FP32 GT+Select合法尾部骨架；实际SDK待核对。int32仅采用此文的排除边界并结合已读Max来源证明支持，不套用GT+Select；其它dtype/同形路径不变。'}
 dec['knowledge_use']=[u for u in dec['knowledge_use'] if u['document_ref']['path']!=doc]+[ku]
 for u in dec['knowledge_use']:
  if u['owner']=='diagnosis':
   u['after']=(dec['opportunities'][0]['cost_mechanism'] if u['opportunity_ids']==['primary'] else WORK)+' 来源逻辑机制，不当作实测瓶颈；API路线和新增代价见compare-select-tail实际咨询。'
 dec['selection']['reason']='保留广播重构：地址解码和zero-stride复用优势仍成立；数值/API知识改变计算路线与预算，不构成必须换Action的理由。'+ALT+((' '+R2) if rnd==2 else '')
 dec['selection']['concrete_plan']=PLAN+((' '+R2) if rnd==2 else '')
 for basis in dec['selection']['comparison_basis']:
  if basis['role']=='benefit':basis['decision_effect']=dec['opportunities'][0]['cost_mechanism']
  elif basis['role']=='cost':basis['item_ids']=['primary-cost','primary-int32-cost','primary-dependencies'];basis['decision_effect']=CAP+' 批次、padding和predicate新增工作分别见work_delta，不混同字节预算。'
  elif basis['role']=='alternative':basis['item_ids']=['alternative-reduced','alternative-cost','alternative-batches','alternative-compare-repeats','alternative-select-repeats'];basis['decision_effect']=ALT
  basis['reversal_condition']=PROBE
 if rnd==2:
  fb=dec['previous_feedback'];fb['previous_decision_ref']=ref('decision-r1.json');fb['same_action_reason']=ALT;fb['new_information']=R2
  fb['reassessment']['mechanisms'][0]['finding']=R2
  fb['reassessment']['next_step'].update(retained=PLAN,reopened=R2,reason=ALT)
 dump(f'reasoning-r{rnd}.json',rs);dec['reasoning_ref']=ref(f'reasoning-r{rnd}.json');dec['reasoning_hash']=jsonio.content_hash(rs);dump(f'decision-r{rnd}.json',dec)
 inst=rs['action_instances'][0];row=next(x for x in routing['actions'] if x['action_id']==inst['action_id']);ctx=bindings.routing_context(R,rs,inst,task_root=D,artifact=G)
 route_refs=[]
 for owner,key in [('parallel-planning','planning_subtrees'),('optimization','optimization_subtrees')]:
  n=f'{owner}-action-consult-r{rnd}.json';dump(n,bindings.route_candidates(A[owner],ctx,row[key]));route_refs.append(ref(n))
 c1=read(f'C1-r{rnd}.json');c1['reasoning']=rs;c1['artifacts']=[ref(a['path']) for a in c1['artifacts']];c1['artifacts']=list({a['path']:a for a in c1['artifacts']}.values());dump(f'C1-r{rnd}.json',c1)
 con=read(f'consultation-r{rnd}.json');con['actual_body_readings']=[u for u in dec['knowledge_use'] if u['owner']!='diagnosis'];con['action_bound_route_refs']=route_refs;con['source_api_reading_ref']=ref('compare-select-review.json');dump(f'consultation-r{rnd}.json',con)
 knowledge.validate_schema(R,'knowledge-handoff-v3',c1)
 v=action_decision.validate_handoff_decision(R,c1,'I-primary',task_root=D,artifact=G,implementation=False,artifacts=A,routing_config=routing)
 dump(f'validation-r{rnd}.json',{'valid':True,'decision':v,'C1_sidecar':v});print('case12',rnd,'VALID',flush=True)
manifest=read('rounds.json')
for rnd in manifest['rounds']:
 for k,v in rnd.items():
  if isinstance(v,dict) and 'path' in v: rnd[k]=ref(v['path'])
dump('rounds.json',manifest)
summary=json.loads((P/'SUMMARY.json').read_text())
for c in summary['cases']:
 if c['case']=='case-12':c['manifest_ref']['sha256']=jsonio.file_hash(D/'rounds.json')
(P/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
for f,h in before.items(): assert jsonio.file_hash(P/f)==h, f
dump('review-scope-verification.json',{'other_four_cases_unchanged':True,'checked_file_count':len(before),'other_case_hashes':before})
print('other four cases unchanged',len(before),'files',flush=True)
