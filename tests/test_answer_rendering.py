from stardew_agent.answer_rendering import calculation_answer
from stardew_agent.agent import validate_answer

def test_stock_scope_comes_from_each_tool_output_not_free_text():
    calculations={'reserve':{'rule_id':'bundle_reserve','user_inputs':{'entity_id':'entity:Bundle'},
       'outputs':{'options':[{'reserved':{'Crop_A':{'normal':1},'Crop_B':{'normal':1}},'remaining':{'Crop_A':{'normal':9},'Crop_B':{'normal':0}}}]}},
      'sale':{'rule_id':'sale_value','user_inputs':{'entity_id':'entity:Crop_A','quality':'normal'},'outputs':{'quantity':9,'unit_value_g':35,'sales_g':315}}}
    answer=calculation_answer(calculations,{}, {},candidate=True)
    assert 'Crop_A：普通 9 个' in answer['answer_text'] and 'Crop_B：各品质均无剩余' in answer['answer_text']
    assert '没有多余可卖' not in answer['answer_text'] and '315g' in answer['answer_text']
    assert validate_answer(answer,{},calculations,{})['unsupported_numbers']==[]

def test_comparison_uses_only_same_quantity_actual_outputs():
    def calc(product,quantity,sales):return {'rule_id':'processing_value','user_inputs':{'entity_id':'entity:Fruit','product_id':product,'quantity':quantity,'quality':'gold','profession':'none'},'outputs':{'unit_value_g':100,'sales_g':sales,'raw_opportunity_cost_g':50,'incremental_value_g':sales-50}}
    answer=calculation_answer({'a':calc('entity:Wine',2,200),'b':calc('entity:Jelly',3,300)}, {},{},candidate=True)
    assert '最高' not in answer['answer_text']
    answer=calculation_answer({'a':calc('entity:Wine',2,200),'b':calc('entity:Jelly',2,180)}, {},{},candidate=True)
    assert 'Wine的最终销售额最高' in answer['answer_text'] and '不表示可以同时执行' in answer['answer_text']

def test_new_entity_needs_no_answer_route():
    entities={'entity:Novel':{'name':'Novel','aliases':['新作物']}}
    calc={'rule_id':'sale_value','user_inputs':{'entity_id':'entity:Novel','quality':'silver'},'outputs':{'unit_value_g':17,'quantity':4,'sales_g':68}}
    answer=calculation_answer({'new':calc},entities,{},candidate=True)
    assert '新作物' in answer['answer_text'] and '68g' in answer['answer_text']
