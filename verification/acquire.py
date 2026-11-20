"""Small, resumable, rate-limited acquisition of public Wiki HTML and assets."""
from __future__ import annotations

import argparse
import io
import re
import time
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from PIL import Image

from .common import BASE, DATA, dump, file_sha, jsonl, now, read_jsonl, sha

HOST = "stardewvalleywiki.com"
PAGES = ["Parsnip", "Parsnip_Seeds", "Melon", "Melon_Seeds", "Crops",
         "Keg", "Preserves_Jar", "Bundles", "Blueberry", "Blueberry_Seeds",
         "Wine", "Jellies_and_Pickles"]


class Fetcher:
    def __init__(self):
        self.client = httpx.Client(timeout=30, follow_redirects=False,
            headers={"User-Agent": "StardewCourseVerification/0.1 (educational research; sequential requests)"})
        self.last = 0
        self.events = []
        self.blocked = None

    def get(self, url):
        if self.blocked:
            raise RuntimeError(self.blocked)
        if urlparse(url).hostname != HOST or urlparse(url).scheme != "https":
            raise ValueError("URL outside allowed HTTPS Wiki host")
        time.sleep(max(0, 1.1 - (time.monotonic() - self.last)))
        self.last = time.monotonic()
        try:
            r = self.client.get(url)
            self.events.append({"url":url,"at":now(),"status":r.status_code,"bytes":len(r.content)})
        except httpx.HTTPError as exc:
            self.events.append({"url":url,"at":now(),"error":type(exc).__name__,"message":str(exc)})
            raise
        if r.status_code in (401,403,429):
            self.blocked = f"HTTP {r.status_code}; acquisition stopped, no bypass attempted"
            raise RuntimeError(self.blocked)
        if r.is_redirect:
            return self.get(urljoin(url,r.headers["location"]))
        r.raise_for_status()
        return r


def parse_page(html, page):
    soup = BeautifulSoup(html,"lxml")
    body = soup.select_one(".mw-parser-output") or soup.select_one("#mw-content-text")
    if not body:
        raise ValueError("No MediaWiki article body")
    oldid = re.search(r'"wgRevisionId"\s*:\s*(\d+)',html)
    if not oldid:
        oldid = re.search(r'[?&]oldid=(\d+)',html)
    occurrences=[]
    for n,img in enumerate(body.select("img")):
        src=img.get("src","")
        if not src: continue
        url=urljoin(f"https://{HOST}/{page}",src)
        if urlparse(url).hostname!=HOST: continue
        parent=img.find_parent("a")
        row=img.find_parent("tr")
        heading=img.find_previous(["h2","h3"])
        occurrences.append({"occurrence_id":f"occ:{page}:{n}","page_id":page,
            "asset_url":url,"alt":img.get("alt",""),
            "file_page_url":urljoin(f"https://{HOST}",parent.get("href","")) if parent else None,
            "section":heading.get_text(" ",strip=True) if heading else "infobox",
            "row_text":row.get_text(" ",strip=True)[:3000] if row else None,
            "selector":".mw-parser-output img",
            "article_image_index":n,"alignment_origin":"html_layout","review_status":"candidate"})
    tables=[{"table_index":i,"text":t.get_text(" ",strip=True),
             "rows":[[c.get_text(" ",strip=True) for c in tr.find_all(["th","td"],recursive=False)] for tr in t.find_all("tr")]}
            for i,t in enumerate(body.find_all("table"))]
    return oldid.group(1) if oldid else None,body.get_text("\n",strip=True),tables,occurrences


def run(limit,assets):
    f=Fetcher(); manifest=read_jsonl(DATA/"source_manifest.jsonl")
    pages={r["page_id"]:r for r in manifest}; occurrences=read_jsonl(DATA/"occurrence_manifest.jsonl")
    images={r["url"]:r for r in read_jsonl(DATA/"image_manifest.jsonl")}
    started=now()
    try:
        for page in PAGES[:limit]:
            old=pages.get(page)
            if old and (BASE/old["raw_path"]).exists() and file_sha(BASE/old["raw_path"])==old["sha256"]:
                continue
            url=f"https://{HOST}/{page}"
            r=f.get(url);html=r.text
            rev,text,tables,occs=parse_page(html,page)
            digest=sha(r.content)
            raw=DATA/"raw"/f"{page}-{digest[:12]}.html";raw.parent.mkdir(parents=True,exist_ok=True);raw.write_bytes(r.content)
            norm=DATA/"parsed"/f"{page}.json"
            dump(norm,{"page_id":page,"revision_id":rev,"text":text,"tables":tables})
            pages[page]={"page_id":page,"url":url,"revision_id":rev,"retrieved_at":now(),
                "sha256":digest,"raw_path":str(raw.relative_to(BASE)),"parsed_path":str(norm.relative_to(BASE)),
                "http_status":r.status_code,"game_version_assertion":"unverified","license_status":"per_asset_review_pending"}
            occurrences=[o for o in occurrences if o["page_id"]!=page]+occs
            jsonl(DATA/"source_manifest.jsonl",list(pages.values()));jsonl(DATA/"occurrence_manifest.jsonl",occurrences)
            print(f"PAGE {page} revision={rev} images={len(occs)}",flush=True)
        if assets:
            candidates=[]
            for o in occurrences:
                if o["page_id"] in {"Parsnip","Parsnip_Seeds","Melon","Melon_Seeds","Blueberry","Blueberry_Seeds","Keg","Preserves_Jar"}:
                    alt=o["alt"].lower()
                    if any(x in alt for x in ["parsnip","melon","blueberry","keg","preserves jar","stage"]) and o["asset_url"] not in candidates:
                        candidates.append(o["asset_url"])
            for url in candidates[:60]:
                old=images.get(url)
                if old and (BASE/old["path"]).exists() and file_sha(BASE/old["path"])==old["sha256"]:continue
                r=f.get(url);im=Image.open(io.BytesIO(r.content));im.load();digest=sha(r.content)
                path=DATA/"assets"/(digest+"."+(im.format or "png").lower());path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(r.content)
                images[url]={"image_id":"img:"+digest[:20],"url":url,"sha256":digest,
                    "pixel_sha256":sha(im.convert("RGBA").tobytes()),"path":str(path.relative_to(BASE)),
                    "width":im.width,"height":im.height,"format":im.format,"alpha":"A" in im.getbands() or 'transparency' in im.info,
                    "retrieved_at":now(),"license_status":"per_asset_review_pending"}
                jsonl(DATA/"image_manifest.jsonl",list(images.values()))
                print(f"IMAGE {Path(unquote(urlparse(url).path)).name} {im.size}",flush=True)
    except Exception as exc:
        error={"type":type(exc).__name__,"message":str(exc)}
    else:error=None
    result={"scope":"V01_ACQUISITION","started_at":started,"finished_at":now(),"pages":len(pages),
            "images":len(images),"occurrences":len(occurrences),"events":f.events,"error":error,
            "status":"BLOCKED" if error else "PASS_ACQUISITION_ONLY","version_review":"pending"}
    dump(BASE/"results"/"acquisition_latest.json",result)
    dump(BASE/"logs"/"acquisition"/(started.replace(":","-")+".json"),result)
    print({k:result[k] for k in ["status","pages","images","error"]})
    return 2 if error else 0


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--limit",type=int,default=3,choices=range(1,13));p.add_argument("--assets",action="store_true")
    a=p.parse_args();raise SystemExit(run(a.limit,a.assets))
