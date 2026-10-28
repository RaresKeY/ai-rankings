import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from public_data import public_pack, write_pack
from refresh_public import refresh_public
from build_static import build


def pack(provider, observations=None):
    return {'provider':provider,'retrieved_at':'2026-10-28T00:00:00Z',
            'sources':[{'id':provider,'name':provider,'url':'https://example.org','license':'CC BY 4.0'}],
            'benchmarks':[{'id':'test','name':'Test','source_url':'https://example.org','unit':'%'}],
            'observations':observations or [{'benchmark_id':'test','model':'Example model','score':50,'source_url':'https://example.org','evaluator':'Epoch AI','provenance':'internal'}]}


class PublicationTests(unittest.TestCase):
    def test_unapproved_provider_rejected(self):
        for provider in ('aa','swebench','vals','terminalbench','unknown'):
            with self.assertRaises(ValueError):public_pack(pack(provider))
        changed=pack('arena');changed['sources'][0]['license']='CC BY-NC 4.0'
        with self.assertRaises(ValueError):public_pack(changed)

    def test_epoch_external_data_cannot_escape_through_auxiliary_fields(self):
        source=pack('epoch')
        source['observations'].extend([{**source['observations'][0],'provenance':'external-via-epoch','score':99},
                                       {**source['observations'][0],'evaluator':'Other evaluator','score':98}])
        source['eci_inputs']=[{'performance':99}]
        source['visualization_data']=[{'id':'epoch-eci-adjusted-inputs','data':[{'performance':99}]},
                                      {'id':'epoch-edi-fit-parameters','data':[{'difficulty':120}]}]
        approved=public_pack(source)
        self.assertEqual(len(approved['observations']),1)
        self.assertNotIn('eci_inputs',approved)
        self.assertEqual([v['id'] for v in approved['visualization_data']],['epoch-edi-fit-parameters'])
        self.assertEqual(public_pack(approved),approved)

    def test_failed_or_partial_update_preserves_previous(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('arena','epoch'):write_pack(pack(name),root/'data/public')
            before=(root/'data/public/arena.json').read_bytes()
            def broken(fetch):raise ValueError('source unavailable')
            status=refresh_public(root,{'arena':broken,'epoch':lambda f:pack('epoch')},lambda:None)
            self.assertEqual((root/'data/public/arena.json').read_bytes(),before)
            self.assertTrue(status['sources'][0]['retained_previous'])
            changed=pack('epoch');changed['observations'][0]['benchmark_id']='new'
            status=refresh_public(root,{'arena':lambda f:pack('arena'),'epoch':lambda f:changed},lambda:None)
            self.assertEqual(status['sources'][1]['status'],'error')

    def test_static_build_ignores_private_sources_and_uses_relative_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'app').mkdir();(root/'app/index.html').write_text('<div id="app"></div>')
            (root/'icon.svg').write_text('<svg/>');(root/'THIRD_PARTY_NOTICES.md').write_text('Attribution')
            (root/'data/sources').mkdir(parents=True)
            (root/'data/sources/aa.json').write_text(json.dumps(pack('aa')))
            for name in ('arena','epoch'):write_pack(pack(name),root/'data/public')
            result=build(root)
            catalog=json.loads(gzip.decompress((root/'dist/data/catalog.json.gz').read_bytes()))
            self.assertEqual(set(o['provider'] for o in catalog['observations']),{'arena','epoch'})
            self.assertEqual(result['observations'],2)
            self.assertNotIn('/api/',(root/'dist/config.js').read_text())
            self.assertTrue(catalog['publication']['commercial_reuse_only'])
            self.assertEqual(set(p.name for p in (root/'dist/data/snapshots').iterdir()),{'arena.json.gz','epoch.json.gz'})
