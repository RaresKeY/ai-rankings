"""Exercise the static edition under a project prefix or its hosted URL."""
import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import signal
import tempfile
import threading
import time
from pathlib import Path

from browser_check import ROOT, browser_start


def check(url):
    process, cdp=browser_start(url)
    try:
        cdp.call('Runtime.enable');cdp.call('Page.enable');cdp.call('Network.enable')
        cdp.call('Network.setCacheDisabled',{'cacheDisabled':True})
        cdp.evaluate("localStorage.removeItem('ai-rankings-state-v1')")
        cdp.call('Page.reload',{'ignoreCache':True})
        for _ in range(200):
            if cdp.evaluate('Boolean(window.__rankings)'):break
            time.sleep(.2)
        assert cdp.evaluate('window.__rankings?.rows.length>0'),'No ranking rows'
        cdp.call('Emulation.setDeviceMetricsOverride',{'width':1560,'height':960,'deviceScaleFactor':1,'mobile':False})
        report={'url':url,'initial':cdp.evaluate("({rows:__rankings.rows.length,providers:[...new Set(__rankings.index.data.observations.map(o=>o.provider))],text:document.body.innerText.slice(0,250)})")}
        assert sorted(report['initial']['providers'])==['arena','epoch']
        cdp.screenshot('public-ranking')
        for view in ['frontier','matrix','compare','timeline','sensitivity','distribution','benchmarks','sources','data','method','charts']:
            cdp.evaluate(f'__rankings.set({{view:{json.dumps(view)}}})')
            assert cdp.evaluate('Boolean(document.querySelector("h1"))')
        for _ in range(100):
            if cdp.evaluate("document.querySelectorAll('#main svg.chart').length>0"):break
            time.sleep(.1)
        report['charts']=cdp.evaluate("({svg:document.querySelectorAll('#main svg.chart').length,text:document.querySelector('#main').innerText.slice(0,200)})")
        assert report['charts']['svg']>0,'Source chart did not load'
        cdp.evaluate("__rankings.set({view:'sources'})")
        assert cdp.evaluate("document.querySelector('#main').innerText.includes('CC BY 4.0')")
        assert not cdp.evaluate("Boolean(document.querySelector('[data-refresh-source]'))")
        cdp.screenshot('public-sources')
        cdp.evaluate("document.querySelector('[data-action=refresh]').click()")
        time.sleep(1)
        cdp.evaluate("__rankings.set({view:'rankings',inspectorTab:'weights'});document.querySelector('#preset').value='arena';document.querySelector('#preset').dispatchEvent(new Event('change',{bubbles:true}))")
        assert cdp.evaluate("__rankings.selectedTests().every(id=>__rankings.index.benchmarks.get(id).provider==='arena')")
        cdp.evaluate("__rankings.set({view:'matrix'});document.querySelector('[data-action=matrix-expand]').click()")
        report['selectedTests']=cdp.evaluate('__rankings.selectedTests().length')
        cdp.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        cdp.evaluate("__rankings.set({view:'rankings',showNav:false,showInspector:false})")
        report['mobile']=cdp.evaluate('({width:innerWidth,scroll:document.body.scrollWidth})')
        assert report['mobile']['width']==report['mobile']['scroll']
        cdp.screenshot('public-mobile')
        report['gpu']=cdp.evaluate("(()=>{const gl=document.createElement('canvas').getContext('webgl');const e=gl.getExtension('WEBGL_debug_renderer_info');return gl.getParameter(e.UNMASKED_RENDERER_WEBGL)})()")
        report['exceptions']=[e for e in cdp.events if e.get('method')=='Runtime.exceptionThrown']
        report['apiRequests']=[e['params']['request']['url'] for e in cdp.events if e.get('method')=='Network.requestWillBeSent' and '/api/' in e['params']['request']['url']]
        assert not report['exceptions'],report['exceptions']
        assert not report['apiRequests'],report['apiRequests']
        (ROOT/'.local/visual/public-report.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
    finally:
        cdp.socket.close()
        os.killpg(process.pid,signal.SIGTERM)
        try:process.wait(timeout=10)
        except Exception:os.killpg(process.pid,signal.SIGKILL)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url');args=parser.parse_args()
    if args.url:check(args.url)
    else:
        with tempfile.TemporaryDirectory(prefix='rankings-static-') as directory:
            (Path(directory)/'ai-rankings').symlink_to(ROOT/'dist',target_is_directory=True)
            server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(SimpleHTTPRequestHandler,directory=directory))
            threading.Thread(target=server.serve_forever,daemon=True).start()
            try:check(f'http://127.0.0.1:{server.server_port}/ai-rankings/')
            finally:server.shutdown()
