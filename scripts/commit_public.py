"""Commit the reviewed public export on local public without switching checkout."""
import os
from pathlib import Path
import re
import subprocess
import tempfile

from catalog import ROOT
from export_public_repo import export


def git(*args,env=None,cwd=ROOT):
    return subprocess.check_output(['git',*args],cwd=cwd,env=env).decode().strip()


def commit():
    output=export()
    for file in output.rglob('*'):
        if not file.is_file():continue
        if any(p in ('.git','.local','sources','raw','__pycache__') for p in file.relative_to(output).parts):
            raise ValueError('Excluded path: '+str(file))
        if file.suffix!='.gz' and re.search(r'(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (RSA |EC )?PRIVATE KEY-----)',file.read_text()):
            raise ValueError('Possible credential: '+str(file))
    parent=subprocess.run(['git','rev-parse','--verify','refs/heads/public'],cwd=ROOT,capture_output=True,text=True)
    parents=['-p',parent.stdout.strip()] if parent.returncode==0 else []
    if parents and subprocess.run(['git','merge-base','--is-ancestor','6955a37',parent.stdout.strip()],cwd=ROOT,capture_output=True).returncode==0:
        raise ValueError('Public branch contains private source history')
    with tempfile.TemporaryDirectory(prefix='rankings-source-') as temporary:
        env={**os.environ,'GIT_DIR':git('rev-parse','--absolute-git-dir'),'GIT_WORK_TREE':str(output),'GIT_INDEX_FILE':str(Path(temporary)/'index')}
        git('read-tree','--empty',env=env,cwd=output)
        git('add','--force','--all','.',env=env,cwd=output)
        tree=git('write-tree',env=env,cwd=output)
        if parents and git('rev-parse',parent.stdout.strip()+'^{tree}')==tree:
            print('Public source already current');return
        sha=git('commit-tree',tree,*parents,'-m','Update public site, data policy and publishing checks')
        git('update-ref','refs/heads/public',sha,parent.stdout.strip() if parents else '0'*40)
        print('Public commit:',sha)


if __name__=='__main__':commit()
