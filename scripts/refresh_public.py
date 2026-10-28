"""Refresh the commercial-reuse allowlist, retaining failed source snapshots."""
import gzip
import importlib
import json
import subprocess
import time
import threading
import urllib.error
from datetime import datetime, timezone

from catalog import ROOT
from public_data import PROVIDERS, public_pack, write_pack
from refresh import Fetcher


class PublicFetcher(Fetcher):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.progress_lock=threading.Lock()
        self.request_count=0
        self.last_request=0

    def __call__(self, url):
        for attempt in range(4):
            try:
                with self.progress_lock:
                    time.sleep(max(0, .35-(time.monotonic()-self.last_request)))
                    self.last_request=time.monotonic()
                    self.request_count+=1
                    if self.request_count % 25 == 0:
                        print(f'Public source requests: {self.request_count}', flush=True)
                return super().__call__(url)
            except urllib.error.HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 3:
                    raise
                delay = exc.headers.get('Retry-After', '')
                time.sleep(min(60, int(delay)) if delay.isdigit() else 5 * 2 ** attempt)


def restore(root=ROOT):
    """Restore only approved snapshots from the last deployed branch, if present."""
    for provider in PROVIDERS:
        result = subprocess.run(['git', 'show', f'origin/gh-pages:data/snapshots/{provider}.json.gz'], cwd=root, capture_output=True)
        if result.returncode == 0:
            write_pack(json.loads(gzip.decompress(result.stdout)), root/'data/public')
        elif not (root/'data/public'/(provider+'.json')).exists():
            seed=root/'data/seed'/(provider+'.json.gz')
            if seed.exists():write_pack(json.loads(gzip.decompress(seed.read_bytes())), root/'data/public')


def refresh_public(root=ROOT, collectors=None, fetch_factory=None):
    directory = root/'data/public'
    directory.mkdir(parents=True, exist_ok=True)
    results = []
    for provider in PROVIDERS:
        path = directory/(provider+'.json')
        previous = public_pack(json.loads(path.read_text())) if path.exists() else None
        try:
            fetch = (fetch_factory or (lambda: PublicFetcher(root=root/'.local/public-fetch', cache=False)))()
            if not collectors and provider == 'epoch':
                licensing=fetch('https://epoch.ai/benchmarks/use-this-data').decode()
                if 'https://creativecommons.org/licenses/by/4.0/' not in licensing:
                    raise ValueError('Epoch licensing statement changed; review required')
            collect = collectors[provider] if collectors else importlib.import_module('adapters.'+provider).collect
            pack = public_pack(collect(fetch))
            if previous:
                old_tests = {o['benchmark_id'] for o in previous['observations']}
                new_tests = {o['benchmark_id'] for o in pack['observations']}
                if old_tests - new_tests:
                    raise ValueError(f'Import lost {len(old_tests-new_tests)} populated tests; adapter review required')
                if len(pack['observations']) < .8 * len(previous['observations']):
                    raise ValueError('Import lost over 20% of results; adapter review required')
            write_pack(pack, directory)
            result = {'provider':provider, 'status':'ok', 'observations':len(pack['observations']), 'retrieved_at':pack['retrieved_at']}
        except Exception as exc:
            if not previous:
                raise RuntimeError(f'{provider}: no usable snapshot: {exc}') from exc
            result = {'provider':provider, 'status':'error', 'error':str(exc), 'retained_previous':True, 'retrieved_at':previous['retrieved_at']}
        results.append(result)
        print(json.dumps(result), flush=True)
    status = {'finished_at':datetime.now(timezone.utc).isoformat(), 'sources':results}
    (directory/'update-status.json').write_text(json.dumps(status, indent=2))
    return status


if __name__ == '__main__':
    restore()
    refresh_public()
