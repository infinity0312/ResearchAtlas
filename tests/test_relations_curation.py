from fastapi.testclient import TestClient
from backend.app import app
from backend.db import Session,Paper,Analysis,Tag,PaperTag,DATA,Setting
from backend.graph_labels import acronym
from backend.relations import reference_hits
import json
client=TestClient(app);headers={'X-Atlas-Client':'1'}

def test_named_contribution_precedes_operator():
    assert acronym('Hadamard','QuaRot: Outlier-Free 4-Bit Inference')=='QuaRot'
    assert acronym('R1','SpinQuant: LLM Quantization with Learned Rotations')=='SpinQuant'
    assert acronym('GNN','A molecular model')=='GNN'

def setup_papers():
    with Session.begin() as s:
        for pid,title in [('a','A new molecular architecture'),('b','A foundational molecular prediction method')]:
            s.add(Paper(id=pid,title=title,abstract='',authors=[],categories=[],published='2020',updated='2020'))
        s.add(Analysis(paper_id='a',domain_id='molecules',version=1,taxonomy_version=1,model='fixture',content_hash='fixture-rel',result={'methods':['E(3) 等变网络模块','非常具体的新模块'],'topics':['性质预测'],'problems':['一整句局限描述']}))
    (DATA/'documents').mkdir(exist_ok=True)
    (DATA/'documents'/'fixture-rel.json').write_text(json.dumps([{'page':1,'text':'This extends the earlier architecture and improves accuracy.'},{'page':2,'text':'References\nSmith. A foundational molecular prediction method. 2019.'}]),encoding='utf8')

def test_reference_scan_idempotent_reject_and_revision():
    setup_papers()
    assert client.post('/api/relations/scan',headers=headers).json()['added']==1
    assert client.post('/api/relations/scan',headers=headers).json()['added']==0
    r=client.get('/api/relations').json()[0]
    assert r['kind']=='cites' and r['evidence']['page']==2
    assert client.patch('/api/relations/'+r['id'],headers=headers,json={'revision':1,'status':'rejected'}).status_code==200
    assert client.patch('/api/relations/'+r['id'],headers=headers,json={'revision':1,'status':'confirmed'}).status_code==409
    assert client.post('/api/relations/scan',headers=headers).json()['added']==0
    assert client.get('/api/relations').json()[0]['status']=='rejected'

def test_relation_requires_source_and_does_not_infer_inheritance():
    setup_papers()
    body={'source_id':'a','target_id':'b','kind':'extends','page':1,'quote':'This extends the earlier architecture and improves accuracy.','content_hash':'wrong'}
    assert client.post('/api/relations',headers=headers,json=body).status_code==409
    body['content_hash']='fixture-rel';body['quote']='An invented relation statement.'
    assert client.post('/api/relations',headers=headers,json=body).status_code==422
    body['quote']='This extends the earlier architecture and improves accuracy.'
    assert client.post('/api/relations',headers=headers,json=body).status_code==200

def test_compact_taxonomy_keeps_details_and_manual_tags():
    setup_papers()
    from backend.tags import import_analysis
    import_analysis()
    with Session.begin() as s:
        tag=Tag(id='manual',name='User label',normalized='user label',kind='custom');s.add(tag);s.flush();s.add(PaperTag(paper_id='a',tag_id='manual',source='manual'))
    result=client.post('/api/taxonomy/apply',headers=headers);assert result.status_code==200
    names={t['name'] for t in client.get('/api/tags').json()}
    assert 'User label' in names and '等变神经网络' in names
    assert '非常具体的新模块' not in names and '一整句局限描述' not in names
    import_analysis();assert {t['name'] for t in client.get('/api/tags').json()}==names
    with Session() as s:assert '非常具体的新模块' in s.get(Analysis,1).result['methods']

def test_non_reference_mentions_do_not_create_edges():
    class Target: title='A foundational molecular prediction method'
    assert list(reference_hits([{'page':1,'text':'We compare A foundational molecular prediction method.'}],[Target()]))==[]
