import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import refresh


class RefreshTests(unittest.TestCase):
    def run_import(self, new_pack):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root=Path(temporary.name)
        (root/'data/sources').mkdir(parents=True)
        previous={'provider':'aa','benchmarks':[{'id':'a'},{'id':'b'}],
                  'observations':[{'benchmark_id':'a','score':2},{'benchmark_id':'b','score':3}]}
        file=root/'data/sources/aa.json';file.write_text(json.dumps(previous))
        original=file.read_bytes()
        adapter=types.SimpleNamespace(collect=lambda fetch:new_pack)
        with patch.object(refresh,'ROOT',root),patch.object(refresh.importlib,'import_module',return_value=adapter),patch.object(refresh,'write_catalog'):
            result=refresh.refresh(['aa'],callback=lambda message:None)
        return root,file,original,result[0]

    def test_partial_import_retains_previous_complete_snapshot(self):
        root,file,original,result=self.run_import({'provider':'aa','benchmarks':[{'id':'a'}],
            'observations':[{'benchmark_id':'a','score':99}]})
        self.assertEqual(file.read_bytes(),original)
        self.assertEqual(result['status'],'error')
        self.assertTrue(result['retained_previous'])
        self.assertIn('previously populated',result['error'])

    def test_success_replaces_atomically_and_retains_prior_evidence(self):
        root,file,original,result=self.run_import({'provider':'aa','benchmarks':[{'id':'a'},{'id':'b'}],
            'observations':[{'benchmark_id':'a','score':8},{'benchmark_id':'b','score':9}]})
        self.assertEqual(result['status'],'ok')
        self.assertEqual(json.loads(file.read_text())['observations'][0]['score'],8)
        import gzip
        history=list((root/'data/history/aa').glob('*.gz'))
        self.assertEqual(len(history),1)
        self.assertEqual(gzip.decompress(history[0].read_bytes()),original)


if __name__=='__main__':unittest.main()
