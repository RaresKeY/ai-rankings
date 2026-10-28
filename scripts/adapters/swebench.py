"""SWE-bench official website repository; retain every submitted agent run."""
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
import re

URL = 'https://raw.githubusercontent.com/SWE-bench/swe-bench.github.io/master/data/leaderboards.json'
HOME = 'https://www.swebench.com/'
REPO = 'https://github.com/SWE-bench/swe-bench.github.io'
LICENSE_URL = 'https://raw.githubusercontent.com/SWE-bench/swe-bench.github.io/master/LICENSE'
DATASETS = {
    'Test': 'https://huggingface.co/datasets/princeton-nlp/SWE-bench',
    'Lite': 'https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite',
    'Verified': 'https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified',
    'Multimodal': 'https://huggingface.co/datasets/SWE-bench/SWE-bench_Multimodal',
    'Multilingual': 'https://huggingface.co/datasets/SWE-bench/SWE-bench_Multilingual',
}


def slug(value):
    return re.sub(r'[^a-z0-9]+', '-', str(value).lower()).strip('-')


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def release_date(value):
    if value is None:
        return None
    text = str(value)
    try:
        return datetime.strptime(text, '%Y%m%d' if len(text) == 8 else '%Y-%m-%d').date().isoformat()
    except ValueError:
        return None


