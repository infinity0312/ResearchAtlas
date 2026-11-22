import hashlib
from fastapi.testclient import TestClient
from backend.app import app
from backend.db import *
from backend.services import upsert_papers
from pypdf import PdfWriter
c=TestClient(app);H={'X-Atlas-Client':'1'}
def seed():
    texts=[('Electronic charge density','Equivariant electron density reconstruction for crystal electronic structure'),('Crystal electron charge prediction','Predicting electron density fields from crystal structure'),('Protein sequence folding','Amino acid folding for proteins and genomics')]
    upsert_papers('molecules',[dict(id=f'2609.{i:05}',version=1,title=t,abstract=a,authors=[],categories=['cs.LG'],published=now(),updated=now()) for i,(t,a) in enumerate(texts)])
def test_related_excludes_self_and_gives_real_keyword_reasons():
    seed();r=c.get('/api/paper/related',params={'id':'2609.00000'}).json()
    assert r['items'][0]['id']=='2609.00001'
    assert r['items'][0]['keywords'] and 'density' in r['items'][0]['keywords']
    assert all(p['id']!='2609.00000' for p in r['items'])
    assert all(p['id']!='2609.00002' for p in r['items'])
    assert c.get('/api/paper/related',params={'id':'missing'}).status_code==404
def test_related_tags_ignore_removed_and_archived():
    seed();t=c.post('/api/tags',headers=H,json={'name':'Common problem','kind':'problem'}).json()
    for pid in ['2609.00000','2609.00002']: c.put('/api/paper/tags/'+t['id'],params={'id':pid},headers=H)
    def suggestions():return c.get('/api/paper/related',params={'id':'2609.00000'}).json()['items']
    assert any(p['id']=='2609.00002' and p['shared_tags']==['Common problem'] for p in suggestions())
    c.put('/api/paper/tags/'+t['id'],params={'id':'2609.00002','removed':True},headers=H)
    assert all(p['id']!='2609.00002' for p in suggestions())
    c.put('/api/paper/tags/'+t['id'],params={'id':'2609.00002'},headers=H)
    c.put('/api/tags/'+t['id'],headers=H,json={**t,'archived':True})
    assert all(p['id']!='2609.00002' for p in suggestions())
def test_local_pdf_matches_requested_version_and_missing_fails():
    seed();pid='2609.00000';folder=DATA/'documents';folder.mkdir(exist_ok=True)
    path=folder/f'{hashlib.sha256(pid.encode()).hexdigest()}v1.pdf'
    w=PdfWriter();w.add_blank_page(width=100,height=100);w.write(path)
    info=c.get('/api/paper',params={'id':pid}).json();assert info['has_pdf'] and info['pdf_version']==1
    r=c.get('/api/paper/pdf',params={'id':pid,'version':1});assert r.status_code==200 and r.content.startswith(b'%PDF') and r.headers['content-type']=='application/pdf'
    assert c.get('/api/paper/pdf',params={'id':pid,'version':2}).status_code==404
    assert c.get('/api/paper/pdf',params={'id':'../../secrets','version':1}).status_code==404
