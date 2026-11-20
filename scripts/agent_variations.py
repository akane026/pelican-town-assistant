"""New real dynamic multi-turn diagnostic, with independently written arithmetic references."""
from stardew_agent.core import *
from stardew_agent.knowledge import Snapshot
from stardew_agent.state import TaskStore
from stardew_agent.agent import Agent
tasks=TaskStore();task=tasks.create(Snapshot(allow_candidate=True).id);agent=Agent(tasks,max_rounds=12)
cases=[
 {'question':'我有2个金星甜瓜，无职业加成。只比较做成果酒与果酱的最终销售价值，分别是多少，哪个更高？不需要生产排期，也没有实际加工或出售。',
  'reference':{'wine_g':1500,'jelly_g':1100},'independent_arithmetic':'2 × (250 × 3) = 1500；2 × (250 × 2 + 50) = 1100；品质不影响普通加工产物基础公式。'},
 {'question':'刚才只是比较，没有执行。现在改成3个普通土豆，仍然无职业加成：比较直接卖与加工腌菜的最终价值，保持原库存。',
  'reference':{'raw_g':240,'pickles_g':630},'independent_arithmetic':'3 × 80 = 240；3 × (80 × 2 + 50) = 630。'}]
outputs=[]
for case in cases:
    before=tasks.get(task['task_id']);answer=agent.run(task['task_id'],case['question']);after=tasks.get(task['task_id'])
    observed=[r['outputs'] for r in answer['calculation_traces']]
    row={**case,'task_id':task['task_id'],'answer':answer,'state_before':before,'state_after':after,
         'observed_outputs':observed,'formal_success':None,'human_reference_review':'PENDING',
         'evaluation_scope':'New wording after implementation; development diagnostic, not blind formal evaluation.'}
    outputs.append(row);write(ARTIFACTS/'agent_pilots'/('variations-'+task['task_id']+'.json'),outputs)
    print(canonical({'turn':len(outputs),'status':answer['status'],'outputs':observed,'text':answer['answer_text']}),flush=True)
summary={'task_id':task['task_id'],'snapshot_id':task['snapshot_id'],'statuses':[x['answer']['status'] for x in outputs],
 'rule_ids':[[c['rule_id'] for c in x['answer']['calculation_traces']] for x in outputs],
 'previous_results_invalidated':all(r in outputs[1]['state_after']['stale_result_ids'] for r in outputs[0]['state_after']['results']),
 'model_semantic_checks':[[c['verdict'] for c in x['answer'].get('grounding_checks',[])] for x in outputs],
 'formal_score':None,'references':'Independent arithmetic above, still pending human source review.'}
write(ARTIFACTS/'evaluation/agent_variations_summary.json',summary);print(canonical(summary))
raise SystemExit(0 if all(s=='CANDIDATE_ANSWER' for s in summary['statuses']) and summary['previous_results_invalidated'] else 2)
