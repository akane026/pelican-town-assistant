"""Local form to preserve public DOM snapshots and browser-exported assets.

This does not fetch remote URLs. Use the normal browser's read-only DOM and
pageAssets export. The HTTP scraper's 403 remains a recorded separate failure.
"""
from __future__ import annotations
import io
import json
import re
import shutil
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlparse
from PIL import Image
from .acquire import PAGES,parse_page
from .common import BASE,DATA,dump,jsonl,now,read_jsonl,sha


def preserve(payload):
    page=payload['page_id']
    if page not in PAGES:raise ValueError('Page outside bounded manifest')
    if urlparse(payload['url']).hostname!='stardewvalleywiki.com':raise ValueError('Unexpected source')
    html=payload['html'];digest=sha(html.encode());rev=re.search(r'oldid=(\d+)',payload.get('permanent_url',''))
    raw=DATA/'raw'/f'{page}-dom-{digest[:12]}.html';raw.parent.mkdir(parents=True,exist_ok=True);raw.write_text(html,encoding='utf-8',newline='\n')
    _,text,tables,occ=parse_page(html,page)
    norm=DATA/'parsed'/f'{page}.json';dump(norm,{'page_id':page,'revision_id':rev.group(1) if rev else None,'text':text,'tables':tables})
    sources={r['page_id']:r for r in read_jsonl(DATA/'source_manifest.jsonl')}
    sources[page]={'page_id':page,'url':payload['url'],'permanent_url':payload.get('permanent_url'),
        'revision_id':rev.group(1) if rev else None,'retrieved_at':now(),'sha256':digest,
        'raw_path':str(raw.relative_to(BASE)),'parsed_path':str(norm.relative_to(BASE)),
        'capture_method':'rendered_dom_via_normal_browser','http_status':None,
        'game_version_assertion':'unverified','license_note':payload.get('footer','')}
    jsonl(DATA/'source_manifest.jsonl',list(sources.values()))
    old=read_jsonl(DATA/'occurrence_manifest.jsonl');jsonl(DATA/'occurrence_manifest.jsonl',[r for r in old if r['page_id']!=page]+occ)
    assets={r['url']:r for r in read_jsonl(DATA/'image_manifest.jsonl')}
    bundle=payload.get('bundle',{})
    directory=Path(bundle['directoryPath']).resolve() if bundle else None
    for entry in bundle.get('assets',[]):
        path=Path(entry['path']).resolve()
        if directory not in path.parents:raise ValueError('Asset outside exported bundle')
        data=path.read_bytes();im=Image.open(io.BytesIO(data));im.load();h=sha(data)
        dest=DATA/'assets'/(h+'.'+(im.format or 'png').lower());dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        assets[entry['url']]={'image_id':'img:'+h[:20],'url':entry['url'],'sha256':h,
            'pixel_sha256':sha(im.convert('RGBA').tobytes()),'path':str(dest.relative_to(BASE)),
            'width':im.width,'height':im.height,'format':im.format,'alpha':'A' in im.getbands() or 'transparency' in im.info,
            'capture_method':'browser_pageAssets','retrieved_at':now(),'license_status':'per_asset_review_pending'}
    jsonl(DATA/'image_manifest.jsonl',list(assets.values()))
    log={'at':now(),'page':page,'revision':sources[page]['revision_id'],'raw_sha256':digest,
         'occurrences':len(occ),'assets_exported':len(bundle.get('assets',[])),
         'asset_failures':bundle.get('failures',[])}
    dump(BASE/'logs'/'browser_import'/f'{page}-{digest[:12]}.json',log)
    return f'Saved {page}; revision {log["revision"]}; total {len(sources)} pages and {len(assets)} assets.'


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def page(self,message='Ready for a public Wiki snapshot'):
        html='''<!doctype html><meta charset="utf-8"><title>Wiki snapshot import</title><h1>Local Wiki snapshot import</h1><p>'''+message+'''</p><form method="post"><label for="payload">Snapshot JSON</label><textarea id="payload" name="payload" rows="5" cols="80"></textarea><button type="submit">Save snapshot</button></form>'''
        self.send_response(200);self.send_header('Content-Type','text/html;charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(html.encode())
    def do_GET(self):self.page()
    def do_POST(self):
        try:
            n=int(self.headers.get('Content-Length',0))
            if n>8_000_000:raise ValueError('Snapshot too large')
            body=parse_qs(self.rfile.read(n).decode());result=preserve(json.loads(body['payload'][0]));self.page(result)
        except Exception as exc:self.page('Import failed: '+type(exc).__name__+': '+str(exc))


if __name__=='__main__':
    print('Local snapshot form at http://127.0.0.1:8766',flush=True)
    HTTPServer(('127.0.0.1',8766),Handler).serve_forever()
