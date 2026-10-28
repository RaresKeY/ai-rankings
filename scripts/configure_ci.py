"""Generate the workflow with reviewed TLS roots available before checkout."""
import base64
import gzip
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
bundle=(ROOT/'ci/ca-bundle.pem').read_bytes()
digest=(ROOT/'ci/ca-bundle.sha256').read_text().strip()
if hashlib.sha256(bundle).hexdigest()!=digest:raise SystemExit('Reviewed TLS bundle hash changed')
encoded=base64.b64encode(gzip.compress(bundle,mtime=0)).decode()
workflow='''name: Update data and publish
on:
  push:
    branches: [main]
  schedule:
    - cron: '37 5 * * *'
  workflow_dispatch:
permissions:
  contents: write
  pages: write
concurrency:
  group: public-site
  cancel-in-progress: false
jobs:
  publish:
    if: github.repository == 'RaresKeY/ai-rankings'
    runs-on: ubuntu-24.04
    timeout-minutes: 40
    steps:
      - name: Configure reviewed TLS trust before network access
        shell: bash
        run: |
          python3 - <<'PY'
          import base64, gzip, hashlib, os
          from pathlib import Path
          raw=gzip.decompress(base64.b64decode('BUNDLE_DATA'))
          assert hashlib.sha256(raw).hexdigest() == 'BUNDLE_HASH'
          directory=Path(os.environ['RUNNER_TEMP'])/'rankings-tls'
          directory.mkdir(exist_ok=True)
          (directory/'empty').mkdir(exist_ok=True)
          bundle=directory/'ca.pem'
          bundle.write_bytes(raw)
          values={key:str(bundle) for key in ('SSL_CERT_FILE','CURL_CA_BUNDLE','REQUESTS_CA_BUNDLE','PIP_CERT','GIT_SSL_CAINFO')}
          values.update(SSL_CERT_DIR=str(directory/'empty'),GIT_SSL_CAPATH=str(directory/'empty'))
          with open(os.environ['GITHUB_ENV'],'a') as output:
              for key,value in values.items():output.write(f'{key}={value}\\n')
          PY
      - name: Checkout the triggering source revision
        shell: bash
        env:
          SOURCE_SHA: ${{ github.sha }}
        run: |
          git init .
          git remote add origin https://github.com/RaresKeY/ai-rankings.git
          git fetch --depth=1 origin "$SOURCE_SHA"
          git checkout --detach FETCH_HEAD
          git fetch --depth=1 origin gh-pages:refs/remotes/origin/gh-pages
      - name: Validate source and calculations
        run: |
          python3 -m unittest discover -s tests -v
          python3 scripts/browser_unit_tests.py
      - name: Restore last published data
        run: python3 scripts/refresh_public.py --restore-only
      - name: Update approved sources
        if: github.event_name != 'push'
        run: python3 scripts/refresh_public.py
      - name: Build public website
        run: python3 scripts/build_static.py
      - name: Publish and request Pages build
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          gh auth setup-git
          git config user.name 'github-actions[bot]'
          git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
          python3 scripts/publish_pages.py
      - name: Verify hosted files
        run: python3 scripts/verify_hosted.py
      - name: Report incomplete refresh
        if: always()
        run: |
          python3 - <<'PY'
          import json
          from pathlib import Path
          path=Path('data/public/update-status.json')
          if path.exists():
              status=json.loads(path.read_text())
              failures=[s for s in status['sources'] if s['status']!='ok']
              if failures:raise SystemExit('Previous data retained for: '+', '.join(s['provider'] for s in failures))
          PY
'''.replace('BUNDLE_DATA',encoded).replace('BUNDLE_HASH',digest)
path=ROOT/'.github/workflows/update.yml'
path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(workflow)
print(path)
