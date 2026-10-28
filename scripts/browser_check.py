#!/usr/bin/env python3
"""Offscreen Chromium through Gamescope; stdlib CDP transport, no packages."""
import base64
import hashlib
import json
import os
import signal
import socket
import struct
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CDP:
    def __init__(self, url):
        u = urllib.parse.urlparse(url)
        self.socket = socket.create_connection((u.hostname, u.port), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        self.socket.sendall((f"GET {u.path} HTTP/1.1\r\nHost: {u.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        header = b""
        while not header.endswith(b"\r\n\r\n"):
            header += self.socket.recv(1)
        if not header.startswith(b"HTTP/1.1 101 "):
            raise RuntimeError(header.decode())
        self.seq = 0
        self.events = []

    def read(self, n):
        data = b""
        while len(data) < n:
            block = self.socket.recv(n - len(data))
            if not block:
                raise EOFError("WebSocket closed")
            data += block
        return data

    def send(self, data, opcode=1):
        data = data if isinstance(data, bytes) else data.encode()
        mask = os.urandom(4)
        n = len(data)
        header = bytes([0x80 | opcode, 0x80 | (n if n < 126 else 126 if n < 65536 else 127)])
        if n >= 65536:
            header += struct.pack("!Q", n)
        elif n >= 126:
            header += struct.pack("!H", n)
        self.socket.sendall(header + mask + bytes(v ^ mask[i % 4] for i, v in enumerate(data)))

    def receive(self):
        message = b""
        while True:
            a, b = self.read(2)
            size = b & 127
            if size == 126:
                size = struct.unpack("!H", self.read(2))[0]
            elif size == 127:
                size = struct.unpack("!Q", self.read(8))[0]
            mask = self.read(4) if b & 128 else None
            body = self.read(size)
            if mask:
                body = bytes(v ^ mask[i % 4] for i, v in enumerate(body))
            if a & 15 == 9:
                self.send(body, 10)
                continue
            if a & 15 == 8:
                raise EOFError("WebSocket closed")
            message += body
            if a & 128:
                return json.loads(message)

    def call(self, method, params=None):
        self.seq += 1
        self.send(json.dumps({"id": self.seq, "method": method, "params": params or {}}))
        while True:
            reply = self.receive()
            if reply.get("id") == self.seq:
                if "error" in reply:
                    raise RuntimeError(reply["error"])
                return reply.get("result", {})
            self.events.append(reply)

    def evaluate(self, expression):
        reply = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        if reply.get("exceptionDetails"):
            raise RuntimeError(reply["exceptionDetails"])
        return reply.get("result", {}).get("value")

    def screenshot(self, name):
        image = self.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        (ROOT / ".local/visual" / (name + ".png")).write_bytes(base64.b64decode(image["data"]))


def browser_start(url="http://127.0.0.1:8768"):
    directory = ROOT / ".local/visual"
    directory.mkdir(parents=True, exist_ok=True)
    log = (directory / "gamescope.log").open("w")
    process = subprocess.Popen(["dbus-run-session", "--", "gamescope", "--backend", "headless", "--keep-alive", "-W", "1560", "-H", "1040", "-w", "1560", "-h", "1040", "--", "/usr/bin/chromium", "--ozone-platform=x11", "--no-first-run", "--no-default-browser-check", "--disable-background-networking", "--disable-component-update", "--disable-sync", "--password-store=basic", f"--user-data-dir={ROOT / '.local/chromium-qa'}", "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=9226", "--window-size=1560,1040", url], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(100):
        try:
            with urllib.request.urlopen("http://127.0.0.1:9226/json", timeout=1) as r:
                pages = json.load(r)
            page = next(p for p in pages if p["type"] == "page")
            return process, CDP(page["webSocketDebuggerUrl"])
        except Exception:
            if process.poll() is not None:
                raise RuntimeError((directory / "gamescope.log").read_text()[-4000:])
            time.sleep(.2)
    os.killpg(process.pid, signal.SIGTERM)
    raise TimeoutError("Chromium CDP did not start")


def main():
    process, cdp = browser_start()
    try:
        cdp.call("Runtime.enable")
        cdp.call("Page.enable")
        cdp.evaluate("localStorage.removeItem('ai-rankings-state-v1')")
        cdp.call("Page.reload", {"ignoreCache": True})
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1560, "height": 960, "deviceScaleFactor": 1, "mobile": False})
        for _ in range(150):
            if cdp.evaluate("Boolean(window.__rankings)"):
                break
            time.sleep(.2)
        report = {"initial": cdp.evaluate("({title:document.title,rows:window.__rankings?.rows.length,tests:window.__rankings?.index.data.benchmarks.length,body:document.body.innerText.slice(0,500)})")}
        if not report["initial"].get("rows"):
            report["errors"] = cdp.events
            (ROOT / ".local/visual/report.json").write_text(json.dumps(report, indent=2))
            cdp.screenshot("failed")
            raise AssertionError("Ranking did not load")
        cdp.screenshot("rankings-desktop")
        report["views"] = {}
        for view in ["frontier", "matrix", "compare", "timeline", "sensitivity", "distribution", "benchmarks", "sources", "data", "method", "charts"]:
            cdp.evaluate(f"window.__rankings.set({{view:{json.dumps(view)},page:0}})")
            time.sleep(.15)
            report["views"][view] = cdp.evaluate("({heading:document.querySelector('h1')?.textContent,svg:document.querySelectorAll('svg.chart').length,scrollWidth:document.body.scrollWidth,innerWidth:innerWidth})")
            if view in ("frontier", "matrix", "sources"):
                cdp.screenshot(view + "-desktop")
        # Exercise real UI handlers, not just renderer entry points.
        report["interactions"] = {}
        cdp.evaluate("window.__rankings.set({view:'rankings',weights:{'aa-intelligenceindex':100},query:'',lab:'',coverage:100,missing:'exclude',layout:'horizontal',inspectorTab:'weights'})")
        cdp.evaluate("document.querySelector('[data-view=matrix]').click();document.querySelector('[data-action=matrix-expand]').click()")
        report["interactions"]["expanded"] = cdp.evaluate("({tests:window.__rankings.selectedTests().length,rows:window.__rankings.rows.length})")
        assert report["interactions"]["expanded"]["tests"] >= 3
        cdp.evaluate("document.querySelector('[data-view=rankings]').click(); var t=document.querySelector('#stacked');t.checked=true;t.dispatchEvent(new Event('change',{bubbles:true}))")
        report["interactions"]["contributions"] = cdp.evaluate("({checked:window.__rankings.state.stacked,rects:document.querySelectorAll('svg.chart rect').length})")
        assert report["interactions"]["contributions"]["checked"]
        cdp.screenshot("contributions-desktop")
        cdp.evaluate("window.__rankings.set({view:'frontier',axisY:window.__rankings.selectedTests()[0],metric:'test:'+window.__rankings.selectedTests()[1],log:false})")
        assert cdp.evaluate("document.querySelectorAll('svg.chart circle').length")>0
        cdp.screenshot('benchmark-versus-benchmark')
        cdp.evaluate("window.__rankings.set({view:'rankings',axisY:'ranking',metric:'cost_usd',log:true})")
        cdp.evaluate("var t=document.querySelector('[data-weight-number]');t.value=73;t.dispatchEvent(new Event('change',{bubbles:true}))")
        assert 73 in cdp.evaluate("Object.values(window.__rankings.state.weights)")
        for view in ['compare','sensitivity','matrix']:
            cdp.evaluate(f"document.querySelector('[data-view={view}]').click()")
            assert cdp.evaluate("document.querySelectorAll('svg.chart,.heat-cell').length") > 0
            cdp.screenshot(view + "-custom")
        cdp.evaluate("document.querySelector('[data-view=rankings]').click();document.querySelector('svg [data-row]').dispatchEvent(new MouseEvent('click',{bubbles:true}))")
        report["interactions"]["evidence"] = cdp.evaluate("({tab:window.__rankings.state.inspectorTab,links:document.querySelectorAll('#inspector a').length,text:document.querySelector('#inspector').innerText.slice(0,500)})")
        assert report["interactions"]["evidence"]["links"] > 0
        cdp.evaluate("window.__rankings.set({inspectorTab:'weights'});var t=document.querySelector('#preset');t.value='professional';t.dispatchEvent(new Event('change',{bubbles:true}))")
        report["interactions"]["vals"] = cdp.evaluate("({tests:window.__rankings.selectedTests(),rows:window.__rankings.rows.length})")
        assert report["interactions"]["vals"]["rows"] > 0
        cdp.evaluate("window.__rankings.set({view:'charts',benchProvider:'vals',sourceChart:'',chartPath:'',chartY:'',chartX:'',chartLabel:'',chartMode:'bars'})")
        for _ in range(100):
            if cdp.evaluate("Boolean(document.querySelector('#chartPath'))"): break
            time.sleep(.1)
        report["interactions"]["sourceChart"] = cdp.evaluate("({series:document.querySelector('#chartPath')?.options.length,svg:document.querySelectorAll('svg.chart').length,heading:document.querySelector('#source-chart-content h3')?.textContent})")
        assert report["interactions"]["sourceChart"]["series"] > 0
        assert report["interactions"]["sourceChart"]["svg"] == 1
        cdp.screenshot("source-chart-desktop")
        cdp.evaluate("window.__rankings.set({sourceChart:'vals:3',chartPath:'',chartY:'',chartX:'',chartLabel:''})")
        for _ in range(100):
            if cdp.evaluate("document.querySelector('#source-chart-content')?.innerText.includes('shared results table')"): break
            time.sleep(.1)
        report['interactions']['sharedSourceChart']=cdp.evaluate("({series:document.querySelector('#chartPath')?.options.length,svg:document.querySelectorAll('svg.chart').length,origin:document.querySelector('#source-chart-content')?.innerText.includes('shared results table')})")
        assert report['interactions']['sharedSourceChart']['origin']
        assert report['interactions']['sharedSourceChart']['svg']==1
        cdp.screenshot('source-chart-results')
        cdp.evaluate("var t=document.querySelector('#chartMode');t.value='scatter';t.dispatchEvent(new Event('change',{bubbles:true}))")
        assert cdp.evaluate("Boolean(document.querySelector('#chartX'))")
        downloads=ROOT/'.local/visual/downloads'/str(time.time_ns());downloads.mkdir(parents=True,exist_ok=True)
        cdp.call('Browser.setDownloadBehavior',{'behavior':'allow','downloadPath':str(downloads)})
        cdp.evaluate("document.querySelector('[data-action=chart-json]').click();window.__rankings.set({view:'rankings',weights:{'aa-intelligenceindex':100},stacked:false});document.querySelector('[data-action=export]').click();document.querySelector('[data-action=svg]').click()")
        for _ in range(50):
            if len(list(downloads.glob('*')))>=3: break
            time.sleep(.1)
        report['interactions']['exports']=[p.name for p in downloads.iterdir() if not p.name.endswith('.crdownload')]
        assert len(report['interactions']['exports'])>=3
        report["errors"] = [event for event in cdp.events if event.get("method") == "Runtime.exceptionThrown"]
        cdp.evaluate("window.__rankings.set({view:'rankings'})")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
        time.sleep(.2)
        cdp.screenshot("rankings-mobile")
        report['mobileNav']=cdp.evaluate("({display:getComputedStyle(document.querySelector('.nav-toggle')).display,width:document.querySelector('.nav-toggle').getBoundingClientRect().width})")
        assert report['mobileNav']['display']!='none'
        cdp.evaluate("document.querySelector('[data-action=nav]').click()")
        assert cdp.evaluate("getComputedStyle(document.querySelector('.sidebar')).display")!='none'
        cdp.screenshot('navigation-mobile')
        cdp.evaluate("document.querySelector('[data-view=sources]').click();document.querySelector('[data-action=inspector]').click()")
        assert cdp.evaluate("getComputedStyle(document.querySelector('.inspector')).display")!='none'
        cdp.screenshot('controls-mobile')
        cdp.evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));window.__rankings.set({view:'rankings'})")
        report["mobile"] = cdp.evaluate("({scrollWidth:document.body.scrollWidth,innerWidth:innerWidth,mainWidth:document.querySelector('main').clientWidth})")
        with urllib.request.urlopen("http://127.0.0.1:9226/json/version") as r:
            browser = CDP(json.load(r)["webSocketDebuggerUrl"])
        report["gpu"] = browser.call("SystemInfo.getInfo").get("gpu")
        (ROOT / ".local/visual/report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps({"initial":report["initial"],"views":report["views"],"interactions":report["interactions"],"errors":len(report["errors"]),"mobile":report["mobile"],"gpu":report["gpu"].get("devices")}, indent=2))
    finally:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


if __name__ == "__main__":
    main()
