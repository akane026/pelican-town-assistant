"""Compare retained real outputs to pre-written arithmetic, never a human gold score."""
from stardew_agent.core import *
s=read(ARTIFACTS/'evaluation/agent_variations_summary.json')
runs=read(ARTIFACTS/'agent_pilots'/('variations-'+s['task_id']+'.json'));checks=[]
for turn,row in enumerate(runs,1):
    observed={}
    for c in row['answer']['calculation_traces']:
        key='raw_g' if c['rule_id']=='sale_value' else {'entity:Wine':'wine_g','entity:Jelly':'jelly_g','entity:Pickles':'pickles_g'}.get(c['user_inputs'].get('product_id'))
        if key:observed[key]=c['outputs']['sales_g']
    checks.append({'turn':turn,'reference':row['reference'],'observed':observed,
                   'matches_pre_written_arithmetic':all(observed.get(k)==v for k,v in row['reference'].items()),'human_review':'PENDING'})
write(ARTIFACTS/'evaluation/agent_variations_arithmetic.json',{'scope':'offline comparison of retained real tool outputs with pre-written arithmetic; not a new Agent execution or formal human score','checks':checks})
print(canonical(checks));raise SystemExit(0 if all(c['matches_pre_written_arithmetic'] for c in checks) else 2)
