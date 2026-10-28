"""Publish reviewed static output only, without changing the source checkout."""
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from catalog import ROOT

REPOSITORY = 'RaresKeY/ai-rankings'


def git(*args, env=None, input=None):
    return subprocess.check_output(['git', *args], cwd=(env.get('GIT_WORK_TREE', ROOT) if env else ROOT), env=env, input=input).decode().strip()


def publish():
    remote = git('remote', 'get-url', '--push', 'origin')
    if remote not in (f'https://github.com/{REPOSITORY}.git', f'git@github.com:{REPOSITORY}.git'):
        raise ValueError('Unexpected publishing destination')
    output = ROOT/'dist'
    manifest = json.loads((output/'build.json').read_text())
    if manifest['providers'] != ['arena','epoch']:
        raise ValueError('Unapproved providers in build')
    actual = {str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob('*') if p.is_file() and p.name != 'build.json'}
    if actual != manifest['files']:
        raise ValueError('Build files changed after validation')
    old = git('ls-remote','origin','refs/heads/gh-pages').split()
    expected = old[0] if old else ''
    with tempfile.TemporaryDirectory(prefix='rankings-index-') as temporary:
        env = {**os.environ, 'GIT_INDEX_FILE':str(Path(temporary)/'index'), 'GIT_WORK_TREE':str(output), 'GIT_DIR':git('rev-parse','--absolute-git-dir')}
        git('read-tree','--empty',env=env)
        git('add','--all','--force','.',env=env)
        tree = git('write-tree',env=env)
        # Generated branch has one current snapshot, so daily binary data does not accumulate.
        commit = git('commit-tree',tree, '-m',f'Publish approved data {manifest["built_at"]}')
        git('push',f'--force-with-lease=refs/heads/gh-pages:{expected}','origin',f'{commit}:refs/heads/gh-pages')
    print(commit)
    subprocess.run(['gh','api','--method','POST',f'repos/{REPOSITORY}/pages/builds'],check=True)


if __name__ == '__main__':
    publish()
