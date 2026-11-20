import argparse,json
from stardew_agent.agent import Agent
from stardew_agent.core import *
p=argparse.ArgumentParser();p.add_argument('--task-id',required=True);p.add_argument('--message',required=True);a=p.parse_args()
r=Agent(max_rounds=10).run(a.task_id,a.message)
write(ARTIFACTS/'agent_pilots'/('continued-'+a.task_id+'.json'),r)
print(json.dumps({'status':r['status'],'answer':r['answer_text'],'tools':[e['tool'] for e in r['tool_events']], 'outputs':[x['outputs'] for x in r['calculation_traces']]},ensure_ascii=False))
raise SystemExit(2 if r['status'] in ('MODEL_ERROR','BUDGET_STOP','ANSWER_VALIDATION_FAILED','INVALID_MODEL_OUTPUT') else 0)
