"""Build a Pages-compatible static edition from approved source packs only."""
import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path
from catalog import ROOT, compile_catalog
from public_data import PROVIDERS, policy, public_pack


def write_json(path,data,compressed=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    path.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0) if compressed else raw)


def build(root=ROOT,output=None):
    output=Path(output or root/'dist').resolve()
    if output==root or output==root/'app' or not output.is_relative_to(root):
        raise ValueError('Static output must be a generated directory inside the project')
    if output.exists():shutil.rmtree(output)
    output.mkdir(parents=True)
    staging=root/'.local/public-build'
    staging.mkdir(parents=True,exist_ok=True)
    for file in staging.glob('*.json'):file.unlink()
    for provider in PROVIDERS:
        source=root/'data/public'/(provider+'.json')
        seed=root/'data/seed'/(provider+'.json.gz')
        if not source.exists() and not seed.exists():raise ValueError(f'Missing approved {provider} pack; run scripts/refresh_public.py')
        pack=public_pack(json.loads(source.read_text() if source.exists() else gzip.decompress(seed.read_bytes())))
        write_json(staging/(provider+'.json'),pack)
        write_json(output/'data/snapshots'/(provider+'.json.gz'),pack,True)
        for i,visual in enumerate(pack.get('visualization_data',[])):
            write_json(output/'data/charts'/f'{provider}-{i}.json.gz',visual,True)
    catalog=compile_catalog(root,source_dir=staging)
    if catalog['problems']:raise ValueError(catalog['problems'])
    catalog['publication']=policy()
    status=root/'data/public/update-status.json'
    catalog['updates']=json.loads(status.read_text()) if status.exists() else None
    for p in (root/'app').iterdir():
        if p.is_file():shutil.copy2(p,output/p.name)
    shutil.copy2(root/'icon.svg',output/'icon.svg')
    shutil.copy2(root/'THIRD_PARTY_NOTICES.md',output/'attribution.txt')
    write_json(output/'data/catalog.json.gz',catalog,True)
    write_json(output/'data/publication.json',policy())
    runtime={'mode':'static','catalog':'data/catalog.json.gz','repository':'https://github.com/RaresKeY/ai-rankings','schedule':'Daily at 05:37 UTC'}
    (output/'config.js').write_text('export const runtime = '+json.dumps(runtime)+';\n')
    (output/'.nojekyll').touch()
    manifest={'built_at':catalog['generated_at'],'providers':list(PROVIDERS),'observations':len(catalog['observations']),
              'benchmarks':len(catalog['benchmarks']),'models':len(catalog['models']),
              'files':{str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob('*') if p.is_file()}}
    write_json(output/'build.json',manifest)
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path);args=p.parse_args()
    result=build(output=args.output);print(json.dumps({k:v for k,v in result.items() if k!='files'}))
