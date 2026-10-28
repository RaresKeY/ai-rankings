"""Compile official observations without losing provenance or conflating runs."""
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


def identity(label):
    # Conservative alias normalization. Original source label always survives.
    text = str(label).strip()
    text = re.sub(r"^(?:openai|anthropic|google|meta|moonshot(?: ai)?)\s*[/·:]\s*", "", text, flags=re.I)
    text = re.sub(r"\s*\((?:max|high|xhigh|medium|low|thinking|reasoning|non-reasoning|adaptive reasoning|default fallback)(?:[^)]*)\)\s*", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^Wonder(?=\s|$)", "Muse Wonder", text)
    text = re.sub(r"^GPT\s+(?=\d)", "GPT-", text, flags=re.I)
    # Decimal separators in endpoint names are unambiguous only for these families.
    text = re.sub(r"(gpt|claude|gemini|grok|glm|kimi)[- ](\d)[-](\d)(?=[- ]|$)", r"\1-\2.\3", text, flags=re.I)
    return slug(text), text


def infer_lab(name):
    n = name.lower()
    for prefixes, lab in [(("gpt", "o1", "o3", "o4", "chatgpt", "codex"), "OpenAI"), (("claude",), "Anthropic"), (("gemini", "gemma"), "Google"), (("muse", "llama", "wonder"), "Meta"), (("kimi",), "Moonshot AI"), (("grok",), "xAI"), (("deepseek",), "DeepSeek"), (("qwen", "qwq"), "Alibaba"), (("glm", "chatglm"), "Z AI"), (("mistral", "magistral", "codestral", "ministral"), "Mistral"), (("minimax",), "MiniMax"), (("mimo",), "Xiaomi"), (("nemotron",), "NVIDIA")]:
        if n.startswith(prefixes):
            return lab
    return "Unknown"


def canonical_lab(value):
    aliases = {
        "openai": "OpenAI", "anthropic": "Anthropic", "google": "Google",
        "googledeepmind": "Google", "meta": "Meta", "metaai": "Meta",
        "moonshot": "Moonshot AI", "moonshotai": "Moonshot AI", "kimi": "Moonshot AI",
        "zhipuai": "Z AI", "zai": "Z AI", "zhipu": "Z AI",
        "xai": "xAI", "spacexai": "xAI", "deepseek": "DeepSeek",
        "alibaba": "Alibaba", "qwen": "Alibaba", "minimax": "MiniMax",
        "mistral": "Mistral", "mistralai": "Mistral", "nvidia": "NVIDIA",
        "xiaomi": "Xiaomi", "cohere": "Cohere", "ai21labs": "AI21 Labs",
    }
    return aliases.get(re.sub(r"[^a-z0-9]", "", value.lower()), value)


def canonical_country(value):
    if not isinstance(value, str):
        return value
    return {"us": "United States", "usa": "United States", "united states of america": "United States",
            "cn": "China", "uk": "United Kingdom", "gb": "United Kingdom",
            "fr": "France", "ca": "Canada", "kr": "South Korea", "ae": "United Arab Emirates",
            "sg": "Singapore", "de": "Germany", "il": "Israel"}.get(value.lower(), value)


def compile_catalog(root=ROOT, source_dir=None):
    sources, benchmarks, observations, inventory, models = [], {}, [], [], {}
    visualizations, history = [], []
    problems = []
    for file in sorted((source_dir or root / "data/sources").glob("*.json")):
        try:
            pack = json.loads(file.read_text())
            provider = pack["provider"]
            for source in pack.get("sources", []):
                sources.append({**source, "provider": provider, "retrieved_at": pack.get("retrieved_at")})
            for benchmark in pack.get("benchmarks", []):
                b = dict(benchmark)
                b.setdefault("provider", provider)
                b.setdefault("category", "Other")
                b.setdefault("higher_is_better", True)
                b.setdefault("kind", "benchmark")
                if provider == "arena" and b.get("native_category", "").startswith("agent"):
                    b["unit"] = "pp"
                benchmarks[b["id"]] = b
            for raw in pack.get("observations", []):
                if raw.get("benchmark_id") not in benchmarks:
                    problems.append(f"{file.name}: unknown benchmark {raw.get('benchmark_id')}")
                    continue
                score = raw.get("score")
                if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
                    continue
                if not raw.get("source_url") or not raw.get("model"):
                    problems.append(f"{file.name}: observation missing attribution/model")
                    continue
                model_id, display = identity(raw["model"])
                lab = raw.get("lab") or infer_lab(display)
                lab = canonical_lab(lab)
                model = models.setdefault(model_id, {"id": model_id, "name": display, "lab": lab, "aliases": [], "providers": []})
                if raw["model"] not in model["aliases"]:
                    model["aliases"].append(raw["model"])
                if provider not in model["providers"]:
                    model["providers"].append(provider)
                if model["lab"] == "Unknown" and lab != "Unknown":
                    model["lab"] = lab
                for key in ("weights", "release_date", "country", "modalities", "context_tokens", "parameters", "active_parameters", "training_compute", "training_compute_flop"):
                    if raw.get(key) is not None and key not in model:
                        model[key] = canonical_country(raw[key]) if key == "country" else raw[key]
                obs = {**raw, "provider": provider, "model_id": model_id, "retrieved_at": pack.get("retrieved_at")}
                if raw.get("country") is not None:
                    obs["source_country"] = raw["country"]
                    obs["country"] = canonical_country(raw["country"])
                obs["id"] = hashlib.sha256(json.dumps(obs, sort_keys=True, default=str).encode()).hexdigest()[:16]
                observations.append(obs)
            inventory.extend({**i, "provider": provider} for i in pack.get("inventory", []))
            for i, visual in enumerate(pack.get("visualization_data", [])):
                visualizations.append({k: v for k, v in {**visual, "provider": provider, "source_index": i}.items() if k != "data"})
            for raw in pack.get("history", []):
                if raw.get("model") and isinstance(raw.get("score"), (int, float)):
                    mid, _ = identity(raw["model"])
                    history.append({**raw, "model_id": mid, "provider": provider})
        except (ValueError, KeyError, TypeError) as exc:
            problems.append(f"{file.name}: {exc}")
    seen = set()
    observations = [o for o in observations if not (o["id"] in seen or seen.add(o["id"]))]
    counts = {}
    for o in observations:
        counts[o["benchmark_id"]] = counts.get(o["benchmark_id"], 0) + 1
    for b in benchmarks.values():
        b["observation_count"] = counts.get(b["id"], 0)
    return {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(), "sources": sources, "benchmarks": list(benchmarks.values()), "models": list(models.values()), "observations": observations, "inventory": inventory, "visualizations": visualizations, "history": history, "problems": problems}


def write_catalog(root=ROOT):
    catalog = compile_catalog(root)
    path = root / "data/catalog.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    temp.replace(path)
    return catalog


if __name__ == "__main__":
    result = write_catalog()
    print(json.dumps({key: len(result[key]) for key in ("sources", "benchmarks", "models", "observations", "problems")}))
