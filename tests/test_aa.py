"""Regression checks for source decoding and metric integrity, stdlib only."""
import json
import unittest
from pathlib import Path
from scripts.adapters.aa import Flight, Builder, ingest_media, model_metadata, task_fields


def page(records):
    stream=''.join(key+':'+json.dumps(value)+'\n' for key,value in records.items())
    return '<script>self.__next_f.push('+json.dumps([1,stream])+')</script>'


class ArtificialAnalysisTests(unittest.TestCase):
    def test_flight_model_reference_and_public_map(self):
        data=Flight(page({'a':['$','main',None,{'currentModel':{'name':'Variant (High)','score':0}}],
                          'b':[[None,[{'values':{'name':'Image','elo':1050}}]]]}))
        self.assertEqual(data.resolve('$a:props:currentModel'),{'name':'Variant (High)','score':0})
        self.assertEqual(data.resolve('$Qb')[0][1][0]['values']['elo'],1050)
        self.assertIsNone(data.resolve('$undefined'))

    def test_endpoint_metadata_cannot_impersonate_task_performance(self):
        meta=model_metadata({'name':'A','slug':'a','timescaleData':{'medianOutputSpeed':80,'medianTimeToFirstChunk':0.3},'intelligenceIndexCostPerTask':{'cost':{'total':2.5}}})
        self.assertEqual(meta['endpoint_latency_seconds'],0.3)
        self.assertEqual(meta['endpoint_speed_tps'],80)
        self.assertNotIn('latency_seconds',meta)
        self.assertNotIn('speed_tps',meta)
        self.assertNotIn('cost_usd',meta)
        scoped=task_fields(1.2,40,'Exact evaluation task')
        self.assertEqual(scoped['latency_seconds'],40)
        self.assertEqual(scoped['cost_usd'],1.2)
        self.assertEqual(task_fields(None,None,'No values'),{})

    def test_broken_source_fails_instead_of_making_scores(self):
        with self.assertRaises(ValueError):Flight(b'<html>Login or unavailable</html>')

    def test_media_category_ci_and_units_preserved(self):
        data=Flight(page({'a':{'title':'Image test v2','initialData':'$Qb','tags':[{'slug':'physics','displayName':'Physics'}]},
                         'b':[['physics',[{'values':{'id':'i','name':'A','elo':1012.5,'ciLower':998,'ciUpper':1027,'appearances':400,'pricePer1kImages':35,'creator':{'name':'Lab'},'isCurrent':True}}]]]}))
        b=Builder();self.assertEqual(ingest_media(b,data,'https://artificialanalysis.ai/image/leaderboard/text-to-image'),1)
        row=b.observations[0]
        self.assertEqual(row['ci_low'],998)
        self.assertEqual(row['sample_count'],400)
        self.assertEqual(row['price_per_1000_images'],35)
        self.assertNotIn('cost_usd',row)
        self.assertEqual(next(iter(b.benchmarks.values()))['media_category'],'Physics')

    def test_published_pack_scale_uniqueness_and_missing_scores(self):
        p=Path(__file__).parents[1]/'data/sources/aa.json'
        if not p.exists():self.skipTest('No bundled snapshot')
        pack=json.loads(p.read_text());benchmarks={x['id']:x for x in pack['benchmarks']}
        keys=set()
        for o in pack['observations']:
            key=(o['benchmark_id'],o.get('source_model_id'),o['model'],o.get('harness'))
            self.assertNotIn(key,keys);keys.add(key)
            b=benchmarks[o['benchmark_id']]
            self.assertIsInstance(o['score'],(int,float))
            if b['min'] is not None:self.assertGreaterEqual(o['score'],b['min'])
            if b['max'] is not None:self.assertLessEqual(o['score'],b['max'])
            if o.get('ci_low') is not None and o.get('ci_high') is not None:
                self.assertLessEqual(o['ci_low'],o['ci_high'])  # Source intervals can be rounded.
        self.assertGreater(len(keys),10000)
        index=benchmarks['aa-intelligenceindex']
        self.assertAlmostEqual(sum(c['weight'] for c in index['components']),1)
        self.assertIsNone(index['private'])
        self.assertEqual(index['private_share'],0.6)
        for o in pack['observations']:
            self.assertNotIn('speed_tps',o)  # Global endpoint speed has its own field.
            if 'latency_seconds' in o:
                self.assertEqual(o['latency_seconds'],o['task_time_seconds'])
                self.assertIn('latency_basis',o)
            if 'cost_usd' in o:self.assertIn('cost_basis',o)
        legacy=next(o for o in pack['observations'] if o['benchmark_id']=='aa-tau2' and o['model']=='GLM-4.5V (Non-reasoning)')
        self.assertIn('endpoint_latency_seconds',legacy)
        self.assertNotIn('latency_seconds',legacy)
        self.assertNotIn('cost_usd',legacy)
        self.assertTrue(all(c['benchmark_id'] in benchmarks for c in index['components']))
        models={o['model'] for o in pack['observations'] if o['benchmark_id']=='aa-intelligenceindex'}
        self.assertNotIn('GLM-4.5V (Non-reasoning)',models)  # Upstream index is null.

if __name__=='__main__':unittest.main()
