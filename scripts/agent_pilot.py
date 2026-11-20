"""Real online diagnostic, not formal scored evaluation or a fixed product route."""
import argparse,json
from stardew_agent.core import *
from stardew_agent.knowledge import Snapshot
from stardew_agent.state import TaskStore
from stardew_agent.agent import Agent

def main():
    p=argparse.ArgumentParser();p.add_argument('--case',choices=['sale','compose','clarify'],required=True);a=p.parse_args()
    q={
      'sale':'我有12个普通品质甘蓝，无职业加成，只比较直接出售总价值。请查当前资料并实际计算。',
      'compose':'春季作物收集包还没完成。我有10个普通防风草、1个普通青豆、1个普通花椰菜、1个普通土豆，无职业加成。先在计划里留献祭，再计算剩余防风草直接卖多少钱。仅作候选诊断，不改变真实库存。',
      'clarify':'我想知道甘蓝直接卖多少钱，目前还没告诉你数量和品质。'}[a.case]
    tasks=TaskStore();task=tasks.create(Snapshot(allow_candidate=True).id);agent=Agent(tasks,max_rounds=12)
    answer=agent.run(task['task_id'],q)
    result={'case':a.case,'task_id':task['task_id'],'question':q,'answer':answer,'status':'EXECUTED_CANDIDATE_DIAGNOSTIC',
            'formal_success':False,'human_review':'pending'}
    write(ARTIFACTS/'agent_pilots'/f'{a.case}-{task["task_id"]}.json',result)
    write(ARTIFACTS/'agent_pilots'/(a.case+'.json'),result)
    print(json.dumps({'case':a.case,'task_id':task['task_id'],'status':answer['status'],'text':answer['answer_text'],
        'tools':[e['tool'] for e in answer['tool_events']],'calculations':[c['outputs'] for c in answer['calculation_traces']]},ensure_ascii=False))
    return 0 if answer['status'] not in ('MODEL_ERROR','INVALID_MODEL_OUTPUT','BUDGET_STOP','ANSWER_VALIDATION_FAILED') else 2
if __name__=='__main__':raise SystemExit(main())
