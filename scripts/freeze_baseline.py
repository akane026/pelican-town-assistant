"""Freeze existing evidence before implementation; replay only in an isolated copy."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, shutil, subprocess, sys, tarfile, time

ROOT = Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    dest = ROOT / 'artifacts/v3' / run_id / 'baseline'
    dest.mkdir(parents=True)
    paths = sorted(p for folder in ('verification', 'requirements') for p in (ROOT/folder).rglob('*')
                   if p.is_file() and '__pycache__' not in p.parts and '.DS_Store' not in p.parts)
    before = {str(p.relative_to(ROOT)): {'sha256':sha(p),'bytes':p.stat().st_size} for p in paths}
    archive = dest/'original.tar.gz'
    with tarfile.open(archive, 'w:gz') as t:
        for p in paths: t.add(p, arcname=p.relative_to(ROOT), recursive=False)
    archive.chmod(0o444)
    replay = dest/'replay'
    for directory in ('verification','requirements'):
        shutil.copytree(ROOT/directory, replay/directory, ignore=shutil.ignore_patterns('__pycache__','.DS_Store'))
    command = [str(ROOT/'.venv/bin/python'), '-m', 'verification.run_all','--offline']
    start = time.monotonic()
    result = subprocess.run(command, cwd=replay, capture_output=True, text=True, timeout=240)
    (dest/'stdout.log').write_text(result.stdout)
    (dest/'stderr.log').write_text(result.stderr)
    after = {str(p.relative_to(ROOT)):sha(p) for p in paths}
    unchanged = all(after[k] == v['sha256'] for k,v in before.items())
    manifest = dict(run_id=run_id, command=command, cwd=str(replay), exit_code=result.returncode,
                    elapsed_seconds=time.monotonic()-start, original_files=before,
                    archive_sha256=sha(archive), original_unchanged=unchanged,
                    outcome='PARTIAL' if result.returncode==2 else 'FAIL',
                    limitations=['Legacy diagnostics are not V3 product acceptance.','No online model calls repeated.'])
    (dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    (ROOT/'artifacts/v3/baseline_pointer.json').write_text(json.dumps({'directory':str(dest.relative_to(ROOT))}))
    print(json.dumps({k:manifest[k] for k in ('run_id','exit_code','original_unchanged','elapsed_seconds','outcome')}))
    return 0 if unchanged and result.returncode == 2 else 1
if __name__=='__main__': raise SystemExit(main())
