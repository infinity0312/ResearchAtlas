from fastapi.testclient import TestClient
from backend.app import app
from backend.db import Session,Paper,Membership,Analysis,Domain,now

client=TestClient(app)

def seed(count=1):
    with Session.begin() as s:
        for i in range(count):
            s.add(Paper(id=f'2609.{i:05d}',title=f'Molecular graph prediction {i}',abstract='分子生成模型与材料预测',authors=['Jane Doe','王小明'],published='2026-09-01',updated=now()))
            s.add(Membership(paper_id=f'2609.{i:05d}',domain_id='molecules' if i%2==0 else 'life'))

def search(q):return client.get('/api/papers',params={'q':q,'days':0}).json()

def test_index_search_literal_terms_languages_and_updates():
    seed()
    for q in ['GRAPH molecular','Jane prediction','王小明','王小','分子','生成模型','2609.00000','"Molecular graph"']:
        assert search(q)['total']==1,q
    assert search('molecular missing')['total']==0
    assert search('" OR *')['total']==0
    with Session.begin() as s:s.get(Paper,'2609.00000').title='Revised quantum study'
    assert search('graph')['total']==0
    assert search('quantum')['total']==1
    with Session.begin() as s:s.delete(s.get(Paper,'2609.00000'))
    assert search('quantum')['total']==0

def test_cursor_ties_and_concurrent_inserts_no_duplicates():
    seed(45)
    def page(cursor=''):return client.get('/api/papers',params={'feed':True,'days':0,'size':20,'cursor':cursor}).json()
    first=page();assert len(first['items'])==20
    with Session.begin() as s:s.add(Paper(id='new',title='New',abstract='',published='2026-09-02',updated=now()))
    second=page(first['next_cursor']);third=page(second['next_cursor'])
    ids=[p['id'] for batch in [first,second,third] for p in batch['items']]
    assert len(ids)==len(set(ids))==45
    assert third['next_cursor'] is None
    assert client.get('/api/papers?feed=true&cursor=invalid').status_code==422


def test_research_rank_applies_impact_to_matched_candidates():
    from backend.db import PaperRelation

    seed(6)
    with Session.begin() as s:
        s.get(Paper, '2609.00000').published = '2024-01-01'
        s.get(Paper, '2609.00001').published = '2025-01-01'
        cited_only_in_abstract = s.get(Paper, '2609.00002')
        cited_only_in_abstract.title = 'Improving experimental benchmarks'
        cited_only_in_abstract.abstract = 'Molecular graph prediction for benchmarks'
        for index in range(3, 6):
            source = s.get(Paper, f'2609.{index:05d}')
            source.title = 'Unrelated citing article'
            source.abstract = ''
            s.add(Analysis(paper_id=source.id, domain_id='molecules', version=1,
                           taxonomy_version=1, model='fixture', content_hash='current', result={}))
            for target in (0, 2):
                s.add(PaperRelation(source_id=source.id, target_id=f'2609.{target:05d}', kind='cites',
                                    evidence={'version': 1,'page': 2,'content_hash': 'current',
                                              'quote': 'Reference for test citation.'}))
        s.add(PaperRelation(source_id='2609.00003',target_id='2609.00001',kind='cites',
                            evidence={'version': 1,'page': 2,'content_hash': 'old',
                                      'quote': 'Reference for outdated source.'}))

    params = {'q': 'molecular graph','days': 0,'feed':True,'size':1}
    first = client.get('/api/papers',params=params).json()
    assert first['total']==3
    assert first['items'][0]['id']=='2609.00000'
    assert first['items'][0]['search_rank']=={'exact_id':False,'title_hits':2,'terms':2,'local_citations':3,'curation_reason':None}
    second = client.get('/api/papers',params={**params,'cursor':first['next_cursor']}).json()
    assert second['items'][0]['id']=='2609.00002'
    assert second['items'][0]['search_rank']['local_citations']==3
    third = client.get('/api/papers',params={**params,'cursor':second['next_cursor']}).json()
    assert third['items'][0]['id']=='2609.00001'
    assert third['items'][0]['search_rank']['local_citations']==0
    assert third['next_cursor'] is None
    assert client.get('/api/papers',params={**params,'domain_id':'molecules','cursor':first['next_cursor']}).status_code==422
    recent = client.get('/api/papers',params={**params,'sort':'recent'}).json()
    assert recent['items'][0]['id']=='2609.00002'
    exact = search('2609.00000')['items'][0]
    assert exact['search_rank']['exact_id']

    from backend.db import Setting, Version
    with Session.begin() as s:
        s.add(Setting(key='source-edit:current',value={'digest':'corrected'}))
    assert search('molecular graph')['items'][0]['id']=='2609.00001'
    with Session.begin() as s:
        s.add(Version(paper_id='2609.00000',version=1,metadata_json={'historical_curation':{'reason':'Foundational work'}}))
    ranked = search('molecular graph')['items'][0]
    assert ranked['id']=='2609.00000'
    assert ranked['search_rank']['curation_reason']=='Foundational work'


