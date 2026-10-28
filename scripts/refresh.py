"""Refresh curated public sources, retaining the last successful source pack."""
import argparse
import gzip
import hashlib
import importlib
import json
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from catalog import ROOT, write_catalog

ADAPTERS = ("aa", "vals", "epoch", "arena", "terminalbench", "swebench")
HOSTS = {"artificialanalysis.ai", "www.artificialanalysis.ai", "vals.ai", "www.vals.ai", "epoch.ai", "www.epoch.ai", "arena.ai", "lmarena.ai", "www.tbench.ai", "tbench.ai", "www.swebench.com", "swebench.com", "raw.githubusercontent.com", "github.com", "api.github.com", "huggingface.co", "datasets-server.huggingface.co", "cdn-lfs.huggingface.co", "cdn-lfs-us-1.huggingface.co", "cdn-lfs.hf.co"}
HOSTS.add("ofhuhcpkvzjlejydnvyd.supabase.co")


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_url(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError(f"Unapproved data origin: {parsed.hostname}")
    if parsed.hostname == "ofhuhcpkvzjlejydnvyd.supabase.co" and parsed.path != "/functions/v1/leaderboard-read":
        raise ValueError("Only the official Terminal-Bench public reader is allowed")


class Fetcher:
    def __init__(self, root=ROOT, cache=True):
        self.root = root
        self.cache = cache
        self.records = []
        self.opener = urllib.request.build_opener(SafeRedirect, urllib.request.HTTPSHandler(context=ssl.create_default_context()))

    def __call__(self, url):
        validate_url(url)
        key = hashlib.sha256(url.encode()).hexdigest()
        directory = self.root / "data/raw"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (key + ".gz")
        meta = directory / (key + ".json")
        if self.cache and path.exists() and time.time() - path.stat().st_mtime < 21600:
            data = gzip.decompress(path.read_bytes())
            self.records.append(json.loads(meta.read_text()))
            return data
        request = urllib.request.Request(url, headers={"User-Agent": "AI-Rankings/1.0 (local research explorer)", "Accept": "application/json,text/csv,text/html,*/*"})
        with self.opener.open(request, timeout=45) as response:
            data = response.read(64 * 1024 * 1024 + 1)
            if len(data) > 64 * 1024 * 1024:
                raise ValueError("Source response exceeded 64 MiB")
            record = {"url": url, "final_url": response.url, "retrieved_at": datetime.now(timezone.utc).isoformat(), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "content_type": response.headers.get("Content-Type", "")}
        path.write_bytes(gzip.compress(data))
        meta.write_text(json.dumps(record, indent=2))
        self.records.append(record)
        return data


def refresh(names=ADAPTERS, callback=print, cache=True):
    summary = []
    for name in names:
        if name not in ADAPTERS:
            raise ValueError("Unknown source")
        callback(f"Reading {name}")
        fetcher = Fetcher(cache=cache)
        try:
            adapter = importlib.import_module("adapters." + name)
            pack = adapter.collect(fetcher)
            if not pack.get("observations"):
                raise ValueError("No observations extracted; previous data retained")
            previous_path = ROOT / "data/sources" / (name + ".json")
            if previous_path.exists():
                previous = json.loads(previous_path.read_text())
                old_tests = {o["benchmark_id"] for o in previous.get("observations", [])}
                new_tests = {o["benchmark_id"] for o in pack["observations"]}
                missing_tests = old_tests - new_tests
                if missing_tests:
                    raise ValueError(f"Import lost {len(missing_tests)} previously populated test series; retaining the full previous snapshot. Source changes require adapter review.")
            pack["fetch_records"] = fetcher.records
            pack.setdefault("retrieved_at", datetime.now(timezone.utc).isoformat())
            serialized = json.dumps(pack, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            path = ROOT / "data/sources" / (name + ".json")
            if path.exists():
                history = ROOT / "data/history" / name
                history.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                (history / (stamp + ".json.gz")).write_bytes(gzip.compress(path.read_bytes()))
                for old in sorted(history.glob("*.json.gz"))[:-12]:
                    old.unlink()
            temp = path.with_suffix(".tmp")
            temp.write_text(serialized)
            temp.replace(path)
            item = {"provider": name, "status": "ok", "observations": len(pack["observations"]), "benchmarks": len(pack["benchmarks"])}
        except Exception as exc:
            item = {"provider": name, "status": "error", "error": str(exc), "retained_previous": (ROOT / "data/sources" / (name + ".json")).exists()}
        summary.append(item)
        callback(json.dumps(item))
    write_catalog()
    (ROOT / "data/refresh-status.json").write_text(json.dumps({"finished_at": datetime.now(timezone.utc).isoformat(), "sources": summary}, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs="*", choices=ADAPTERS, default=list(ADAPTERS))
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()
    refresh(args.sources or ADAPTERS, cache=not args.no_cache)
