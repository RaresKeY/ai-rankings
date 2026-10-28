"""Wait for the candidate's Pages build and verify the published manifest."""
import hashlib
import json
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPOSITORY='RaresKeY/ai-rankings'
BASE='https://rareskey.github.io/ai-rankings/'


def verify(timeout=600):
    expected=json.loads((ROOT/'dist/build.json').read_text())
    deadline=time.monotonic()+timeout
    failure='Waiting for Pages publication'
    while time.monotonic()<deadline:
        try:
            with urllib.request.urlopen(BASE+'build.json?build='+hashlib.sha256((ROOT/'dist/build.json').read_bytes()).hexdigest()[:16],timeout=30) as response:
                actual=json.load(response)
            if actual==expected:
                for name in ('index.html','app.js','config.js','data/catalog.json.gz'):
                    with urllib.request.urlopen(BASE+name+'?build='+expected['files'][name][:12],timeout=30) as response:
                        digest=hashlib.sha256(response.read()).hexdigest()
                    if digest!=expected['files'][name]:raise ValueError('Hosted hash mismatch: '+name)
                print('Verified hosted build:',expected['built_at'],BASE)
                return
            failure='Pages still serves an earlier build'
        except Exception as exc:failure=str(exc)
        time.sleep(5)
    raise TimeoutError(failure)


if __name__=='__main__':verify()
