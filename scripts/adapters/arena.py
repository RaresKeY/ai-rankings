"""Official Arena public leaderboard snapshots via Hugging Face's rows API.

No hosted model calls, parquet dependency or third-party leaderboard mirrors.
All latest snapshots are imported, plus a separate dated Agent Arena history.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlencode

DATASET = 'lmarena-ai/leaderboard-dataset'
DATA_URL = 'https://huggingface.co/datasets/' + DATASET
SPLITS_URL = 'https://datasets-server.huggingface.co/splits?' + urlencode({'dataset': DATASET})
README_URL = DATA_URL + '/raw/main/README.md'
METHOD_URL = 'https://arena.ai/blog/leaderboard-changelog'
AGENT_METHOD_URL = 'https://arena.ai/blog/agent-arena-methodology'
LABELS = {
    'text': 'Text', 'text_style_control': 'Text · style controlled',
    'text_factuality': 'Text · factuality', 'vision': 'Vision',
    'vision_style_control': 'Vision · style controlled', 'search': 'Search',
    'search_style_control': 'Search · style controlled', 'search_factuality': 'Search · factuality',
    'document': 'Document', 'document_style_control': 'Document · style controlled',
    'webdev': 'WebDev', 'text_to_image': 'Text to image', 'image_edit': 'Image edit',
    'text_to_video': 'Text to video', 'image_to_video': 'Image to video', 'video_edit': 'Video edit',
    'agent': 'Agent · overall', 'agent_bash_recovery_steps': 'Agent · bash recovery (retired)',
    'agent_bash_reliability': 'Agent · bash reliability',
    'agent_praise_complaint': 'Agent · praise vs complaint',
    'agent_steerability': 'Agent · steerability',
    'agent_task_outcome_explicit': 'Agent · confirmed success',
    'agent_tool_hallucination': 'Agent · tool hallucination',
}


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def slug(value):
    return re.sub(r'[^a-z0-9]+', '-', str(value).lower()).strip('-')


def rows_url(config, offset=0, split='latest'):
    return 'https://datasets-server.huggingface.co/rows?' + urlencode({
        'dataset': DATASET, 'config': config, 'split': split, 'offset': offset, 'length': 100,
    })


def read_rows(fetch, config, split='latest'):
    """Read every page, rejecting unexpected truncation instead of hiding it."""
    rows, offset = [], 0
    while True:
        for attempt in range(6):
            try:
                payload = json.loads(fetch(rows_url(config, offset, split)))
                break
            except HTTPError as exc:
                if exc.code != 429 or attempt == 5:
                    raise
                retry = exc.headers.get('Retry-After', '30')
                delay = float(retry) if retry.isdigit() else 30
                time.sleep(min(60, max(10, delay)))
        page = payload.get('rows', [])
        if payload.get('partial') or any(item.get('truncated_cells') for item in page):
            raise ValueError('Hugging Face returned partial/truncated ' + config)
        for item in page:
            row = dict(item['row'])
            row['_source_url'] = rows_url(config, offset, split)
            row['_row_index'] = item.get('row_idx')
            rows.append(row)
        total = payload['num_rows_total']
        if len(rows) >= total:
            return rows
        if not page:
            raise ValueError('Hugging Face pagination stopped before end: ' + config)
        offset += len(page)


def arena_category(config, native):
    if config.startswith('agent'):
        return 'Knowledge work'
    if config in ('vision', 'vision_style_control', 'image_edit', 'image_to_video',
                  'text_to_image', 'text_to_video', 'video_edit'):
        return 'Multimodal'
    if config == 'webdev' or native in ('coding', 'coding_hard'):
        return 'Coding'
    if native in ('math', 'math_hard'):
        return 'Math'
    return 'Preference'


def parse_rows(config, rows):
    benchmarks, observations = {}, []
    agent = config.startswith('agent')
    for row in rows:
        metric = 'score' if agent else 'rating'
        if not number(row.get(metric)) or not row.get('model_name'):
            continue
        native = row.get('category') or 'overall'
        bid = 'arena-' + slug(config) + '-' + slug(native)
        label = LABELS.get(config, config.replace('_', ' ').title())
        label += '' if native == 'overall' else ' · ' + native.replace('_', ' ')
        if bid not in benchmarks:
            benchmarks[bid] = {
                'id': bid, 'name': 'Arena ' + label, 'provider': 'arena',
                'category': arena_category(config, native), 'native_category': config + '/' + native,
                'unit': 'pp' if agent else 'score', 'higher_is_better': True,
                'min': None, 'max': None, 'version': 'latest/' + config,
                'source_url': 'https://arena.ai/leaderboard', 'dataset_url': DATA_URL + '/viewer/' + config + '/latest',
                'description': ('Causal IPS net improvement, displayed in percentage points; not task accuracy. '
                                'Higher means better, including negatively coded failure signals. '
                                'Bash recovery was replaced by bash reliability on 2026-10-12.' if agent else
                                'Human preference Bradley–Terry rating. Different categories and style controls '
                                'are distinct populations, not a shared absolute ability scale.'),
                'private': None, 'kind': 'composite' if config == 'agent' else 'benchmark',
            }
        factor = 100 if agent else 1
        license_name = row.get('license') or ''
        weights = 'proprietary' if license_name.lower() == 'proprietary' else (
            'open' if license_name and license_name.lower() not in ('-', 'other', 'unknown') else 'unknown')
        model = row['model_name']
        effort_match = re.search(r'\((Low|Medium|High|xHigh|Max|Ultra)\)\s*$', model, re.I)
        item = {
            'benchmark_id': bid, 'model': model, 'lab': row.get('organization') or 'Unknown',
            'score': row[metric] * factor, 'source_url': row.get('_source_url') or rows_url(config),
            'source_row_index': row.get('_row_index'),
            'effort': effort_match.group(1).lower() if effort_match else None,
            'harness': 'Arena Agent Mode' if agent else 'Arena blind pairwise comparison',
            'date': row.get('leaderboard_publish_date'), 'weights': weights,
            'source_model_id': model, 'rank': row.get('rank'), 'model_license': license_name or None,
            'notes': ('Official latest snapshot; category ' + native + '; ' +
                      ('IPS net improvement × 100 (percentage points), not success rate. ' if agent else
                       'Bradley–Terry rating; ' + ('style controlled. ' if config.endswith('style_control') else 'raw category setting. ')) +
                      'License field copied from Arena; open indicates a non-proprietary listed license.'),
        }
        for target, source in [('ci_low', 'score_ci_lower' if agent else 'rating_lower'),
                               ('ci_high', 'score_ci_upper' if agent else 'rating_upper')]:
            if number(row.get(source)):
                item[target] = row[source] * factor
        for field in ('vote_count', 'observation_count', 'session_count', 'variance'):
            if number(row.get(field)):
                item[field] = row[field]
        observations.append(item)
    return list(benchmarks.values()), observations


def collect(fetch):
    splits = json.loads(fetch(SPLITS_URL))
    readme = fetch(README_URL).decode('utf-8')
    license_match = re.search(r'^license:\s*(.+)$', readme, re.M)
    license_name = license_match.group(1).strip() if license_match else 'Not stated'
    configs = sorted({item['config'] for item in splits['splits'] if item['split'] == 'latest'})
    pack = {'schema_version': 1, 'provider': 'arena',
            'retrieved_at': datetime.now(timezone.utc).isoformat(),
            'sources': [], 'benchmarks': [], 'observations': [], 'history': [], 'inventory': []}
    def one(config):
        try:
            return config, parse_rows(config, read_rows(fetch, config)), None
        except Exception as exc:
            return config, ([], []), str(exc)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(one, configs))
    for config, (benchmarks, observations), error in results:
        pack['benchmarks'].extend(benchmarks)
        pack['observations'].extend(observations)
        pack['sources'].append({
            'id': 'arena-' + slug(config), 'name': 'Arena · ' + LABELS.get(config, config),
            'url': 'https://arena.ai/leaderboard', 'data_url': rows_url(config),
            'methodology_url': AGENT_METHOD_URL if config.startswith('agent') else METHOD_URL,
            'status': 'unavailable' if error else 'ok', 'license': license_name,
            'notes': 'Official Arena Hugging Face dataset. All latest rows paginated through the public JSON API. '
                     'Source publication dates retained. ' + (error or f'{len(observations)} observations in {len(benchmarks)} categories.'),
        })
        pack['inventory'].append({'name': LABELS.get(config, config), 'url': DATA_URL + '/viewer/' + config + '/latest',
                                  'type': 'category', 'supported_view': 'Rankings / matrix / confidence intervals',
                                  'status': 'unavailable' if error else 'data-only',
                                  'notes': error or f'All {len(benchmarks)} published native categories imported; separate metric per category.'})
    try:
        _, history = parse_rows('agent', read_rows(fetch, 'agent', 'full'))
        for item in history:
            item['notes'] = item['notes'].replace('Official latest snapshot', 'Official dated historical snapshot')
        pack['history'] = history
        history_status = 'data-only'
        history_note = f'{len(history)} actual Agent Arena historical observations imported. Other arenas link to full archives but import current snapshots only.'
    except Exception as exc:
        history_status = 'unavailable'
        history_note = 'Agent Arena history could not be retrieved: ' + str(exc)
    pack['inventory'].append({'name': 'Agent Arena published score history', 'url': DATA_URL + '/viewer/agent/full',
                              'type': 'dataset', 'supported_view': 'Observation-date trends', 'status': history_status,
                              'notes': history_note})
    for name, view, status, note in [
        ('Rank and score with confidence intervals', 'Rankings / table', 'data-only', 'Scores, bounds, rank and battle/session counts imported.'),
        ('Category comparison', 'Matrix / compare', 'data-only', 'Raw, style-controlled and factuality categories remain separate.'),
        ('License and organization comparison', 'Model filters / distribution', 'data-only', 'Official organization and license retained; country not inferred.'),
        ('Leaderboard trends / historic progress', 'Timeline', 'unavailable', 'Full historical splits exist upstream. Only Agent Arena aggregate history is imported; other arenas have current snapshots only.'),
        ('Agent cost Pareto frontier', 'Scatter / Pareto', 'unavailable', 'Public Hugging Face snapshot does not include observed per-task costs. No price-derived costs substituted.'),
        ('Pairwise win-rate and battle-count heatmaps', 'Matrix', 'unavailable', 'Aggregate leaderboard dataset does not include pairwise matchups.'),
        ('Alignment and image-to-WebDev', 'Category filters', 'unavailable', 'No dedicated public subset in the inspected official dataset; do not infer scores from other arenas.'),
    ]:
        pack['inventory'].append({'name': name, 'url': DATA_URL, 'type': 'visualization', 'supported_view': view,
                                  'status': status, 'notes': note})
    return pack
