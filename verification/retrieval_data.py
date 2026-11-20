"""Freeze query inputs and separately stored expected evidence before scoring."""
from .common import BASE, DATA, dump, file_sha, jsonl, read_jsonl


def prepare():
    samples={r['sample_id']:r for r in read_jsonl(DATA/'visual_test_manifest.jsonl')}
    # Expected IDs are scorer-only; online inputs receive only question, image and confirmation.
    cases=[
      ('D01','dev','V07','Parsnip_Seeds','这是什么种子？',['entity:Parsnip_Seeds','fact:Parsnip_Seeds:grows_into']),
      ('D02','dev','V01','Parsnip','这个作物的普通品质卖价是多少？',['fact:Parsnip:sell_normal']),
      ('D03','dev','V10','Melon_Stage_3','这个阶段还需要多少个生长夜晚？',['fact:Melon:stage_durations','fact:Calendar:watered_growth']),
      ('D04','dev','V08',None,'这是什么？',[]),
      ('R01','test','V28','Parsnip_Seeds','这是什么种子？',['entity:Parsnip_Seeds','fact:Parsnip_Seeds:grows_into']),
      ('R02','test','V28','Parsnip_Seeds','春季种下它，需要多少个生长夜晚？',['fact:Parsnip_Seeds:grows_into','fact:Parsnip:season','fact:Parsnip:growth_days','fact:Calendar:watered_growth']),
      ('R03','test','V13','Melon','它的金星品质卖多少钱？',['fact:Melon:sell_gold']),
      ('R04','test','V13','Melon','它在高品质作物献祭中需要多少个、什么品质？',['fact:Melon:quality_bundle','fact:Quality_Crops_Bundle:choose_k']),
      ('R05','test','V13','Melon','把它放进罐头瓶做果酱，成品售价怎么算？',['fact:Melon:sell_normal','fact:Jelly:value_formula','fact:Jelly:equipment']),
      ('R06','test','V13','Melon','把它放进罐头瓶做果酱，每天六点操作多久收一次？',['fact:Jelly:processing_minutes','fact:Jelly:equipment','fact:Calendar:machine_day']),
      ('R07','test','V33','Melon_Stage_3','图中作物是什么生长阶段？',['entity:Melon_Stage_3','fact:Melon_Stage_3:duration']),
      ('R08','test','V33','Melon_Stage_3','图中作物距离成熟还需要多少个生长夜晚？',['fact:Melon:stage_durations','fact:Calendar:watered_growth']),
      ('R09','test','V12','Parsnip','这种作物适合什么季节、需要多久成熟？',['fact:Parsnip:season','fact:Parsnip:growth_days']),
      ('R10','test','V13','Melon','这种作物适合什么季节、需要多久成熟？',['fact:Melon:season','fact:Melon:growth_days']),
      ('R11','test','V32','Melon_Stage_6','这个阶段距离成熟还需要多少个生长夜晚？',['fact:Melon:stage_durations','fact:Calendar:watered_growth']),
      ('R12','test','V33','Melon_Stage_3','这个阶段距离成熟还需要多少个生长夜晚？',['fact:Melon:stage_durations','fact:Calendar:watered_growth']),
      ('R13','test','V14','Blueberry','这是什么、普通品质值多少钱？',['entity:Blueberry','fact:Blueberry:sell_normal']),
      ('R14','test','V18',None,'这是什么、普通品质值多少钱？',[]),
      ('R15','test','V13','Melon','把它加工成果酒后值多少钱？',['fact:Melon:sell_normal','fact:Wine:value_formula','fact:Wine:equipment']),
      ('R16','test','V27',None,'把它加工成果酒后值多少钱？',[]),
    ]
    inputs=[];gold=[]
    for id,split,sample,entity,q,required in cases:
        s=samples[sample]
        inputs.append({'query_id':id,'split':split,'question':q,'image_path':s['path'],'image_sha256':s['sha256'],
          'visual_entities':[entity] if entity else [],'identification_mode':'scripted_assistance' if entity else 'user_rejects_candidates',
          'player_state':{'watered_daily':True,'acceleration':'none','profession':'none','operation_time':'06:00'},
          'pair_id':None if split=='dev' else 'P'+str((int(id[1:])+1)//2)})
        gold.append({'query_id':id,'sufficient_fact_sets':[required] if required else [],'expected_status':'EVIDENCE' if required else 'NEEDS_IDENTIFICATION',
          'review':'assistant-created; independent human review pending','image_gold_origin':'manual screenshot review'})
    jsonl(DATA/'retrieval_inputs.jsonl',inputs);jsonl(DATA/'retrieval_gold.jsonl',gold)
    dump(DATA/'retrieval_dataset_freeze.json',{'input_sha256':file_sha(DATA/'retrieval_inputs.jsonl'),'gold_sha256':file_sha(DATA/'retrieval_gold.jsonl'),
      'changes_from_plan':['R09/R10 compare two crop icons, not two seed types (only Parsnip seed screenshots acquired)',
                           'R15/R16 compare confirmed Melon with unrecognized raw item, not ambiguous processed-wine image'],
      'scope':'assisted retrieval diagnostic; image recognition measured separately; not original complete preregistered suite'})

if __name__=='__main__':prepare()
