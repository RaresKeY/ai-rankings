"""Run dependency-free calculation tests in an installed browser."""
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
browser=next((shutil.which(n) for n in ('google-chrome','chromium','chromium-browser') if shutil.which(n)),None)
if not browser:raise SystemExit('An installed Chromium browser is required')
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
try:
    with tempfile.TemporaryDirectory(prefix='rankings-tests-') as profile:
        command=[browser,'--headless','--disable-gpu','--disable-background-networking','--disable-component-update','--no-first-run',f'--user-data-dir={profile}','--dump-dom','--virtual-time-budget=15000',f'http://127.0.0.1:{server.server_port}/tests/browser-tests.html']
        result=subprocess.run(command,capture_output=True,text=True,timeout=45)
        if result.returncode or '<pre id="result">PASS ' not in result.stdout:
            raise SystemExit(result.stdout+'\n'+result.stderr[-2000:])
        print('Browser calculation tests passed')
finally:server.shutdown()
