"""Regression checks for source attribution and incompatible score semantics."""
import json
import unittest
from scripts.adapters import arena, swebench, terminalbench


class ArenaSourceTests(unittest.TestCase):
    def test_ips_is_percentage_point_effect_and_keeps_negative_values(self):
        rows = [{'model_name': 'Model (Max)', 'organization': 'Org', 'license': 'Proprietary',
                 'score': -0.12, 'score_ci_lower': -0.2, 'score_ci_upper': -0.04,
                 'category': 'overall', 'leaderboard_publish_date': '2026-10-01'}]
        benchmarks, observations = arena.parse_rows('agent', rows)
        self.assertEqual(observations[0]['score'], -12)
        self.assertEqual(observations[0]['ci_low'], -20)
        self.assertIsNone(benchmarks[0]['min'])
        self.assertIn('not task accuracy', benchmarks[0]['description'])
        self.assertEqual(observations[0]['effort'], 'max')
        self.assertEqual(benchmarks[0]['unit'], 'pp')

    def test_style_control_and_raw_categories_are_separate(self):
        rows = [{'model_name': 'Model', 'rating': 1440, 'rating_lower': 1430,
                 'rating_upper': 1450, 'category': 'coding'}]
        a, ao = arena.parse_rows('text', rows)
        b, bo = arena.parse_rows('text_style_control', rows)
        self.assertNotEqual(a[0]['id'], b[0]['id'])
        self.assertEqual(ao[0]['score'], 1440)
        self.assertEqual(a[0]['unit'], 'score')
        self.assertEqual(a[0]['category'], 'Coding')

    def test_pagination_requires_all_rows(self):
        calls = []
        def fetch(url):
            calls.append(url)
            return json.dumps({'rows': [{'row': {'model_name': 'a'}}] if len(calls) == 1 else [],
                               'num_rows_total': 2, 'partial': False}).encode()
        with self.assertRaisesRegex(ValueError, 'before end'):
            arena.read_rows(fetch, 'text')
        self.assertIn('offset=1', calls[1])


class TerminalBenchSourceTests(unittest.TestCase):
    def payload(self):
        return {'leaderboard': {'name': '4-0-0'}, 'rows': [{
            'id': 'run-1', 'status': 'display', 'created_at': '2026-10-20T12:00:00Z',
            'metadata': {'model_display': {'label': 'Model'}, 'agent_display': {'label': 'Harness'},
                         'date': '2026-09-01', 'reasoning_effort': 'high'},
            'metrics': {'accuracy': 50, 'accuracy_ci95_half_width': 3, 'pass_at_2': 0.72,
                        'total_cost_usd': 100, 'n_trials': 10, 'display_cost': '$100'},
        }]}

    def test_pass_at_k_has_own_scale_and_no_borrowed_interval(self):
        _, rows = terminalbench.parse_payload(self.payload(), '4.0', 'terminal-bench/terminal-bench', '4-0-0', '4')
        self.assertEqual(rows[0]['score'], 50)
        self.assertEqual(rows[0]['ci_low'], 47)
        self.assertEqual(rows[1]['score'], 72)
        self.assertNotIn('ci_low', rows[1])
        self.assertEqual(rows[0]['cost_usd'], 10)
        self.assertNotIn('cost_usd', rows[1])
        self.assertEqual(rows[0]['date'], '2026-10-20')
        self.assertEqual(rows[0]['release_date'], '2026-09-01')

    def test_partial_cost_never_becomes_mean_cost(self):
        p = self.payload()
        p['rows'][0]['metrics']['display_cost'] = '$100 (partial: 9/10)'
        _, rows = terminalbench.parse_payload(p, '4.0', 'terminal-bench/terminal-bench', '4-0-0', '4')
        self.assertNotIn('cost_usd', rows[0])
        self.assertEqual(rows[0]['total_cost_usd'], 100)

    def test_science_standard_error_is_not_mislabeled_as_95_percent(self):
        p = self.payload()
        p['leaderboard']['name'] = 'v0-1-eval'
        p['rows'][0]['metrics'].pop('accuracy_ci95_half_width')
        p['rows'][0]['metrics']['accuracy_stderr'] = 3.2
        p['rows'][0]['metadata']['model_release_date'] = '2026-08-01'
        b, rows = terminalbench.parse_payload(p, '0.1', 'terminal-bench-science/terminal-bench-science', 'v0-1-eval', '10')
        self.assertEqual(b[0]['category'], 'Science')
        self.assertNotIn('ci_low', rows[0])
        self.assertEqual(rows[0]['standard_error'], 3.2)
        self.assertEqual(rows[0]['release_date'], '2026-08-01')

    def test_reject_wrong_version_response(self):
        with self.assertRaisesRegex(ValueError, 'differ'):
            terminalbench.parse_payload(self.payload(), '3.0', 'terminal-bench/terminal-bench', '3-0-0', '1')


class SWEBenchSourceTests(unittest.TestCase):
    def test_run_identity_cost_and_repository_derivation(self):
        rows = [{'name': 'Agent + M', 'model_display': 'M', 'agent': 'Agent', 'resolved': 50,
                 'folder': folder, 'date': '2026-10-01', 'cost': 30, 'instance_cost': 15,
                 'per_instance_details': {'org__repo-1': {'resolved': True, 'cost': 10},
                                          'org__repo-2': {'resolved': False, 'cost': 20}},
                 'os_model': False, 'os_system': True} for folder in ['run-a', 'run-b']]
        pack = swebench.collect(lambda _: json.dumps({'leaderboards': [{'name': 'Verified', 'results': rows}]}).encode())
        aggregate = [r for r in pack['observations'] if r['benchmark_id'] == 'swebench-verified']
        derived = [r for r in pack['observations'] if r.get('derived')]
        self.assertNotEqual(aggregate[0]['harness'], aggregate[1]['harness'])
        self.assertEqual(aggregate[0]['cost_usd'], 15)
        self.assertEqual(aggregate[0]['weights'], 'proprietary')
        self.assertEqual(derived[0]['score'], 50)
        self.assertEqual(derived[0]['sample_count'], 2)
        self.assertNotIn('total_cost_usd', derived[0])


if __name__ == '__main__':
    unittest.main()
