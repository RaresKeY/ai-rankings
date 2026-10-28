"""Prepare a clean public source tree. Never copy the private Git history."""
import shutil
from pathlib import Path

from catalog import ROOT
from public_data import PROVIDERS, public_pack
from build_static import write_json
import json

FILES = ('AGENTS.md', 'README.md', 'THIRD_PARTY_NOTICES.md', '.gitignore', 'icon.svg', 'server.py', 'play.sh')
DIRECTORIES = ('app', 'scripts', 'tests', 'specs', '.github', 'ci')


def export(root=ROOT):
    output = root/'.local/public-source'
    if output.exists():shutil.rmtree(output)
    output.mkdir(parents=True)
    for name in FILES:
        shutil.copy2(root/name, output/name)
    for name in DIRECTORIES:
        shutil.copytree(root/name, output/name, ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for provider in PROVIDERS:
        pack = public_pack(json.loads((root/'data/public'/(provider+'.json')).read_text()))
        write_json(output/'data/seed'/(provider+'.json.gz'), pack, True)
    print(output)
    return output


if __name__ == '__main__':
    export()
