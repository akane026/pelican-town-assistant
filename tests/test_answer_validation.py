import json
from stardew_agent.agent import validate_answer,repair_answer

def test_unsupported_side_claim_not_whitelisted_by_status():
    answer={'answer_text':'总价值315g，另留5个。','claim_evidence_refs':[],'calculation_trace_refs':['calc:test'],'status':'NEEDS_INPUT'}
    calcs={'calc:test':{'outputs':{'sales_g':315}}}
    assert validate_answer(answer,{},calcs,{})['unsupported_numbers']==['5']

def test_one_repair_retains_same_evidence():
    original={'answer_text':'315g，另外留5个','claim_evidence_refs':[],'calculation_trace_refs':['calc:test']}
    calcs={'calc:test':{'run_id':'calc:test','rule_id':'sale_value','user_inputs':{},'outputs':{'sales_g':315}}}
    class Synthetic:
        def __init__(self):self.calls=0
        def call(self,messages,**opts):
            self.calls+=1
            assert opts['label']=='v3_answer_repair' and 'tools' not in opts
            return {'status':'OK','content':json.dumps({'answer_text':'候选结果315g。','claim_evidence_refs':[],'calculation_trace_refs':['calc:test']})}
    model=Synthetic();answer,report=repair_answer(model,original,{},calcs,{})
    assert model.calls==1 and report['accepted'] and answer['answer_text']=='候选结果315g。'
    assert report['original_draft']==original and report['original_errors']['unsupported_numbers']==['5']
    answer['answer_repairs']=[report]
    assert json.loads(json.dumps(answer))['answer_repairs'][0]['accepted']

def test_repair_cannot_change_value_or_fake_reference():
    class Synthetic:
        def call(self,*args,**kw):return {'status':'OK','content':json.dumps({'answer_text':'999g','claim_evidence_refs':['invented'],'calculation_trace_refs':[]})}
    original={'answer_text':'315g，另留5个。','claim_evidence_refs':[],'calculation_trace_refs':['calc:test']}
    calcs={'calc:test':{'run_id':'calc:test','rule_id':'sale','user_inputs':{},'outputs':{'sales_g':315}}}
    answer,report=repair_answer(Synthetic(),original,{},calcs,{})
    assert not report['accepted'] and answer==original
    assert report['repaired_errors']['invalid_references']
