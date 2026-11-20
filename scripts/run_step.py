"""Record actual commands and exit statuses without turning partial runs into success."""
import argparse, datetime, hashlib, json, os, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('step');p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
    if a.command and a.command[0]=='--':a.command=a.command[1:]
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    d=ROOT/'artifacts/v3/execution'/f'{stamp}-{a.step}';d.mkdir(parents=True)
    fingerprint={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()
                 for base,pattern in [('stardew_agent','*.py'),('tests','*.py'),('scripts','*.py'),('web','*')]
                 for f in sorted((ROOT/base).glob(pattern)) if f.is_file()}
    (d/'code_manifest.json').write_text(json.dumps(fingerprint,sort_keys=True,indent=2))
    start=time.monotonic()
    with (d/'stdout.log').open('w') as out,(d/'stderr.log').open('w') as err:
        r=subprocess.run(a.command,cwd=ROOT,stdout=out,stderr=err)
    row={'step':a.step,'command':a.command,'cwd':str(ROOT),'exit_code':r.returncode,
         'elapsed_seconds':time.monotonic()-start,'artifacts':str(d.relative_to(ROOT)),
         'code_manifest':str((d/'code_manifest.json').relative_to(ROOT)),
         'code_manifest_sha256':hashlib.sha256((d/'code_manifest.json').read_bytes()).hexdigest(),
         'stdout':str((d/'stdout.log').relative_to(ROOT)),'stderr':str((d/'stderr.log').relative_to(ROOT))}
    (d/'record.json').write_text(json.dumps(row,ensure_ascii=False,indent=2))
    with (ROOT/'artifacts/v3/execution.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    print(json.dumps(row,ensure_ascii=False)); print((d/'stdout.log').read_text()[-4000:]);print((d/'stderr.log').read_text()[-2000:])
    return r.returncode
if __name__=='__main__':raise SystemExit(main())
