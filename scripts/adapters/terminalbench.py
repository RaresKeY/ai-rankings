"""Terminal-Bench official Harbor backend, as used by tbench.ai.

API origin was verified in the public tbench.ai website bundle. It accepts a
read-only GET with the same package/name parameters as the site's POST.
"""
from datetime import datetime, timezone
import json
import math
from urllib.parse import urlencode, quote

API = 'https://ofhuhcpkvzjlejydnvyd.supabase.co/functions/v1/leaderboard-read'
HOME = 'https://www.tbench.ai/'
CONFIGS = [
    ('4.0', 'terminal-bench/terminal-bench', '4-0-0', '4'),
    ('3.0', 'terminal-bench/terminal-bench', '3-0-0', '1'),
    ('2.1', 'terminal-bench/terminal-bench-2-1', 'main', 'latest'),
    ('2.0', 'terminal-bench/terminal-bench-2', '2-0', 'latest'),
    ('0.1', 'terminal-bench-science/terminal-bench-science', 'v0-1-eval', '10'),
]


def data_url(package, name):
    return API + '?' + urlencode({'package': package, 'name': name})


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def label(value, default='Unknown'):
    return value.get('label', default) if isinstance(value, dict) else value or default


def parse_payload(payload, version, package, name, dataset_version):
    board = payload['leaderboard']
    if board['name'] != name:
        raise ValueError('Requested leaderboard and returned leaderboard differ')
    url = data_url(package, name)
    dataset = 'https://hub.harborframework.com/datasets/' + package + '/' + dataset_version
    science = package.startswith('terminal-bench-science/')
    title = ('Terminal-Bench-Science ' if science else 'Terminal-Bench ') + version
    page_url = dataset if science else HOME + '?version=' + version
    prefix = ('terminalbench-science-' if science else 'terminalbench-') + version.replace('.', '-')
    benchmarks, observations = {}, []
    for row in payload['rows']:
        if row.get('status') != 'display':
            continue
        meta, metrics = row['metadata'], row['metrics']
        model = label(meta.get('model_display'))
        agent = label(meta.get('agent_display'))
        agent_version = meta.get('agent_version')
        harness = agent + (' ' + agent_version if agent_version and agent_version != 'unknown' else '')
        effort = meta.get('reasoning_effort') or None
        trials = metrics.get('n_trials') or row.get('n_trials')
        cost = metrics.get('total_cost_usd')
        cost_label = metrics.get('display_total_cost_usd') or metrics.get('display_cost') or ''
        partial_cost = 'partial' in cost_label.lower()
        base = {
            'model': model, 'lab': label(meta.get('model_org')), 'source_url': url,
            'harness': harness, 'effort': effort, 'source_model_id': row['id'],
            'submission_id': row['id'], 'date': (row.get('created_at') or '')[:10] or None,
            'release_date': meta.get('model_release_date') or meta.get('release_date') or meta.get('date'),
            'weights': 'unknown', 'agent': agent, 'agent_version': agent_version,
            'agent_organization': label(meta.get('agent_org')),
            'source_label': model, 'rank': row.get('rank'), 'n_trials': trials,
            'submission_url': dataset + '/leaderboards/' + quote(name) + '/rows/' + row['id'],
            'checked': meta.get('verified'), 'source_created_at': row.get('created_at'),
            'source_updated_at': row.get('updated_at'),
            'notes': 'Official ' + title + ' submitted agent run. '
                     'Date is source leaderboard record creation, not model release or a fresh re-evaluation. '
                     'Original model: ' + model + '; agent: ' + harness + '; effort: ' + (effort or 'unspecified') + '. ',
        }
        if number(metrics.get('accuracy_stderr')):
            base['standard_error'] = metrics['accuracy_stderr']
            base['notes'] += 'Published accuracy standard error retained separately from any 95% interval. '
        for field in ('total_tokens', 'output_tokens', 'cached_input_tokens', 'uncached_input_tokens', 'successes', 'reward_hacks'):
            if number(metrics.get(field)):
                base[field] = metrics[field]
        if number(cost):
            base['total_cost_usd'] = cost
            if number(trials) and trials > 0 and not partial_cost:
                base['cost_usd'] = cost / trials
                base['notes'] += 'Mean cost per trial calculated from published total USD / trial count. '
            elif partial_cost:
                base['notes'] += 'Published total cost is partial: ' + cost_label + '; mean cost omitted. '
        if number(metrics.get('avg_trial_duration_sec')):
            base['latency_seconds'] = metrics['avg_trial_duration_sec']
            base['notes'] += 'Time is mean whole-trial duration, not first-token latency. '
        for key in ('accuracy', 'pass_at_2', 'pass_at_3', 'pass_at_4', 'pass_at_5'):
            if not number(metrics.get(key)):
                continue
            bid = prefix if key == 'accuracy' else prefix + '-' + key.replace('_', '-')
            if bid not in benchmarks:
                suffix = '' if key == 'accuracy' else ' · pass@' + key[-1]
                benchmarks[bid] = {
                    'id': bid, 'name': title + suffix, 'provider': 'terminalbench',
                    'category': 'Science' if science else 'Coding', 'native_category': version + '/' + key,
                    'unit': '%', 'higher_is_better': True, 'min': 0, 'max': 100,
                    'version': version, 'source_url': page_url,
                    'dataset_url': dataset, 'private': False, 'kind': 'benchmark',
                    'description': ('Resolution rate of terminal tasks; model, agent and effort are inseparable evaluation settings.'
                                    if key == 'accuracy' else 'Published pass@' + key[-1] +
                                    ' estimate: chance of solving a task with multiple attempts. Distinct from single-attempt resolution rate.'),
                }
            item = dict(base, benchmark_id=bid, score=metrics[key] * (1 if key == 'accuracy' else 100), metric_key=key)
            if key != 'accuracy':
                item.pop('cost_usd', None)
                item.pop('latency_seconds', None)
                item.pop('standard_error', None)
                item['notes'] += 'Per-trial cost/time omitted from this multi-attempt success metric to avoid implying the cost of k attempts. '
            # Only accuracy has a published interval; never reuse it for pass@k.
            width = metrics.get('accuracy_ci95_half_width')
            if key == 'accuracy' and number(width):
                item['ci_low'] = metrics[key] - width
                item['ci_high'] = metrics[key] + width
            observations.append(item)
    return list(benchmarks.values()), observations


