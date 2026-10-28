"""Artificial Analysis public-page importer. No API keys or hidden endpoints.

The model detail page carries the complete model comparison dataset in its public
React Flight stream. Read JSON values, including Flight references, without
executing upstream JavaScript. Media leaderboards carry public Map entries.
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

ROOT = 'https://artificialanalysis.ai'
MODEL_URL = ROOT + '/models/gemini-4-argon'
METHOD_URL = ROOT + '/methodology/intelligence-benchmarking'
EVAL_URL = ROOT + '/evaluations'
FETCH_URLS = [ROOT + '/', MODEL_URL, EVAL_URL, METHOD_URL,
             ROOT + '/image/leaderboard/text-to-image', ROOT + '/image/leaderboard/editing',
             ROOT + '/video/leaderboard/text-to-video', ROOT + '/video/leaderboard/image-to-video',
             ROOT + '/video/leaderboard/video-editing', ROOT + '/text-to-speech/models']


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


class Flight:
    """Decode JSON-only Flight records and references; do not evaluate scripts."""
    def __init__(self, body):
        text = body.decode('utf-8') if isinstance(body, bytes) else body
        chunks = []
        for match in re.finditer(r'self\.__next_f\.push\((.*?)\)</script>', text, re.S):
            try:
                chunk = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            if len(chunk) > 1 and isinstance(chunk[1], str):
                chunks.append(chunk[1])
        self.records = {}
        for line in ''.join(chunks).splitlines():
            try:
                key, raw = line.split(':', 1)
                self.records[key] = json.loads(raw)
            except (ValueError, json.JSONDecodeError):
                continue
        if not self.records:
            raise ValueError('Artificial Analysis public page contains no readable Flight JSON')

    def resolve(self, value, seen=()):
        if isinstance(value, str):
            if value == '$undefined':
                return None
            match = re.fullmatch(r'\$(?:Q)?([0-9a-f]+)(?::(.*))?', value)
            if match and value not in seen:
                target = self.records.get(match[1])
                try:
                    for part in (match[2] or '').split(':') if match[2] else []:
                        if isinstance(target, list):
                            target = target[3] if part == 'props' else target[int(part)]
                        else:
                            target = target[part]
                    return self.resolve(target, seen + (value,))
                except (KeyError, IndexError, TypeError, ValueError):
                    raise ValueError(f'Unresolved public Flight reference: {value}')
            return value
        if isinstance(value, list):
            return [self.resolve(v, seen) for v in value]
        if isinstance(value, dict):
            return {k: self.resolve(v, seen) for k, v in value.items()}
        return value

    def objects(self):
        return walk(list(self.records.values()))


def slug(value):
    return re.sub(r'[^a-z0-9]+', '-', str(value).lower()).strip('-')


# field, evaluation slug, display name, category, version, upstream dataset
EVALUATIONS = [
 ('intelligenceIndex','artificial-analysis-intelligence-index','Artificial Analysis Intelligence Index','General','5.0',None),
 ('omniscience','omniscience','AA-Omniscience Index','General','1.1','https://huggingface.co/datasets/ArtificialAnalysis/AA-Omniscience-Public-v1.1'),
 ('omniscienceAccuracy','omniscience','AA-Omniscience Accuracy','General','1.1','https://huggingface.co/datasets/ArtificialAnalysis/AA-Omniscience-Public-v1.1'),
 ('omniscienceHallucinationRate','omniscience','AA-Omniscience Non-Hallucination Rate','General','1.1','https://huggingface.co/datasets/ArtificialAnalysis/AA-Omniscience-Public-v1.1'),
 ('mlcrOverall','mlcr-aa','MLCR-AA','Knowledge work',None,'https://huggingface.co/datasets/Wisedocs/mlcr-dataset'),
 ('gdpPdfAllPass','gdp-pdf','GDP.pdf All-Pass','Knowledge work',None,'https://huggingface.co/datasets/surgeai/GDP.pdf'),
 ('gdpval','gdpval-aa','GDPval-AA','Knowledge work','2.1','https://huggingface.co/datasets/openai/gdpval'),
 ('itBenchSre','itbench-aa','ITBench-AA','Coding',None,'https://huggingface.co/datasets/ArtificialAnalysis/ITBench-AA'),
 ('tau2','tau2-bench','τ²-Bench Telecom','Knowledge work',None,'https://github.com/sierra-research/tau2-bench'),
 ('tauBanking','tau3-banking','τ³-Banking','Knowledge work',None,'https://github.com/sierra-research/tau2-bench'),
 ('terminalbenchHard','terminalbench-hard','Terminal-Bench Hard','Coding',None,'https://www.tbench.ai/registry'),
 ('terminalBench21','terminalbench-2-1','Terminal-Bench','Coding','2.1','https://www.tbench.ai/leaderboard/terminal-bench/2.1'),
 ('terminalBench40','terminalbench-4-0','Terminal-Bench','Coding','4.0','https://github.com/harbor-framework/terminal-bench'),
 ('frontierCode','frontiercode','FrontierCode','Coding','1.1','https://cognition.com/blog/frontier-code-1.1'),
 ('frontierCode20','frontiercode-2-0','FrontierCode','Coding','2.0','https://cognition.com/blog/frontier-code-2.0'),
 ('terminalBenchScience','terminal-bench-science','Terminal-Bench-Science','Science','0.1','https://github.com/harbor-framework/terminal-bench-science'),
 ('healthbench','healthbench','HealthBench','Knowledge work',None,'https://github.com/openai/simple-evals'),
 ('healthbenchProfessional','healthbench','HealthBench Professional','Knowledge work',None,'https://github.com/openai/simple-evals'),
 ('hleDiamond','hle-diamond','HLE-Diamond','General',None,'https://huggingface.co/datasets/cais/hle-diamond'),
 ('critptAgenticHard','critpt-v2','CritPt v2 (Hard Subset)','Science','2','https://critpt.com/'),
 ('scicode','scicode','SciCode','Coding',None,'https://scicode-bench.github.io/'),
 ('lcr','artificial-analysis-long-context-reasoning','AA-LCR','General','1.1','https://huggingface.co/datasets/ArtificialAnalysis/AA-LCR'),
 ('ifbench','ifbench','IFBench','General',None,'https://huggingface.co/datasets/allenai/IFBench_test'),
 ('hle','humanitys-last-exam',"Humanity’s Last Exam",'General',None,'https://huggingface.co/datasets/cais/hle'),
 ('gpqa','gpqa-diamond','GPQA Diamond','Science',None,'https://github.com/openai/simple-evals/blob/main/gpqa_eval.py'),
 ('critpt','critpt','CritPt','Science','1','https://huggingface.co/datasets/CritPt-Benchmark/CritPt'),
 ('apexAgents','apex-agents-aa','APEX-Agents-AA','Knowledge work',None,'https://huggingface.co/datasets/mercor/apex-agents'),
 ('mmmuPro','mmmu-pro','MMMU-Pro','Multimodal',None,'https://huggingface.co/datasets/MMMU/MMMU_Pro'),
 ('livecodebench','livecodebench','LiveCodeBench','Coding',None,'https://huggingface.co/datasets/livecodebench/code_generation_lite'),
 ('aime25','aime-2025','AIME 2025','Math','2025',None),
 ('analystAgent','aa-analyst-agent','AA-AnalystAgent','Knowledge work',None,None),
 ('automationBenchPartialScore','automationbench-aa','AutomationBench-AA','Knowledge work',None,'https://github.com/zapier/AutomationBench'),
 ('enterpriseOpsGym','enterprise-ops-gym-aa','EnterpriseOps-Gym-AA','Knowledge work',None,'https://huggingface.co/datasets/ServiceNow-AI/EnterpriseOps-Gym'),
 ('harveyLab','harvey-lab-aa','Harvey LAB-AA','Knowledge work','1.1','https://github.com/harveyai/harvey-labs'),
 ('aa3dElo','aa-3d','AA-3D','Multimodal',None,None),
 ('code2videoElo','code2video-aa','Code2Video-AA','Multimodal',None,'https://github.com/heygen-com/hyperframes'),
]
ELO_FIELDS = {'gdpval', 'aa3dElo', 'code2videoElo'}
SCORE_FIELDS = {'intelligenceIndex', 'omniscience'}


class Builder:
    def __init__(self):
        self.benchmarks = {}
        self.observations = []
        self.inventory = []

    def benchmark(self, key, name, category='Other', unit='%', url=MODEL_URL,
                  version=None, dataset=None, description='', private=None,
                  kind='benchmark', higher=True, native=None, bounds=None, **extra):
        key = 'aa-' + slug(key)
        self.benchmarks[key] = dict(id=key, name=name, provider='aa', category=category,
            unit=unit, higher_is_better=higher,
            min=(0 if unit == '%' else None) if bounds is None else bounds[0],
            max=(100 if unit == '%' else None) if bounds is None else bounds[1],
            version=version, source_url=url, dataset_url=dataset,
            description=description, private=private, kind=kind,
            native_category=native or category, **extra)
        return key

    def add(self, key, model, score, url=None, scale=1, **extra):
        if not number(score):
            return
        self.observations.append(dict(benchmark_id=key, **model, score=score * scale,
            source_url=url or self.benchmarks[key]['source_url'], **extra))

    def item(self, name, url, view, notes='', status='data-only', type='visualization'):
        self.inventory.append(dict(name=name, url=url, type=type, supported_view=view,
                                   status=status, notes=notes))


def model_metadata(model):
    creator = model.get('creator') or {}
    effort = model.get('effort')
    times = model.get('timescaleData') or {}
    data = dict(model=model['name'], lab=creator.get('name'),
        source_model_id=model.get('id'), date=None,
        weights='open' if model.get('isOpenWeights') else 'proprietary',
        effort=effort.get('label') if isinstance(effort, dict) else model.get('suffix'),
        context_tokens=model.get('contextWindowTokens'), release_date=model.get('releaseDate'),
        input_price=model.get('price1mInputTokens'), output_price=model.get('price1mOutputTokens'),
        endpoint_speed_tps=times.get('medianOutputSpeed'),
        endpoint_latency_seconds=times.get('medianTimeToFirstChunk'),
        endpoint_performance_basis='Representative endpoint output speed and time to first chunk; not benchmark task duration.' if times else None,
        endpoint_performance_source=model.get('performanceDataSource'),
        country=creator.get('country'), deprecated=model.get('deprecated'),
        modalities=[x.lower() for x in ('Text','Image','Speech','Video') if model.get('inputModality'+x)],
        release_group=(model.get('release') or {}).get('name'),
        source_model_url=ROOT+'/models/'+model['slug'])
    return {k:v for k,v in data.items() if v is not None}


def task_fields(cost, seconds, basis):
    """Attach performance only when published for this exact evaluation scope."""
    result = {}
    if number(cost):
        result.update(cost_usd=cost, cost_basis=basis)
    if number(seconds):
        result.update(latency_seconds=seconds, task_time_seconds=seconds, latency_basis=basis)
    return result


def ingest_language(b, flight, evaluation_metadata):
    blocks = [d for d in flight.objects() if isinstance(d.get('models'), list)
              and d['models'] and isinstance(d['models'][0],dict)
              and 'contextWindowTokens' in d['models'][0]]
    if not blocks:
        raise ValueError('AA model detail page no longer exposes the full model comparison dataset')
    models = flight.resolve(max(blocks, key=lambda d: len(d['models']))['models'])
    if len(models) < 100:
        raise ValueError('AA model table unexpectedly contains fewer than 100 models')
    evmap = {x['slug']: x for x in evaluation_metadata}
    keys = {}
    for field, evslug, name, category, version, dataset in EVALUATIONS:
        ev = evmap.get(evslug, {})
        unit = 'Elo' if field in ELO_FIELDS else 'score' if field in SCORE_FIELDS else '%'
        keys[field] = b.benchmark(field, name + (f' {version}' if version and version not in name else ''),
            category, unit, EVAL_URL+'/'+evslug, version, dataset,
            description=f'Independent Artificial Analysis evaluation; original measurement field: {field}.',
            private=None if field=='intelligenceIndex' else 'private-dataset' in ev.get('attributes',[]) if ev else None,
            kind='composite' if field=='intelligenceIndex' else 'benchmark',
            taxonomy={k:ev.get(k,[]) for k in ('skills','knowledge','attributes')},
            bounds=(-100,100) if field=='omniscience' else (0,100) if field=='intelligenceIndex' else None)
    brief = b.benchmark('briefcase','AA-Briefcase 1.1','Knowledge work','Elo',EVAL_URL+'/aa-briefcase','1.1',
        'https://huggingface.co/datasets/ArtificialAnalysis/AA-Briefcase-Lite',
        description='Combined task success, analytical quality and presentation Elo; private full task set, public Lite examples.',private=True)
    keys['briefcase'] = brief
    for sub, name, unit in [('rubricPassRate','Rubric pass rate','%'),('analyticalQuality','Analytical quality','Elo'),('presentation','Presentation','Elo')]:
        keys['briefcase-'+sub] = b.benchmark('briefcase-'+sub,'AA-Briefcase · '+name,'Knowledge work',unit,EVAL_URL+'/aa-briefcase','1.1',private=True)
    for field, label in [('financeAndAccounting','Finance & Accounting'),('strategyAndOps','Strategy & Ops'),('legal','Legal'),('healthcareAndMedical','Healthcare & Medical'),('engineering','Engineering'),('economics','Economics')]:
        keys['capability-'+field] = b.benchmark('capability-'+field,'AA '+label+' Index','Knowledge work','score',ROOT+'/indexes',kind='composite',native=label,bounds=(0,100))
    metricdefs = [
      ('intelligenceIndexCostPerTask','Cost per Intelligence Index task','USD','Cost',False),
      ('intelligenceIndexTimePerTask','Time per Intelligence Index task','seconds','Performance',False),
      ('output-tokens-per-task','Output tokens per Intelligence Index task','tokens','Cost',False),
      ('price1mInputTokens','Input price / million tokens','USD','Cost',False),
      ('price1mOutputTokens','Output price / million tokens','USD','Cost',False),
      ('cacheHitPrice','Cache hit price / million tokens','USD','Cost',False),
      ('medianOutputSpeed','Output speed','tokens/s','Performance',True),
      ('medianTimeToFirstChunk','Time to first chunk','seconds','Performance',False),
      ('timeToFirstAnswerToken','Time to first answer token','seconds','Performance',False),
      ('endToEndResponseTime','End-to-end response time','seconds','Performance',False),
      ('contextWindowTokens','Context window','tokens','Context',True),
      ('parameters','Total parameters','billions','Model size',True),
      ('inferenceParametersActiveBillions','Active inference parameters','billions','Model size',True),
      ('opennessIndex','Openness Index','score','Openness',True),
    ]
    for field,name,unit,native,higher in metricdefs:
        keys[field] = b.benchmark(field,name,unit=unit,native=native,kind='metric',higher=higher)
    for model in models:
        meta = model_metadata(model)
        per_eval = {v['slug']:v for v in model.get('intelligenceIndexEvaluations',[]) if isinstance(v,dict)}
        for field,evslug,*_ in EVALUATIONS:
            value=model.get(field)
            if not number(value): continue
            if field=='omniscienceHallucinationRate':value=1-value
            extra={}
            task_slug='critpt-v2-hard' if field=='critptAgenticHard' else evslug
            performance=per_eval.get(task_slug,{})
            extra.update(task_fields(performance.get('costPerTask'),performance.get('timePerTask'),
                'AA-reported per-task result for '+task_slug))
            if number(performance.get('outputTokensPerTask')):extra['output_tokens_per_task']=performance['outputTokensPerTask']
            interval=model.get(field+'Interval')
            if interval:extra.update(ci_low=interval['lower'],ci_high=interval['upper'])
            if field=='intelligenceIndex':
                costs=model.get('intelligenceIndexCostPerTask') or {}
                costs=costs.get('cost',costs)
                extra.update(task_fields(costs.get('total'),model.get('intelligenceIndexTimePerTask'),
                    'Weighted average per Intelligence Index v5.0 task'))
                extra['cost_components']=costs
                extra['estimated']=model.get('intelligenceIndexIsEstimated',False)
            b.add(keys[field],meta,value,scale=1 if field in ELO_FIELDS|SCORE_FIELDS else 100,**extra)
        breakdown=model.get('briefcaseBreakdown') or {}
        for sub in ['overall','rubricPassRate','analyticalQuality','presentation']:
            raw=breakdown.get(sub)
            if isinstance(raw,dict):
                performance=per_eval.get('aa-briefcase',{}) if sub=='overall' else {}
                extra=task_fields(performance.get('costPerTask'),performance.get('timePerTask'),
                    'AA-reported per-task result for aa-briefcase')
                b.add(brief if sub=='overall' else keys['briefcase-'+sub],meta,raw.get('elo'),
                      ci_low=raw.get('lower95ci'),ci_high=raw.get('upper95ci'),**extra)
            elif sub=='rubricPassRate':b.add(keys['briefcase-'+sub],meta,raw,scale=100)
        for field,value in model.get('capabilities',{}).items():
            key=keys.get('capability-'+field)
            if key:b.add(key,meta,value)
        for field,*_ in metricdefs:
            value=model.get(field)
            extra={}
            if field=='intelligenceIndexCostPerTask':
                raw=value or {};raw=raw.get('cost',raw);value=raw.get('total');extra['components']=raw
            elif field=='output-tokens-per-task':
                raw=model.get('intelligenceIndexOutputTokensPerTask') or {};value=raw.get('output');extra['components']=raw
            elif field in ('medianOutputSpeed','medianTimeToFirstChunk'):
                value=(model.get('timescaleData') or {}).get(field)
                extra['distribution']=model.get('outputSpeedVariance' if field=='medianOutputSpeed' else 'timeToFirstChunkVariance')
                extra['performance_by_prompt_type']=model.get('performanceByPromptType')
                extra['performance_source']=model.get('performanceDataSource')
            elif field in ('timeToFirstAnswerToken','endToEndResponseTime'):
                raw=model.get(field) or {};value=raw.get('total');extra['components']=raw
            elif field=='opennessIndex':
                raw=model.get('openness') or {};value=raw.get(field);extra['components']=raw
            b.add(keys[field],meta,value,**extra)
        for field,value in (model.get('personalityBench') or {}).get('indexScores',{}).items():
            key=b.benchmark('personality-'+field,'AA-PersonalityBench · '+field.title(),unit='percentile',url=EVAL_URL+'/aa-personalitybench',kind='trait',native='Personality',higher=field!='slop',bounds=(1,100),description='Communication-style percentile; not a capability or correctness score.')
            ci=(model.get('personalityBench') or {}).get('indexIntervals',{}).get(field,{})
            b.add(key,meta,value,ci_low=ci.get('lower'),ci_high=ci.get('upper'))
        for field,value in (model.get('personalityBench') or {}).get('scores',{}).items():
            key=b.benchmark('personality-trait-'+field,'AA-PersonalityBench · '+re.sub(r'([A-Z])',r' \1',field).capitalize(),unit='score',url=EVAL_URL+'/aa-personalitybench',kind='trait',native='Personality',higher=field not in ('slop','sycophantic'),description='Raw judged communication trait; higher means more of the named trait, not universally better.')
            b.add(key,meta,value)
        for field,value in (model.get('personalityBenchMeans') or {}).items():
            key=b.benchmark('personality-measured-'+field,'AA-PersonalityBench · '+re.sub(r'([A-Z])',r' \1',field).capitalize(),unit='count',url=EVAL_URL+'/aa-personalitybench',kind='trait',native='Personality',description='Mean measured communication characteristic. More is not universally better; see source units.')
            b.add(key,meta,value)
    components=[('briefcase',.15),('automationBenchPartialScore',.05),('gdpPdfAllPass',.05),('frontierCode20',.15),('terminalBench40',.1),('terminalBenchScience',.15),('critptAgenticHard',.1),('omniscienceAccuracy',.1),('omniscienceHallucinationRate',.05),('hleDiamond',.1)]
    b.benchmarks[keys['intelligenceIndex']]['private_share']=0.6
    b.benchmarks[keys['intelligenceIndex']]['private_share_basis']='Share of v5.0 index weight from private questions or held-out answers; mixed public/private suite.'
    b.benchmarks[keys['intelligenceIndex']]['components']=[{'benchmark_id':keys[field],'weight':weight} for field,weight in components]
    b.benchmarks[keys['intelligenceIndex']]['description']='Published v5.0 composite: knowledge work, coding, science and general each carry 25%. Elo components require upstream scaling; a raw weighted average of these columns does not reproduce the published index.'
    return len(models)


def ingest_home(b, flight):
    for obj in flight.objects():
        if isinstance(obj.get('benchmarkRows'),list):
            for row in flight.resolve(obj['benchmarkRows']):
                meta=dict(model=row['display']['model'],lab=', '.join(x['name'] for x in row.get('modelCreators',[])),
                    harness=row['agentName'],source_model_id=row['id'],date=None,notes='Agent and model run; harness versions preserved separately.',harness_versions=row.get('versions'),router=row.get('isRouter'))
                key=b.benchmark('coding-agent-index','AA Coding Agent Index','Coding','%',ROOT+'/agents/coding-agents','2.0',kind='composite')
                mean=row.get('mean') or {}
                b.add(key,meta,row.get('indexScore'),scale=100,
                    **task_fields(mean.get('costUsd'),mean.get('agentWallTimeSec'),
                        'AA Coding Agent Index v2.0 mean per task for this agent/model run'))
                for ev in row.get('evals',[]):
                    key=b.benchmark('coding-agent-'+ev['datasetIndexName'],ev['evaluationDatasetSlug']+' · coding agents','Coding','%',ROOT+'/agents/coding-agents',description='Artificial Analysis coding-agent evaluation. Each observation retains its own agent harness.')
                    b.add(key,meta,(ev.get('mean') or {}).get('reward'),scale=100)
        if isinstance(obj.get('contestants'),list):
            key=b.benchmark('decision-index','AA Decision Index','General','%',EVAL_URL+'/artificial-analysis-decision-index',kind='composite')
            for row in flight.resolve(obj['contestants']):
                meta=dict(model=row['name'],lab=row.get('creatorName'),source_model_id=row['slug'],date=None,harness=row.get('hostName'),model_kind=row.get('kind'))
                b.add(key,meta,row.get('indexScore'),
                    **task_fields(row.get('costPerTaskUsd'),row['timePerTaskMs']/1000 if number(row.get('timePerTaskMs')) else None,
                        'AA Decision Index mean per task for this contestant'))
                for field,value in row.get('scores',{}).items():
                    sub=b.benchmark('decision-'+field,'Decision · '+re.sub(r'([A-Z])',r' \1',field).capitalize(),'General','%',EVAL_URL+'/artificial-analysis-decision-index',description='Decision-model evaluation, separate from language-model suite.')
                    b.add(sub,meta,value)
        if obj.get('evalSlug')=='artificial-analysis-cyber-index' and isinstance(obj.get('models'),list):
            key=b.benchmark('cyber-index','AA Cyber Index','Coding','%',EVAL_URL+'/artificial-analysis-cyber-index','1',kind='composite')
            for row in flight.resolve(obj['models']):
                b.add(key,dict(model=row['name'],source_model_id=row['id'],date=None),row.get('score'),refusal_rate=row.get('refusalRate'))


def ingest_media(b, flight, url):
    count=0
    for obj in flight.objects():
        properties=[k for k in ('initialData','withAudioData','withoutAudioData') if isinstance(obj.get(k),str) and obj[k].startswith('$Q')]
        for prop in properties:
            title=obj.get('titleNoAudio') if prop=='withoutAudioData' else obj.get('title')
            title=title or url.rsplit('/',1)[-1]
            tags={v['slug']:v.get('displayName',v.get('label',v['slug'])) for v in flight.resolve(obj.get('tags',[]))}
            for category,rows in flight.resolve(obj[prop]):
                label=tags.get(category,category) if category else 'Overall'
                key=b.benchmark('media-'+slug(title)+'-'+(category or 'overall'),title+(' · '+label if category else ''),'Multimodal','Elo',url,kind='benchmark',native='Media preference',description='Blind pairwise human preference Elo. Category scores use separate fits; confidence intervals and vote counts are preserved.',media_category=label)
                for item in rows:
                    row=item['values']; creator=row.get('creator') or {}
                    meta=dict(model=row['name'],lab=creator.get('name'),source_model_id=row['id'],date=None,release_date=row.get('releaseDate'),weights='open' if row.get('openWeightsUrl') else 'unknown')
                    b.add(key,meta,row.get('elo'),ci_low=row.get('ciLower'),ci_high=row.get('ciUpper'),sample_count=row.get('appearances'),price_per_1000_images=row.get('pricePer1kImages'),price_per_video_minute=row.get('pricePerMinute'),notes=row.get('note'),deprecated=not row.get('isCurrent',True))
                    count+=1
            b.item(title,url,'rankings, comparison, cost scatter, category filter','All public category tables, CIs and appearance counts. Media price units stay separate from token prices.')
    return count


def ingest_speech(b, flight, url):
    seen=set()
    key=b.benchmark('tts-elo','AA Text-to-Speech Preference','Multimodal','Elo',url,native='Media preference')
    for obj in flight.objects():
        if isinstance(obj.get('hostModels'),list):
            for host in flight.resolve(obj['hostModels']):
                m=host['model']
                if m['id'] in seen:continue
                seen.add(m['id'])
                b.add(key,dict(model=m['name'],lab=(m.get('creator') or {}).get('name'),source_model_id=m['id'],date=None,release_date=m.get('releaseDate'),weights='open' if m.get('isOpenWeights') else 'proprietary'),m.get('qualityElo'),ci_low=m.get('qualityEloCi95Lower'),ci_high=m.get('qualityEloCi95Upper'))
    b.item('Text-to-speech quality, speed, latency, cost and history',url,'rankings, confidence intervals','Preference Elo imported; endpoint speed, latency and history are not yet ported.',status='data-only')


def collect(fetch):
    b=Builder(); failures=[]; retrieved=datetime.now(timezone.utc).isoformat()
    # Required source: fail loudly rather than overwrite the prior pack with no data.
    model_flight=Flight(fetch(MODEL_URL))
    evaluation_flight=Flight(fetch(EVAL_URL))
    evals=next((d['evaluations'] for d in evaluation_flight.objects() if isinstance(d.get('evaluations'),list)),[])
    index_meta=next((x for x in evals if x.get('slug')=='artificial-analysis-intelligence-index'),{})
    if 'v5.0' not in index_meta.get('name',''):
        raise ValueError('AA Intelligence Index version changed; review weights and dataset mappings before importing')
    fetch(METHOD_URL)  # Record the methodology snapshot with the measurements.
    models=ingest_language(b,model_flight,evals)
    for url in [ROOT+'/']+FETCH_URLS[4:]:
        try:
            flight=Flight(fetch(url))
            if url==ROOT+'/':ingest_home(b,flight)
            elif '/text-to-speech/' in url:ingest_speech(b,flight,url)
            else:
                if not ingest_media(b,flight,url):raise ValueError('No readable public media leaderboard tables')
        except Exception as error:
            failures.append(f'{url}: {type(error).__name__}: {error}')
            b.item(url.rsplit('/',1)[-1],url,'rankings',str(error),status='unavailable')
    for name,view,notes in [
      ('Intelligence Index bars','rankings','All available v5 scores; missing model results remain missing.'),
      ('Intelligence vs cost per task; Pareto frontier','scatter','Uses actual published weighted task cost, not token-price estimates.'),
      ('Cost, time and token-use breakdowns','cost breakdown','Per-task components preserved on intelligence observations; comparison metrics also exposed.'),
      ('Capability Index comparison','heatmap, rankings','Six professional-domain composites.'),
      ('Individual evaluations and Intelligence Evaluation Relevance','heatmap, benchmark filters','Original skills, knowledge domains, attributes and versions preserved.'),
      ('AA-Briefcase rubric, analytical and presentation comparisons','comparison, scatter','Overall and component Elo with published confidence intervals.'),
      ('AA-Omniscience accuracy and hallucination comparison','scatter, rankings','Accuracy and non-hallucination are separate measurements.'),
      ('AA-PersonalityBench indexes and traits','heatmap, comparison','Communication traits are excluded from capability weighting by default.'),
      ('Openness Index','rankings','Describes access/transparency; not general capability.'),
      ('Input, output and cached token pricing','scatter, table','Prices are USD per million tokens; cache price is a separate metric.'),
      ('Context window and model size','scatter, table','Context tokens and total/active parameter counts are separate native units.'),
      ('Output speed and latency','scatter, rankings','Representative speed, time-to-first-chunk, first-answer and end-to-end timing; source percentile and prompt-length distributions retained.'),
      ('Coding Agent Index and evaluation/cost/time breakdown','rankings, comparison','Harness labels and versions preserved; runs are not collapsed into model-only scores.'),
      ('Decision Index and component evaluation comparisons','rankings, comparison','Decision and language-model evaluations remain distinct.'),
      ('Cyber Index and safety blocks','rankings','Published success and refusal data retained when available.'),
    ]:b.item(name,ROOT+'/models' if 'Agent' not in name else ROOT+'/agents/coding-agents',view,notes)
    for name in ['Open Weights / Proprietary','Text Only / Multimodal Inputs','By Country','Creator / provider','Reasoning effort','Release / deprecated variants','Context window','Model size / active parameters']:
        b.item(name,ROOT+'/models','filter',type='category',notes='Original per-model metadata is retained; UI may expose a subset.')
    covered_urls={o['source_url'] for o in b.observations}
    for ev in evals:
        b.item(ev['name'],EVAL_URL+'/'+ev['slug'],'benchmark catalog',type='dataset',status='data-only' if EVAL_URL+'/'+ev['slug'] in covered_urls else 'unavailable',notes='Skills: '+', '.join(ev.get('skills',[]))+'; domains: '+', '.join(ev.get('knowledge',[]))+'; attributes: '+', '.join(ev.get('attributes',[])))
    for name,url,notes in [
      ('Progress Index and historical frontier',ROOT+'/trends','History is not inferred from current scores or release dates; no historical data imported.'),
      ('Multilingual Index and language splits',EVAL_URL+'/global-mmlu-lite','Language-specific source arrays are not present in the full model payload.'),
      ('Speech recognition and streaming',ROOT+'/speech-to-text/non-streaming','Separate speech benchmark data not imported in this adapter version.'),
      ('API endpoint throughput and availability',ROOT+'/providers','Per-host endpoint results are separate from representative model performance; not imported.'),
      ('Robotics',EVAL_URL+'/aa-robotics','Separate physical task results not imported.'),
      ('Search API benchmark',ROOT+'/search','Retrieval benchmark results not imported.'),
    ]:b.item(name,url,'source link',notes,status='unavailable')
    # Home page repeats some values in its bar and scatter components.
    unique={}
    for observation in b.observations:
        identity=(observation['benchmark_id'],observation.get('source_model_id'),observation['model'],observation.get('harness'))
        if identity in unique and unique[identity]['score'] != observation['score']:
            raise ValueError(f'Conflicting repeated AA observation: {identity}')
        unique.setdefault(identity,observation)
    b.observations=list(unique.values())
    observed={o['benchmark_id'] for o in b.observations}
    b.benchmarks={k:v for k,v in b.benchmarks.items() if k in observed}
    return dict(schema_version=1,provider='aa',retrieved_at=retrieved,
        sources=[dict(id='aa',name='Artificial Analysis',url=ROOT+'/',data_url=MODEL_URL,methodology_url=METHOD_URL,
            status='partial',license='Not stated; attribution and upstream Terms of Use apply',
            extraction_method='Public server-rendered HTML React Flight JSON; no upstream JavaScript executed, no authenticated API calls.',
            data_urls=FETCH_URLS,
            notes=f'Independent AA evaluator runs. {models} language-model variants read from the full public comparison payload. Original benchmark authors are linked per metric. Null scores omitted; date is retrieval time only, not evaluation date. Media and agent scores are separate evaluations. API access requires a user-supplied account/key; no API used. History and several specialist families remain unavailable. '+('Optional source failures: '+'; '.join(failures) if failures else ''))],
        benchmarks=list(b.benchmarks.values()),observations=b.observations,inventory=b.inventory,
        extraction_errors=failures)
