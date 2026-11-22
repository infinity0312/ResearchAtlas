import json
import pytest,httpx
from pydantic import BaseModel
from backend.llm_runtime import validated,validated_items,reviewed
from backend.analysis import DeepSeek,ModelServiceError
class Item(BaseModel):
    id:str
    value:int
class Fake:
    config={'model':'test'}
    def __init__(self,results):self.results=iter(results);self.prompts=[]
    def generate(self,prompt):self.prompts.append(prompt);return next(self.results)
def test_partial_repair_does_not_resend_successful_sources():
    m=Fake([{'papers':[{'id':'a','value':1},{'id':'b','value':'bad'}]},{'papers':[{'id':'b','value':2}]}])
    out=validated_items(m,'Return JSON',[{'id':'a','text':'LARGE SOURCE A'},{'id':'b','text':'SOURCE B'}],Item,lambda r:None)
    assert [r.value for r in out]==[1,2]
    assert 'LARGE SOURCE A' not in m.prompts[1] and 'SOURCE B' in m.prompts[1]
def test_duplicate_and_out_of_range_are_repaired():
    m=Fake([{'papers':[{'id':'a','value':99},{'id':'a','value':1}]},{'papers':[{'id':'a','value':99}]},{'papers':[{'id':'a','value':2}]}])
    def check(r):
        if r.value>3:raise ValueError('index out of range')
    assert validated_items(m,'JSON',[{'id':'a'}],Item,check)[0].value==2
    assert len(m.prompts)==3
def test_cached_results_revalidate_without_api(monkeypatch,tmp_path):
    monkeypatch.setattr('backend.llm_runtime.DATA',tmp_path)
    m=Fake([{'id':'a','value':1}]);m.validated_cache=True
    assert validated(m,'JSON',Item).value==1
    assert validated(m,'JSON',Item).value==1
    assert len(m.prompts)==1
    def stricter(r):raise ValueError('new gate')
    m.results=iter([{'id':'a','value':1}]*3)
    with pytest.raises(ValueError):validated(m,'JSON',Item,stricter)
def test_semantic_failure_never_publishes():
    issue={'issues':[{'field':'value','reason':'wrong','evidence':'source says 2'}]}
    m=Fake([{'id':'a','value':1},issue,{'id':'a','value':1},issue])
    with pytest.raises(ValueError,match='语义复核'):reviewed(m,'JSON',Item,lambda v:None,'source','test')
    assert len(m.prompts)==4
def test_terminal_auth_is_not_repaired(monkeypatch):
    monkeypatch.setattr('backend.analysis._circuits',{})
    monkeypatch.setattr('backend.analysis.get_key',lambda:'fake')
    calls=[]
    def post(*a,**k):calls.append(k);return httpx.Response(401)
    monkeypatch.setattr('backend.analysis._client.post',post)
    with pytest.raises(ModelServiceError):validated(DeepSeek(),'JSON',Item)
    assert len(calls)==1
def test_truncation_and_bad_json_fail_closed(monkeypatch):
    monkeypatch.setattr('backend.analysis._circuits',{})
    monkeypatch.setattr('backend.analysis.get_key',lambda:'fake')
    replies=iter([{'finish_reason':'length','message':{'content':'{}'}},{'finish_reason':'stop','message':{'content':'{"id":"a","value":2}'}}])
    monkeypatch.setattr('backend.analysis._client.post',lambda *a,**k:httpx.Response(200,json={'choices':[next(replies)]}))
    assert validated(DeepSeek(),'JSON truncation test',Item).value==2

def test_unknown_opportunity_is_not_zero():
    from backend.trend_signals import summarize
    r=summarize({'papers':[{'novelty':70,'rigor':65,'headroom':None,'family':'GNN'}]*10,'sample':10})
    assert r['opportunity'] is None and r['supported_sample']==0
