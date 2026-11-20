"""Local demonstration CLI; always offline and restricted to verified calculator scope."""
import argparse
import json
from pathlib import Path
from .common import BASE, dump, file_sha, offline_guard
from .pipeline import AssistantPipeline


def main():
    p=argparse.ArgumentParser(description='星露谷助手核验原型：局部截图、证据和确定性计算')
    p.add_argument('--image',type=Path,required=True);p.add_argument('--intent',choices=['planting','remaining'],required=True)
    p.add_argument('--question',default='根据图中物品和给定条件完成计算。');p.add_argument('--day',type=int);p.add_argument('--plants',type=int)
    p.add_argument('--season',choices=['Spring','Summer','Fall','Winter']);p.add_argument('--watered',action='store_true')
    p.add_argument('--confirmed-entity');p.add_argument('--planted-day',type=int);p.add_argument('--reject-all',action='store_true')
    p.add_argument('--output',type=Path);a=p.parse_args();offline_guard()
    request={'image_path':str(a.image.resolve()),'image_sha256':file_sha(a.image),'intent':a.intent,'kind':'stage' if a.intent=='remaining' else 'item',
      'question':a.question,'confirmed_entity':a.confirmed_entity,'reject_all_candidates':a.reject_all,
      'state':{'day':a.day,'plants':a.plants,'season':a.season,'watered':True if a.watered else None,'planted_day':a.planted_day,'acceleration':'none'}}
    result=AssistantPipeline().run(request)
    if a.output:dump(a.output,result)
    print(json.dumps({k:v for k,v in result.items() if k!='trace'},ensure_ascii=False,indent=2))
    return 0 if result['status']=='OK' else 2

if __name__=='__main__':raise SystemExit(main())
