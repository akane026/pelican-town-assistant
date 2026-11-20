"""Download a bounded set of source-linked public gameplay screenshots."""
import io
import time
import httpx
from PIL import Image
from .common import BASE,DATA,read_jsonl,jsonl,sha,now

SOURCES=[
 ('autosaved_inventory','https://autosaved.org/stardew-valley-first-six-days-guide','https://autosaved-images.s3.us-east-2.amazonaws.com/dev/images/stardewvalley/check.webp'),
 ('arqade_melon','https://gaming.stackexchange.com/questions/298179/why-did-these-plants-wither','https://i.sstatic.net/71i1p.png'),
 ('tom_melon','https://forums.tomshardware.com/faq/stardew-valley-%E2%80%9Ccrop-research%E2%80%9D-story-quest-guide.3339368/','https://i.imgur.com/fH0RljP.jpg'),
 ('3dm_inventory','https://shouyou.3dmgame.com/gl/596419.html','https://syimg.3dmgame.com/uploadimg/xiaz/2025/1020/1760938975244.jpg'),
 ('9game_inventory','https://a.9game.cn/xlgwy/5065842.html','https://media.9game.cn/gamebase/2021/3/31/226744283.png'),
 ('twinfinite_melon','https://twinfinite.net/guides/best-summer-crops-stardew-valley/','https://twinfinite.net/wp-content/uploads/2023/07/stardew-valley-melons.jpg?resize=991%2C557'),
 ('forum_seed_shop','https://forums.stardewvalley.net/threads/max-stack-button-on-stores.2600/','https://forums.stardewvalley.net/attachments/screenshot-2020-10-20-at-9-22-10-am-png.1652/'),
 ('carls_beginning','https://www.carlsguides.com/stardewvalley/','https://www.carlsguides.com/stardewvalley/pictures/beginners-guide/beginning.jpg'),
 ('steam_crafting','https://steamcommunity.com/sharedfiles/filedetails/?id=812004740','https://images.steamusercontent.com/ugc/101725152288056762/41EBCBD592466A9AF91621F0877D700FB7FDF91B/'),
 ('korean_inventory','https://iizz.tistory.com/158','https://raw.githubusercontent.com/spacedustz/Typora-Image-Server/main/img/star.png'),
]

def main():
 rows={r['capture_id']:r for r in read_jsonl(DATA/'external_screenshot_manifest.jsonl')}
 client=httpx.Client(timeout=30,follow_redirects=True,headers={'User-Agent':'StardewCourseVerification/0.1'})
 for id,source,url in SOURCES:
  if id in rows:continue  # preserve failed downloads; retries need a deliberate new attempt
  row={'capture_id':id,'source_page':source,'image_url':url,'retrieved_at':now(),'origin':'public_gameplay_image',
       'game_version':'unknown','mod_status':'unverified','ground_truth_review':'pending','redistribution':'not_authorized_local_research_only'}
  try:
   r=client.get(url);row['http_status']=r.status_code;r.raise_for_status();im=Image.open(io.BytesIO(r.content));im.load()
   path=DATA/'external'/f'{id}.{im.format.lower()}';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(r.content)
   row.update(status='DOWNLOADED',path=str(path.relative_to(BASE)),sha256=sha(r.content),width=im.width,height=im.height)
  except Exception as exc:row.update(status='BLOCKED',error=type(exc).__name__)
  rows[id]=row;jsonl(DATA/'external_screenshot_manifest.jsonl',list(rows.values()));print(id,row['status'],flush=True);time.sleep(1)

if __name__=='__main__':main()
