from io import BytesIO
from pypdf import PdfWriter
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from backend.app import app
from backend.db import Session,Paper,Membership,Job,DATA
from backend import paper_import
client=TestClient(app);headers={'X-Atlas-Client':'1'}
def pdf():
 w=PdfWriter();w.add_blank_page(width=612,height=792);w.add_metadata({'/Title':'Imported research'});b=BytesIO();w.write(b);return b.getvalue()
def upload(content=None,**fields):
 return client.post('/api/paper/import',headers=headers,data={'domain_id':'molecules','analyze':'false',**fields},files={'file':('research.pdf',pdf() if content is None else content,'application/pdf')})
def test_import_read_and_dedupe():
 a=upload(published='2001-02-03');assert a.status_code==201,a.text
 pid=a.json()['paper_id'];assert pid.startswith('local-')
 with Session() as s:
  p=s.get(Paper,pid);assert p.title=='Imported research';assert p.published.startswith('2001-02-03');assert s.get(Membership,('molecules',pid))
 b=upload(domain_id='life');assert b.json()['duplicate'];assert b.json()['paper_id']==pid
 with Session() as s:
  assert s.scalar(select(func.count()).select_from(Paper))==1;assert s.get(Membership,('life',pid))
 r=client.get('/api/paper/pdf',params={'id':pid,'version':1});assert r.status_code==200;assert r.content.startswith(b'%PDF')
def test_import_validation():
 assert upload(b'bad').status_code==422
 assert upload(b'%PDF malformed').status_code==422
 assert upload(b'').status_code==422
 assert upload(domain_id='missing').status_code==404
 assert upload(published='3000-01-01').status_code==422
 assert not list((DATA/'uploads').glob('import-*.pdf'))
def test_import_enqueues_standard_analysis_once(monkeypatch):
 monkeypatch.setattr(paper_import,'get_key',lambda:'test-only')
 a=upload(analyze='true').json();b=upload(analyze='true').json()
 assert a['job_id'] and a['job_id']==b['job_id']
 with Session() as s:
  job=s.get(Job,a['job_id']);assert job.kind=='analyze';assert job.payload=={'paper_id':a['paper_id'],'domain_id':'molecules'}
def test_import_without_key_still_preserves_pdf(monkeypatch):
 monkeypatch.setattr(paper_import,'get_key',lambda:None)
 a=upload(analyze='true');assert a.status_code==201;assert a.json()['job_id'] is None

