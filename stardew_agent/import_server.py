"""Accept normal-browser exports only; never fetch or bypass remote HTTP restrictions."""
import io,json,re
from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.parse import parse_qs,urlparse
from pathlib import Path
from PIL import Image
from .core import *

def preserve(payload):
    config=read(ROOT/'configs/corpus.json');page=payload['page_id']
    allowed=set(config['development']+config['batch_a']+config['batch_b']+config['remaining'])
    if page not in allowed or urlparse(payload['url']).hostname!='stardewvalleywiki.com':raise ValidationError('SOURCE_NOT_ALLOWED')
    html=payload['html'];h=digest(html.encode());rev=re.search(r'oldid=(\d+)',payload.get('permanent_url',''))
    if not rev:raise ValidationError('MISSING_REVISION')
    p=DATA/'raw'/f'{page}-{h[:12]}.html';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(html)
    sources={s['page_id']:s for s in read(DATA/'manifests/sources.json')}
    batch=next(k for k in ('batch_a','batch_b','remaining','development') if page in config[k])
    sources[page]={'page_id':page,'revision_id':rev.group(1),'url':payload['url'],'permanent_url':payload['permanent_url'],
       'sha256':h,'raw_path':str(p.relative_to(ROOT)),'capture_method':'rendered_dom_via_normal_browser','retrieved_at':now(),
       'game_version_assertion':'unverified','batch':batch,'split':batch,'license_note':payload.get('footer','')}
    assets={a['id']:a for a in read(DATA/'manifests/assets.json')};bundle=payload['bundle'];base=Path(bundle['directoryPath']).resolve()
    for a in bundle.get('assets',[]):
        original=contained(a['path'],base);raw=original.read_bytes()
        with Image.open(io.BytesIO(raw)) as im:
            im.load()
            if im.width*im.height>20_000_000:raise ValidationError('LARGE_IMAGE')
            ah=digest(raw);dest=DATA/'assets'/(ah+'.'+im.format.lower());dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
            aid='asset:'+ah;row={'id':aid,'url':a['url'],'sha256':ah,'path':str(dest.relative_to(ROOT)),
                   'width':im.width,'height':im.height,'format':im.format,'alpha':'A' in im.getbands(),'pixel_sha256':digest(im.convert('RGBA').tobytes()),
                   'capture_method':'browser_pageAssets','source_kind':'original_wiki_asset','license_status':'per_asset_review_pending'}
            if aid in assets:row['url_aliases']=sorted(set(assets[aid].get('url_aliases',[])+[assets[aid]['url'],a['url']]))
            assets[aid]=row
    write(DATA/'manifests/sources.json',list(sources.values()));write(DATA/'manifests/assets.json',list(assets.values()))
    log={'page_id':page,'revision':rev.group(1),'batch':batch,'source_sha256':h,'assets_exported':len(bundle['assets']),
         'failures':bundle.get('failures',[]),'command':'normal browser DOM + pageAssets bundle + local form import','exit_status':0,'at':now()}
    write(ARTIFACTS/'acquisition'/(page+'-'+h[:12]+'.json'),log)
    return f'Saved {page}; revision {rev.group(1)}; {len(bundle["assets"])} assets; batch {batch}'

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def page(self,message='Ready'):
        import html
        out='<meta charset="utf-8"><title>V3 Wiki import</title><h1>V3 Wiki import</h1><p>'+html.escape(message)+'</p><form method="post"><label for="payload">Snapshot JSON</label><textarea id="payload" name="payload"></textarea><button>Save snapshot</button></form>'
        self.send_response(200);self.send_header('Content-Type','text/html;charset=utf-8');self.end_headers();self.wfile.write(out.encode())
    def do_GET(self):self.page()
    def do_POST(self):
        try:
            n=int(self.headers.get('Content-Length',0))
            if not 0<n<10_000_000:raise ValidationError('BODY_LIMIT')
            data=parse_qs(self.rfile.read(n).decode());self.page(preserve(json.loads(data['payload'][0])))
        except Exception as e:self.page('ERROR '+type(e).__name__+': '+str(e))
if __name__=='__main__':HTTPServer(('127.0.0.1',8766),Handler).serve_forever()
