from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app import app
from backend.db import *
from backend.trend_signals import insight,summarize,period_key
from backend.trends import buckets
from backend.services import upsert_papers
c=TestClient(app);H={'X-Atlas-Client':'1'}
def test_highlight_roundtrip_and_version_isolation():
    upsert_papers('molecules',[dict(id='2609.10000',version=1,title='Test',abstract='',authors=[],categories=[],published=now(),updated=now())])
    body={'version':1,'page':2,'quote':'test text','rects':[{'x':.1,'y':.2,'w':.3,'h':.02}]}
    r=c.post('/api/paper/highlights?id=2609.10000',headers=H,json=body);assert r.status_code==200
    mark=r.json()['id']
    assert len(c.get('/api/paper/highlights?id=2609.10000&version=1').json())==1
    assert c.get('/api/paper/highlights?id=2609.10000&version=2').json()==[]
    assert c.patch(f'/api/paper/highlights/{mark}?id=2609.10000',headers=H,json={'note':'My note'}).json()['note']=='My note'
    assert c.delete(f'/api/paper/highlights/{mark}?id=other',headers=H).status_code==404
    assert c.post('/api/paper/highlights?id=2609.10000',headers=H,json={**body,'rects':[{'x':.9,'y':.2,'w':.3,'h':.02}]}).status_code==422
    assert c.delete(f'/api/paper/highlights/{mark}?id=2609.10000',headers=H).status_code==200
    assert c.get('/api/paper/highlights?id=2609.10000&version=1').json()==[]
def test_signals_missing_small_samples_and_rebound():
    bs=buckets('2020','2022','year');points=[{'count':n,'partial':False} for n in [100,90,130]]
    empty=insight('ti:test',bs,points);assert empty['y'] is None and empty['x']>50
    with Session.begin() as s:
        model=s.get(Setting,'llm').value['model']
        for (label,lo,hi),novelty in zip(bs,[90,10,90]):
            s.add(TrendEvidence(key=period_key('ti:test',lo,hi,model),result={'population':200,'sample':8,'papers':[{'novelty':novelty,'rigor':80,'headroom':60,'family':'GNN'} for _ in range(8)]}))
    result=insight('ti:test',bs,points);assert result['y']==70.5 and result['rebound']
    assert result['periods'][-1]['diversity']==1
    assert insight('ti:changed',bs,points)['y'] is None
    assert insight('ti:test',bs,[{'count':100,'partial':False},{'count':None,'partial':False},{'count':120,'partial':False}])['x'] is None
    assert summarize({'papers':[],'sample':0})['opportunity'] is None
def test_macro_sampling_uses_unranked_population_and_reuses_cache():
    from backend.trend_signals import analyze_period
    papers=[{'id':str(i),'title':'Test','abstract':'Exact abstract evidence for research.','published':'2020-01-01'} for i in range(30)]
    class Model:
        config={'model':'test'}
        def generate(self,prompt):
            import json
            items=json.loads(prompt.split('\nPapers: ')[1])
            return {'papers':[{'id':p['id'],'novelty':75,'rigor':65,'headroom':50,'headroom_evidence':0,'family':'GNN','bottleneck':'Open task','evidence_index':0} for p in items]}
    with patch('backend.trend_signals.collect',return_value=(papers,None)) as remote,patch('backend.analysis.DeepSeek',return_value=Model()):
        result=analyze_period('ti:test','202001010000','202012312359',lambda m:None)
        assert result['sample']==24 and result['population']==30
        assert analyze_period('ti:test','202001010000','202012312359',lambda m:None)==result
        assert remote.call_count==1
