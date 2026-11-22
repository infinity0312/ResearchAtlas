import json
from fastapi.testclient import TestClient
from backend.app import app
from backend.db import Session,Paper,Analysis,DATA,now
from backend import paper_chat

client=TestClient(app);headers={'X-Atlas-Client':'1'}
def seed():
    with Session.begin() as s:
        for pid in ['paper-a','paper-b']:
            s.add(Paper(id=pid,title=pid,abstract='Quantization reduces memory.',published=now(),updated=now()))
    DATA.joinpath('documents').mkdir(exist_ok=True)
    DATA.joinpath('documents/chat-fixture.json').write_text(json.dumps([{'page':1,'text':'Quantization reduces memory by storing low-bit weights.'}]),encoding='utf8')
    with Session.begin() as s:s.add(Analysis(paper_id='paper-a',domain_id='molecules',version=1,taxonomy_version=1,model='test',content_hash='chat-fixture',result={}))

def test_chat_context_history_idempotency_and_version_isolation(monkeypatch):
    seed();prompts=[]
    monkeypatch.setattr(paper_chat,'get_key',lambda:'test')
    class Provider:
        config={'model':'test'}
        def generate(self,prompt):
            prompts.append(json.loads(prompt.split('\n',1)[1]));return {'answer':'权重量化可减少存储。[片段 0]\n\n$e=x-\\hat{x}$','source_ids':[0]}
    monkeypatch.setattr(paper_chat,'DeepSeek',Provider)
    def ask(pid,req):return client.post('/api/paper/chat?id='+pid,headers=headers,json={'question':'解释方法','request_id':req})
    a=ask('paper-a','request-0000000001').json();assert a['status']=='done';assert a['scope']=='已解析全文';assert a['sources'][0]['page']==1
    assert ask('paper-a','request-0000000001').json()['id']==a['id'];assert len(prompts)==1
    ask('paper-a','request-0000000002');assert len(prompts[-1]['conversation'])==1
    b=ask('paper-b','request-0000000003').json();assert b['scope']=='仅论文摘要';assert prompts[-1]['conversation']==[]
    with Session.begin() as s:s.get(Paper,'paper-a').version=2
    a=ask('paper-a','request-0000000004').json();assert a['scope']=='仅论文摘要';assert prompts[-1]['conversation']==[]
    assert len(client.get('/api/paper/chat?id=paper-a').json())==3

def test_chat_rejects_invalid_sources_and_missing_key(monkeypatch):
    seed();monkeypatch.setattr(paper_chat,'get_key',lambda:None)
    payload={'question':'解释','request_id':'request-0000000001'}
    assert client.post('/api/paper/chat?id=paper-a',headers=headers,json=payload).status_code==409
    monkeypatch.setattr(paper_chat,'get_key',lambda:'test')
    class Provider:
        config={'model':'test'}
        def generate(self,prompt):return {'answer':'answer','source_ids':[999]}
    monkeypatch.setattr(paper_chat,'DeepSeek',Provider)
    result=client.post('/api/paper/chat?id=paper-a',headers=headers,json=payload).json()
    assert result['status']=='failed';assert result['sources']==[]

def test_selection_persists_and_deleted_turns_are_excluded_from_context(monkeypatch):
    seed();prompts=[]
    monkeypatch.setattr(paper_chat,'get_key',lambda:'test')
    class Provider:
        config={'model':'test'}
        def generate(self,prompt):
            prompts.append(json.loads(prompt.split('\n',1)[1]));return {'answer':'Explanation','source_ids':[0]}
    monkeypatch.setattr(paper_chat,'DeepSeek',Provider)
    def ask(rid,selected=''):
        return client.post('/api/paper/chat?id=paper-a',headers=headers,json={'question':'解释此处','request_id':rid,'selected_text':selected,'selected_page':1}).json()
    result=ask('selection-00000001','Quantization reduces memory')
    assert result['selected_text']=='Quantization reduces memory'
    assert prompts[-1]['selected_excerpt']==result['selected_text']
    assert client.delete('/api/paper/chat/selection-00000001?id=paper-b',headers=headers).status_code==404
    assert client.delete('/api/paper/chat/selection-00000001?id=paper-a',headers=headers).status_code==200
    assert client.get('/api/paper/chat?id=paper-a').json()==[]
    assert len(client.get('/api/paper/chat?id=paper-a&deleted=true').json())==1
    ask('selection-00000002');assert prompts[-1]['conversation']==[]
    assert client.post('/api/paper/chat/selection-00000001/restore?id=paper-a',headers=headers).status_code==200
    assert len(client.get('/api/paper/chat?id=paper-a').json())==2
