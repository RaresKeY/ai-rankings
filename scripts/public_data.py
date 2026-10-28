"""Public data allowlist. Local research packs are never published wholesale."""
import copy
import json
from pathlib import Path

POLICY_VERSION = 1
PROVIDERS = ('arena', 'epoch')
CC_BY = 'https://creativecommons.org/licenses/by/4.0/'
EXCLUDED = [
    {'provider':'aa','name':'Artificial Analysis','url':'https://artificialanalysis.ai/',
     'reason':'Written permission required for a combined public ranking service and raw-data redistribution.',
     'evidence_url':'https://artificialanalysiscdn.com/legal/ProDataPlatformTerms.pdf'},
    {'provider':'vals','name':'Vals AI','url':'https://www.vals.ai/benchmarks',
     'reason':'No blanket permission for commercial redistribution was established for the imported result tables and chart datasets.'},
    {'provider':'terminalbench','name':'Terminal-Bench','url':'https://www.tbench.ai/',
     'reason':'The imported leaderboard backend does not state a verified commercial redistribution license. Task/framework licenses do not establish rights to these result tables.'},
    {'provider':'swebench','name':'SWE-bench','url':'https://www.swebench.com/',
     'reason':'The source website repository uses CC BY-NC 4.0. Noncommercial-only data is excluded from this edition.',
     'evidence_url':'https://github.com/SWE-bench/swe-bench.github.io/blob/master/LICENSE'},
    {'provider':'epoch-external','name':'Epoch external results','url':'https://epoch.ai/benchmarks/use-this-data',
     'reason':'External observations retain their original licenses. Only Epoch evaluations, published ECI scores and fitted difficulty parameters are included.'},
]


def public_pack(pack):
    provider=pack.get('provider')
    if provider not in PROVIDERS:
        raise ValueError(f'Provider not approved for public distribution: {provider}')
    if not pack.get('sources') or any(not s.get('license','').lower().replace('-',' ').startswith('cc by 4.0') for s in pack['sources']):
        raise ValueError('Expected source license CC BY 4.0; review required')
    out={key:copy.deepcopy(pack.get(key,[])) for key in ('sources','benchmarks','observations','inventory','history','visualization_data')}
    out.update(schema_version=1,provider=provider,retrieved_at=pack.get('retrieved_at'),publication_policy=POLICY_VERSION)
    if provider=='epoch':
        out['observations']=[o for o in out['observations'] if o.get('provenance') in ('internal','composite') and o.get('evaluator')=='Epoch AI']
        # Preprocessed ECI inputs contain external individual measurements.
        out['visualization_data']=[v for v in out['visualization_data'] if v.get('id')=='epoch-edi-fit-parameters']
        out['history']=[]
        out['inventory']=[v for v in out['inventory'] if not any(t in v.get('name','').lower() for t in ('external original','catalog including'))]
        for v in out['inventory']:
            v['notes']='Public edition includes Epoch evaluations and published indices only. Externally aggregated observations and adjusted input records are excluded.'
    ids={o['benchmark_id'] for o in out['observations']}
    out['benchmarks']=[b for b in out['benchmarks'] if b['id'] in ids]
    for b in out['benchmarks']:
        if provider=='arena' and b.get('native_category','').startswith('agent'):b['unit']='pp'
        if 'components' in b:b['components']=[c for c in b['components'] if c.get('benchmark_id') in ids]
    for source in out['sources']:
        source.update(license='CC BY 4.0',license_url=CC_BY)
        if provider=='arena':source['notes']='Arena preference ratings and Agent metrics from the official dataset. Categories and style-control variants remain separate.'
        if provider=='epoch':source['notes']='Epoch AI evaluations and published ECI scores. External source observations are excluded under the public data policy.'
    if not out['observations']:raise ValueError('No approved observations')
    return out


def write_pack(pack,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    out=public_pack(pack);path=directory/(out['provider']+'.json')
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':'),allow_nan=False));temp.replace(path)
    return out


def policy():
    return {'version':POLICY_VERSION,'commercial_reuse_only':True,'license_url':CC_BY,
            'included':list(PROVIDERS),'excluded':EXCLUDED,
            'attribution':[{'name':'Arena','url':'https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset','license_url':CC_BY},
                           {'name':'Epoch AI, Capabilities & benchmarking','url':'https://epoch.ai/benchmarks/use-this-data','license_url':CC_BY}],
            'modifications':'Units normalized and labels grouped by this project. Custom scores are calculated from user-selected tests and weights. No affiliation with the source evaluators.'}


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    for provider in PROVIDERS:
        pack=write_pack(json.loads((root/'data/sources'/(provider+'.json')).read_text()),root/'data/public')
        print(provider,len(pack['observations']))
