"""Pure calculations. Every game constant is an explicit argument."""
from __future__ import annotations
from itertools import combinations
from math import ceil
from .graph import EvidenceError


class TaskError(ValueError):
    def __init__(self,status,detail):self.status=status;self.detail=detail;super().__init__(detail)


def integer(value,name,minimum=0):
    if value is None:raise TaskError('NEEDS_INPUT',name)
    if type(value)!=int or value<minimum:raise TaskError('INVALID_INPUT',name)
    return value


def growth(day,growth_nights,season_days,plants,seed_price,sell_price, *, regrowth=0,yield_per_harvest=1):
    for value,name,minimum in [(day,'day',1),(growth_nights,'growth_nights',1),(season_days,'season_days',1),
          (plants,'plants',1),(seed_price,'seed_price',0),(sell_price,'sell_price',0),(regrowth,'regrowth',0),(yield_per_harvest,'yield',1)]:integer(value,name,minimum)
    if day>season_days:raise TaskError('INVALID_INPUT','day outside season')
    first=day+growth_nights
    harvests=[] if first>season_days else list(range(first,season_days+1,regrowth)) if regrowth else [first]
    units=len(harvests)*plants*yield_per_harvest;cost=plants*seed_price;sales=units*sell_price
    return {'status':'OK' if harvests else 'NO_HARVEST','harvest_days':harvests,'units':units,'seed_cost_g':cost,
            'sales_g':sales,'margin_after_seed_g':sales-cost,'random_extra_yield':'excluded'}


def stage_remaining(durations,stage):
    integer(stage,'stage',1)
    if not durations or any(type(d)!=int or d<1 for d in durations):raise TaskError('INVALID_INPUT','durations')
    if stage==len(durations)+1:return [0,0]
    if stage>len(durations):raise TaskError('INVALID_INPUT','stage')
    later=sum(durations[stage:])
    return [later+1,later+durations[stage-1]]


def stage_date_consistent(durations,stage,elapsed_growth_nights):
    integer(elapsed_growth_nights,'elapsed',0);stage_remaining(durations,stage)
    lower=sum(durations[:stage-1])
    upper=sum(durations[:stage])-1 if stage<=len(durations) else float('inf')
    if not lower<=elapsed_growth_nights<=upper:raise TaskError('CONFLICT','date and visual stage disagree')
    return True


def process_value(base_price,raw_quality_price,multiplier,offset,quantity,historical_cost=None):
    for value,name in [(base_price,'base_price'),(raw_quality_price,'raw_quality_price'),(multiplier,'multiplier'),(offset,'offset')]:integer(value,name)
    integer(quantity,'quantity',1)
    if historical_cost is not None:integer(historical_cost,'historical_cost')
    unit=base_price*multiplier+offset;sales=unit*quantity;opportunity=raw_quality_price*quantity
    return {'unit_value_g':unit,'sales_g':sales,'raw_opportunity_cost_g':opportunity,
            'incremental_value_g':sales-opportunity,'profit_after_historical_cost_g':None if historical_cost is None else sales-historical_cost}


def daily_machine_batches(start_day,deadline_day,machine_minutes,machine_day,available_machines, *, include_deadline=True):
    for value,name in [(start_day,'start_day'),(deadline_day,'deadline'),(machine_minutes,'processing'),(machine_day,'machine_day'),(available_machines,'machines')]:integer(value,name,1)
    if type(include_deadline)!=bool:raise TaskError('INVALID_INPUT','deadline inclusion')
    if deadline_day<start_day:raise TaskError('INVALID_INPUT','deadline precedes start')
    interval=ceil(machine_minutes/machine_day)
    days=list(range(start_day+interval,deadline_day+int(include_deadline),interval))
    return {'collection_days':days,'completed_items':len(days)*available_machines,'operation_policy':'06:00 only; initially empty; immediate reload at 06:00'}


def allocate(total,allocations):
    integer(total,'inventory')
    for name,quantity in allocations.items():integer(quantity,name)
    if sum(allocations.values())>total:raise TaskError('INSUFFICIENT_INVENTORY','shared inventory exceeded')
    return total-sum(allocations.values())


def bundle_combinations(requirements,choose_k,completed,inventory):
    integer(choose_k,'choose_k',1);items={r['item'] for r in requirements}
    if not set(completed)<=items or choose_k>len(items):raise TaskError('INVALID_INPUT','bundle requirements')
    remaining=max(0,choose_k-len(set(completed)))
    if not remaining:return [[]]
    eligible=[]
    for r in requirements:
        if r['item'] in completed:continue
        stock=inventory.get(r['item'],{});usable=sum(integer(stock.get(q,0),q) for q in ['gold','iridium'])
        if usable>=r['quantity']:eligible.append(r['item'])
    return [list(c) for c in combinations(eligible,remaining)]


def crafting(materials,quantity,inventory,required_level,user_level,existing_equipment=0):
    integer(quantity,'quantity',1);integer(existing_equipment,'existing_equipment')
    if user_level is None:raise TaskError('NEEDS_INPUT','farming level/unlock')
    integer(user_level,'user_level')
    missing={m:max(0,integer(q,m)*quantity-integer(inventory.get(m,0),m)) for m,q in materials.items()}
    return {'missing_materials':missing,'can_craft':user_level>=required_level and not any(missing.values()),'existing_usable':existing_equipment}


class EvidenceResolver:
    def __init__(self,graph):self.graph=graph;self.used=[]
    def get(self,subject,pred,unit):
        f=self.graph.fact(subject,pred)
        if f['unit']!=unit:raise EvidenceError('INCOMPLETE_EVIDENCE: wrong unit')
        self.used.append(f);return f['value']
    def planting(self,seed, *, day,plants,season,watered,acceleration='none',quality='normal'):
        if season is None or watered is None or quality is None:raise TaskError('NEEDS_INPUT','season/watering/quality')
        if acceleration!='none' or watered is not True or quality!='normal':raise TaskError('UNSUPPORTED_CONDITIONS','only daily watered, no acceleration, normal quality forecast')
        crop=self.graph.seed_crop(seed);self.get(seed,'grows_into','entity')
        if self.get(crop,'season','season')!=season:raise TaskError('UNSUPPORTED_CONDITIONS','wrong outdoor season')
        self.get('Calendar','watered_growth','condition')
        result=growth(day,self.get(crop,'growth_days','growth_nights'),self.get('Calendar','season_days','days'),plants,
           self.get(seed,'buy_price','g'),self.get(crop,'sell_normal','g'),
           regrowth=self.get(crop,'regrowth','growth_nights') if crop=='Blueberry' else 0,
           yield_per_harvest=self.get(crop,'base_yield','items_per_harvest') if crop=='Blueberry' else 1)
        return {'result':result,'trace':{'rule_id':'planting/v1','snapshot_id':self.graph.manifest['snapshot_id'],
          'input_facts':[{'id':f['id'],'value':f['value'],'unit':f['unit'],'evidence':f['evidence']} for f in self.used],
          'user_inputs':{'day':day,'plants':plants,'season':season,'watered':watered,'quality':quality},
          'version_scope':'frozen Wiki diagnostic; not release-validated','units':'g; growth_nights; items'}}