def collect(fetch):
    pack = {'schema_version': 1, 'provider': 'terminalbench', 'retrieved_at': datetime.now(timezone.utc).isoformat(),
            'sources': [], 'benchmarks': [], 'observations': [], 'inventory': []}
    for version, package, name, dataset_version in CONFIGS:
        science = package.startswith('terminal-bench-science/')
        title = ('Terminal-Bench-Science ' if science else 'Terminal-Bench ') + version
        page_url = ('https://hub.harborframework.com/datasets/' + package + '/' + dataset_version) if science else HOME + '?version=' + version
        url = data_url(package, name)
        error = None
        try:
            payload = json.loads(fetch(url))
            benchmarks, observations = parse_payload(payload, version, package, name, dataset_version)
            pack['benchmarks'].extend(benchmarks)
            pack['observations'].extend(observations)
        except Exception as exc:
            error = str(exc)
            observations = []
        pack['sources'].append({
            'id': ('terminalbench-science-' if science else 'terminalbench-') + version.replace('.', '-'), 'name': title,
            'url': page_url, 'data_url': url,
            'methodology_url': HOME + ('news/tb-science-announcement' if science else 'news/terminal-bench-' + version.replace('.', '-')),
            'status': 'unavailable' if error else 'ok', 'license': 'Not stated (leaderboard data)',
            'notes': 'Direct official Harbor leaderboard-read backend used by tbench.ai. All displayed rows; effort settings retained. '
                     + (error or f'{len(observations)} measurements, including available pass@k metrics.'),
        })
        pack['inventory'].append({'name': title, 'url': page_url,
                                  'type': 'category', 'supported_view': 'Rankings / confidence intervals / matrix',
                                  'status': 'unavailable' if error else 'data-only', 'notes': error or 'Full public leaderboard retained; no best-effort filtering.'})
    for name, view, status, notes in [
        ('Ranked resolution rates and 95% intervals', 'Rankings / table', 'data-only', 'Unrounded numeric accuracy and published 95% half-widths imported.'),
        ('Performance versus cost / tokens Pareto', 'Scatter / Pareto', 'data-only', 'Published total tokens, whole-run cost and mean trial time retained; partial costs excluded from per-trial mean.'),
        ('Model × effort × harness waffle matrix', 'Matrix', 'data-only', 'All effort and harness variants retained. Original task-trial waffle requires separate trial records.'),
        ('Pass@k / repeated attempts', 'Benchmark selector / compare', 'data-only', 'Published pass@2 through pass@5 imported as separate metrics; no fabricated confidence intervals.'),
        ('Version 2.0 versus 2.1 / 3.0 versus 4.0', 'Comparison / matrix', 'data-only', 'Different versions remain separate benchmarks, not longitudinal deterioration or improvement.'),
        ('Per-task trial success waffle', 'Task matrix', 'unavailable', 'Leaderboard-read has aggregate metrics; individual trial records have not been downloaded.'),
        ('Terminal-Bench 1.0 and Challenges', 'Dataset catalog', 'unavailable', 'Not exposed by current homepage benchmark configuration. Legacy datasets and long-horizon challenge site linked upstream.'),
        ('Terminal-Bench-Science 0.1', 'Science / rankings', 'data-only', 'Official Harbor science runs imported directly. Published ± numbers are standard errors, not 95% confidence intervals; preserved as standard_error.'),
    ]:
        pack['inventory'].append({'name': name, 'url': HOME + 'benchmarks', 'type': 'visualization',
                                  'supported_view': view, 'status': status, 'notes': notes})
    return pack
