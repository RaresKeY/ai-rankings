"""Startup updates must not block saved results or overlap another refresh."""
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root/'data').mkdir()
        self.catalog = self.root/'data/catalog.json'
        self.catalog.write_text('{"observations":[{"score":10}]}')
        self.entered, self.release = threading.Event(), threading.Event()
        self.calls = []
        self.patches = [patch.object(server, 'ROOT', self.root), patch.object(server, 'refresh', self.fake_refresh),
                        patch.dict(server.state, running=False, messages=[], result=None, run_id=None,
                                   started_at=None, finished_at=None, reason=None, error=None, clear=True)]
        for item in self.patches:item.start()
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.http.server_port}'

    def tearDown(self):
        self.release.set()
        self.wait_finished()
        self.http.shutdown();self.http.server_close();self.thread.join(timeout=2)
        for item in reversed(self.patches):item.stop()
        self.directory.cleanup()

    def fake_refresh(self, names, callback, cache):
        self.calls.append((tuple(names), cache))
        callback('Reading test source')
        self.entered.set()
        if not self.release.wait(5):raise TimeoutError('test release missing')
        self.catalog.write_text('{"observations":[{"score":20}]}')
        return [{'provider':name, 'status':'ok'} for name in names]

    def wait_finished(self):
        deadline = time.monotonic()+6
        while server.refresh_status()['running'] and time.monotonic()<deadline:time.sleep(.01)
        self.assertFalse(server.refresh_status()['running'])

    def post(self, origin=True):
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=self.base
        request=urllib.request.Request(self.base+'/api/refresh',data=b'{"startup":true}',headers=headers)
        try:return urllib.request.urlopen(request,timeout=2)
        except urllib.error.HTTPError as exc:
            exc.close();raise

    def test_saved_data_served_during_fresh_startup_import(self):
        self.assertTrue(server.start_refresh(reason='startup'))
        self.assertTrue(self.entered.wait(2))
        self.assertFalse(server.start_refresh(reason='startup'))
        with urllib.request.urlopen(self.base+'/api/data',timeout=2) as response:
            self.assertEqual(json.load(response)['observations'][0]['score'],10)
        self.assertEqual(self.calls,[(server.ADAPTERS,False)])
        self.release.set();self.wait_finished()
        self.assertEqual(json.loads(self.catalog.read_text())['observations'][0]['score'],20)
        status=server.refresh_status()
        self.assertEqual(status['reason'],'startup')
        self.assertTrue(status['finished_at'])
        self.assertTrue(status['run_id'])

    def test_reused_server_accepts_launch_and_rejects_duplicate(self):
        with self.post() as response:self.assertEqual(response.status,202)
        self.assertTrue(self.entered.wait(2))
        with self.assertRaises(urllib.error.HTTPError) as caught:self.post()
        self.assertEqual(caught.exception.code,409)
        with self.assertRaises(urllib.error.HTTPError) as caught:self.post(origin=False)
        self.assertEqual(caught.exception.code,403)
        self.assertEqual(len(self.calls),1)

    def test_update_failure_preserves_saved_results(self):
        before=self.catalog.read_bytes()
        with patch.object(server,'refresh',side_effect=OSError('offline')):
            server.start_refresh(reason='startup');self.wait_finished()
        self.assertEqual(self.catalog.read_bytes(),before)
        self.assertEqual(server.refresh_status()['error'],'offline')
