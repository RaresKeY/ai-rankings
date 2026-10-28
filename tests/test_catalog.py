import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from catalog import compile_catalog, identity
from refresh import validate_url


class CatalogTests(unittest.TestCase):
    def test_aliases_keep_versions_distinct(self):
        self.assertEqual(identity('OpenAI / GPT-6.1 (high)')[0], identity('GPT 6.1')[0])
        self.assertNotEqual(identity('GPT-6.1 Terra')[0], identity('GPT-6.1 Astra')[0])
        self.assertNotEqual(identity('Model v1')[0], identity('Model v2')[0])

    def test_compilation_preserves_raw_evidence_and_reports_invalid_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'data/sources').mkdir(parents=True)
            raw = {'model':'GPT-6.1 (high)', 'lab':'openai', 'score':71, 'benchmark_id':'b',
                   'source_url':'https://example.org/original', 'country':'us', 'effort':'high',
                   'stderr':2, 'provenance':'external-via-epoch'}
            pack = {'provider':'epoch', 'retrieved_at':'2026-10-28', 'benchmarks':[{'id':'b'}],
                    'observations':[raw, dict(raw), {**raw,'benchmark_id':'missing'}]}
            (root/'data/sources/epoch.json').write_text(json.dumps(pack))
            result=compile_catalog(root)
            self.assertEqual(len(result['observations']),1)
            self.assertEqual(len(result['problems']),1)
            obs=result['observations'][0]
            for key in ('model','lab','score','source_url','effort','stderr','provenance'):
                self.assertEqual(obs[key],raw[key])
            self.assertEqual(obs['source_country'],'us')
            self.assertEqual(result['models'][0]['lab'],'OpenAI')
            self.assertEqual(result['models'][0]['country'],'United States')

    def test_refresh_only_curated_https_origins(self):
        validate_url('https://epoch.ai/data/benchmark_data.zip')
        validate_url('https://ofhuhcpkvzjlejydnvyd.supabase.co/functions/v1/leaderboard-read')
        for url in ('http://epoch.ai/data', 'https://example.org/data', 'https://epoch.ai:8443/data',
                    'https://user@epoch.ai/data', 'https://ofhuhcpkvzjlejydnvyd.supabase.co/rest/v1/private'):
            with self.assertRaises(ValueError): validate_url(url)


if __name__=='__main__': unittest.main()