def collect(fetch):
    data = json.loads(fetch(URL))
    pack = {'schema_version': 1, 'provider': 'swebench', 'retrieved_at': datetime.now(timezone.utc).isoformat(),
            'sources': [{'id': 'swebench', 'name': 'SWE-bench official leaderboards', 'url': HOME,
                         'data_url': URL, 'methodology_url': 'https://www.swebench.com/SWE-bench/',
                         'status': 'ok', 'license': 'CC BY-NC 4.0 (website repository)',
                         'notes': 'Official website leaderboards.json. Every submission retained. Source website repository license: ' + LICENSE_URL + '. '
                                  'Model-open and agent-open fields are distinct. Submissions need not all have been independently rerun by the benchmark team.'}],
            'benchmarks': [], 'observations': [], 'inventory': []}
    repo_benchmarks = set()
    repo_observations = 0
    for board in data['leaderboards']:
        split = board['name']
        bid = 'swebench-' + slug(split)
        pack['benchmarks'].append({
            'id': bid, 'name': 'SWE-bench ' + ('Full' if split == 'Test' else split),
            'provider': 'swebench', 'category': 'Coding', 'native_category': split,
            'unit': '%', 'higher_is_better': True, 'min': 0, 'max': 100,
            'version': split, 'source_url': HOME, 'dataset_url': DATASETS.get(split, REPO),
            'description': 'Percentage of software issues resolved. Different submitted agents, model settings and attempts are distinct runs.',
            'private': False, 'kind': 'benchmark',
        })
        for row in board['results']:
            if not number(row.get('resolved')):
                continue
            folder = row.get('folder') or row.get('name')
            agent = row.get('agent') or 'Agent unspecified'
            version = row.get('mini-swe-agent_version')
            harness = agent + (' ' + version if version else '')
            # A submission ID makes even repeated model/agent configurations distinct.
            harness += ' · ' + str(folder)
            tags = row.get('tags') or []
            item = {
                'benchmark_id': bid, 'model': row.get('model_display') or row['name'],
                'lab': row.get('model_org') or 'Unknown', 'score': row['resolved'],
                'source_url': URL, 'effort': row.get('reasoning_effort'), 'harness': harness,
                'date': row.get('date'), 'source_model_id': folder,
                'release_date': release_date(row.get('model_release_date')),
                'weights': 'open' if row.get('os_model') is True else 'proprietary' if row.get('os_model') is False else 'unknown',
                'source_label': row['name'], 'agent': agent, 'agent_version': version,
                'agent_open_source': row.get('os_system'), 'checked': row.get('checked'),
                'submission_id': folder, 'submission_url': row.get('site'),
                'notes': 'Original submission: ' + row['name'] + '. '
                         + ('Directly checked/performed by SWE-bench team. ' if row.get('checked') else 'Not marked directly checked by SWE-bench team. ')
                         + '; '.join(tags) + ('. Warning: ' + str(row['warning']) if row.get('warning') else ''),
            }
            if number(row.get('instance_cost')):
                item['cost_usd'] = row['instance_cost']
            if number(row.get('cost')):
                item['total_cost_usd'] = row['cost']
            if number(row.get('instance_calls')):
                item['mean_api_calls'] = row['instance_calls']
            pack['observations'].append(item)
            repositories = defaultdict(list)
            for task_id, result in (row.get('per_instance_details') or {}).items():
                if isinstance(result.get('resolved'), bool):
                    repository = task_id.rsplit('-', 1)[0].replace('__', '/')
                    repositories[repository].append(result)
            for repository, results in sorted(repositories.items()):
                repo_id = bid + '-repo-' + slug(repository)
                if repo_id not in repo_benchmarks:
                    repo_benchmarks.add(repo_id)
                    pack['benchmarks'].append({
                        'id': repo_id, 'name': 'SWE-bench ' + split + ' · ' + repository,
                        'provider': 'swebench', 'category': 'Coding', 'native_category': split + '/repository/' + repository,
                        'unit': '%', 'higher_is_better': True, 'min': 0, 'max': 100,
                        'version': split, 'source_url': HOME, 'dataset_url': DATASETS.get(split, REPO),
                        'description': 'Repository slice computed from the official submission per-instance results. '
                                       'Available only for submissions publishing task details; sample count is retained.',
                        'private': False, 'kind': 'benchmark',
                    })
                derived = dict(item, benchmark_id=repo_id,
                               score=100 * sum(r['resolved'] for r in results) / len(results),
                               sample_count=len(results), derived=True)
                derived['notes'] += '. Derived repository slice: ' + repository + '; ' + str(len(results)) + ' published instances.'
                derived.pop('total_cost_usd', None)
                derived.pop('cost_usd', None)
                if all(number(r.get('cost')) for r in results):
                    derived['cost_usd'] = sum(r['cost'] for r in results) / len(results)
                pack['observations'].append(derived)
                repo_observations += 1
        pack['inventory'].append({'name': 'SWE-bench ' + split, 'url': HOME, 'type': 'category',
                                  'supported_view': 'Rankings / matrix', 'status': 'data-only',
                                  'notes': f'{len(board["results"])} source submissions retained; no best-agent collapse.'})
    for name, view, status, note in [
        ('Resolved-rate ranking and comparison bars', 'Rankings / comparison', 'data-only', 'All five official leaderboard splits imported.'),
        ('Bash Only / mini-SWE-agent', 'Harness filters', 'data-only', 'Filter agent field; exact mini-SWE-agent version and submission retained.'),
        ('Cost versus % resolved', 'Scatter / Pareto', 'data-only', 'Published instance_cost imported as mean USD per issue; whole-run cost preserved separately.'),
        ('Open-weight / checked / agent / model organization', 'Filters / table', 'data-only', 'Official model license, checked marker and agent organization semantics preserved.'),
        ('Per-instance result comparison', 'Task matrix', 'unavailable', '53 official submissions include per_instance_details in the raw JSON; current pack retains aggregate results only. Raw file is linked.'),
        ('Repository breakdowns', 'Category comparison', 'data-only', f'{repo_observations} repository slices calculated from published per-instance results; each retains its submission and sample count.'),
        ('Issue-year breakdowns', 'Category comparison', 'unavailable', 'Requires task-level joining with original issue dates; not inferred from submission dates or issue IDs.'),
        ('Submission history', 'Timeline', 'data-only', 'Submission dates identify separate experiments, not controlled longitudinal model re-evaluations.'),
    ]:
        pack['inventory'].append({'name': name, 'url': HOME, 'type': 'visualization', 'supported_view': view,
                                  'status': status, 'notes': note})
    return pack
