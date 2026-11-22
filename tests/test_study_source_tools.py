import json
from types import SimpleNamespace
import pytest
from backend.study_source_tools import dispatch, run


BLOCKS={'p1b1':{'page':1,'text':'Table header'},'p1b2':{'page':1,'text':'GraphSAGE result'},'p2b1':{'page':2,'text':'Appendix'}}


def test_read_expands_complete_page_and_rejects_paths():
    assert set(dispatch('read_evidence',{'ids':['p1b2']},BLOCKS)['blocks'])=={'p1b1','p1b2'}
    for name,args in [('read_evidence',{'ids':['../../secret']}),('shell',{}),('search_source',{'query':''})]:
        with pytest.raises(ValueError):dispatch(name,args,BLOCKS)
    assert dispatch('search_source',{'query':'graphsage'},BLOCKS)['matches'][0]['id']=='p1b2'


def test_reasoning_tool_history_and_budget_preserved(monkeypatch,tmp_path):
    import backend.study_source_tools as module
    monkeypatch.setattr('backend.model_control.require_enabled',lambda:None)
    sent=[]
    msg={'role':'assistant','content':None,'reasoning_content':'private continuity','tool_calls':[{'id':'c1','type':'function','function':{'name':'read_evidence','arguments':'{"ids":["p1b2"]}'}}]}
    responses=[{'usage':{'completion_tokens':100},'choices':[{'message':msg,'finish_reason':'tool_calls'}]},
               {'usage':{'completion_tokens':100},'choices':[{'message':{'role':'assistant','content':'{"ok":true}'},'finish_reason':'stop'}]}]
    class Client:
        def __init__(self,**kw):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def post(self,url,headers,json):
            sent.append(__import__('copy').deepcopy(json))
            response=responses.pop(0)
            return SimpleNamespace(status_code=200,json=lambda:response)
    monkeypatch.setattr(module.httpx,'Client',Client)
    p=SimpleNamespace(thinking_enabled=True,system_prompt='source',config={'base_url':'https://test'},key='test',request_body=lambda prompt:{'model':'test','thinking':{'type':'enabled'},'reasoning_effort':'high'})
    assert run(p,'test',BLOCKS,tmp_path/'run',output_budget=2000,max_turns=2)=={'ok':True}
    assert sent[1]['messages'][2]['reasoning_content']=='private continuity'
    assert sent[1]['max_tokens']==1900
    assert sent[1]['tool_choice']=='none'
    assert sent[1]['reasoning_effort']=='low' and sent[0]['reasoning_effort']=='high'
    assert 'private continuity' not in (tmp_path/'run'/'answer-0.json').read_text()
