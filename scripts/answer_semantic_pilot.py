"""New semantic check/repair calls over retained real tool outputs, not a new Agent run."""
from stardew_agent.core import *
from stardew_agent.agent import grounding_check,repair_answer,validate_answer
from stardew_agent.state import TaskStore
from stardew_agent.model import ModelClient
saved=read(ARTIFACTS/'agent_pilots/compose.json');original=saved['answer'];evidence={};calcs={c['run_id']:c for c in original['calculation_traces']}
for event in original['tool_events']:
    result=event['result']
    for key in ('facts','relations','evidence_refs'):
        for rec in result.get(key,[]):evidence[rec['id']]=rec
    if result.get('record',{}).get('id'):evidence[result['record']['id']]=result['record']
inputs=TaskStore().get(original['task_id'])['inputs'];model=ModelClient()
draft={k:original[k] for k in ('answer_text','claim_evidence_refs','calculation_trace_refs','unsupported_parts','status') if k in original}
first=grounding_check(model,draft,evidence,calcs,inputs)
repaired,repair=repair_answer(model,draft,evidence,calcs,inputs,extra_errors=first['issues'] if first['verdict']!='supported' else None)
last=grounding_check(model,repaired,evidence,calcs,inputs) if repair else first
numeric=validate_answer(repaired,evidence,calcs,inputs)
result={'status':'PASS_ENGINEERING_DIAGNOSTIC' if first['verdict']!='supported' and last['verdict']=='supported' and not numeric['invalid_references'] and not numeric['unsupported_numbers'] else 'PARTIAL',
 'execution_scope':'New model semantic verification and at most one repair. Earlier real tool outputs retained; not a new tool execution or human evaluation.',
 'original_task_id':original['task_id'],'original_draft':draft,'original_check':first,'repair':repair,'repaired_draft':repaired,'final_check':last,'numeric_validation':numeric,
 'human_approval':False,'formal_task_success':None,'limitations':['Model-assisted semantic checking can make mistakes; independent human references still required.']}
write(ARTIFACTS/'evaluation/answer_semantic_pilot.json',result)
print(canonical({'status':result['status'],'original_verdict':first['verdict'],'final_verdict':last['verdict'],'issues':first['issues'],'repaired_text':repaired['answer_text']}))
raise SystemExit(0 if result['status']=='PASS_ENGINEERING_DIAGNOSTIC' else 2)