def test_historically_curated_abstract_match_ranks_above_title_match_and_excludes_nonmatches():
    from backend.db import Version
    seed(3)
    with Session.begin() as s:
        s.get(Paper,'2609.00001').title='A foundational research result'
        s.get(Paper,'2609.00001').abstract='Introduces graph prediction.'
        s.get(Paper,'2609.00002').title='Foundational benchmark'
        s.get(Paper,'2609.00002').abstract='No matching research term.'
        for pid in ('2609.00001','2609.00002'):
            s.add(Version(paper_id=pid,version=1,metadata_json={'historical_curation':{'reason':'Foundational work'}}))
    items=search('graph prediction')['items']
    assert [p['id'] for p in items]==['2609.00001','2609.00000']
    assert items[0]['search_rank']['title_hits']==0
    assert items[1]['search_rank']['title_hits']==2

def test_multiple_domains_union_and_classification_status():
    seed(4)
    with Session.begin() as s:
        s.add(Membership(paper_id='2609.00000',domain_id='life'))
        s.add(Analysis(paper_id='2609.00000',domain_id='molecules',version=1,taxonomy_version=0,model='test',content_hash='a',result={'topics':['性质预测'],'methods':[]}))
        s.add(Analysis(paper_id='2609.00002',domain_id='molecules',version=1,taxonomy_version=1,model='test',content_hash='b',result={'topics':['Other'],'methods':[]}))
    data=client.get('/api/hierarchy?days=0&domain_ids=molecules&domain_ids=life').json()
    assert data['total']==4
    assert {d['id'] for d in data['domains']}=={'molecules','life'}
    assert {p['status'] for d in data['domains'] for p in d['pending']}=={'分类版本待更新','分类未匹配','待分析全文'}
    assert client.get('/api/hierarchy?days=0&domain_ids=molecules').json()['total']==2
    matrix=client.get('/api/method-matrix?days=365&domain_ids=life').json()
    assert matrix['papers']==[]


def test_missing_tag_definition_uses_current_matching_evidence_only():
    from backend.db import Tag
    seed()
    with Session.begin() as s:
        s.add(Tag(id='graph',kind='method',name='Graph model',normalized='graph model'))
        s.add(Analysis(paper_id='2609.00000',domain_id='molecules',version=1,taxonomy_version=1,model='test',content_hash='a',result={'methods':['Graph model'],'claims':[{'text':'Graph model predicts molecular properties.','kind':'method'}]}))
    result=client.get('/api/tags').json()[0]
    assert result['description']==''
    assert result['suggestion']=='Graph model predicts molecular properties.'
    assert result['suggestion_paper']=='2609.00000'
    with Session.begin() as s:s.get(Paper,'2609.00000').version=2
    assert 'suggestion' not in client.get('/api/tags').json()[0]
