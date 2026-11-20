import sys,platform
from pathlib import Path
from importlib.metadata import version
import semantica
from stardew_agent.core import *
from stardew_agent.knowledge import Snapshot
from stardew_agent.retrieval import Retriever
from stardew_agent.evidence import BundleStore
from stardew_agent.rules import dependencies,missing_dependencies
from stardew_agent.calculations import execute
s=Snapshot(allow_candidate=True);params={'entity_id':'entity:Kale','quantity':12,'quality':'normal','profession':'none'};retriever=Retriever(s)
out=retriever.retrieve('甘蓝普通售价',entity_ids=[params['entity_id']],candidate=True,task_id='independent-repro');store=BundleStore()
for _ in range(2):
 b=store.get(out['bundle_id'],task_id='independent-repro',revision=0,snapshot_id=s.id)
 missing=missing_dependencies(b.data(),dependencies('sale_value',params,b.data())['selectors'])
 if not missing:break
 out=retriever.supplement(b,missing,candidate=True)
result=execute('sale_value',b,params);assert result['outputs']['sales_g']==1320
package_path=Path(semantica.__file__).resolve();assert '.venv-repro' in str(package_path)
report={'status':'PASS','sys_prefix':sys.prefix,'base_prefix':sys.base_prefix,'python':platform.python_version(),'semantica_version':version('semantica'),
 'semantica_loaded_from':str(package_path),'snapshot_id':s.id,'roundtrip':s.roundtrip(),'representative_task':result,
 'boundaries':{'independently_installed_packages':True,'copied_virtual_environment':False,'same_machine':True,'shared_legally_acquired_sources':True,'new_network_acquisition':False,'new_model_call':False}}
write(ARTIFACTS/'repro/independent_environment.json',report)
print(canonical({k:v for k,v in report.items() if k!='representative_task'}));print('sales_g',result['outputs']['sales_g'])
