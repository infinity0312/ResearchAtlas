import os,tempfile,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
(root/'data'/'qa').mkdir(parents=True,exist_ok=True)
os.environ['ATLAS_DATA']=tempfile.mkdtemp(prefix='e2e-',dir=root/'data'/'qa')
os.environ['ATLAS_SCOPED_INTAKE_DISABLED']='1'
from backend.db import *
from backend.services import upsert_papers
init_db()
papers=[{'id':f'2609.{i:05d}','version':1,'title':title,'abstract':'A benchmark fixture for UI verification. We use equivariant graph neural networks for molecular prediction.','authors':['Test Researcher'],'categories':['cs.LG','q-bio.BM'],'published':now(),'updated':now()} for i,title in enumerate(['Equivariant models for molecular prediction','Protein sequence representation learning','Active learning for material discovery'])]
papers[1]['abstract']=r'''Formula fixture: $E=mc^2$ and \(\frac{a}{b}\). $$\begin{pmatrix}1&2\\3&4\end{pmatrix}$$ \[\sum_{i=1}^n i=\frac{n(n+1)}{2}\] \begin{align}a&=b+c\\d&=e\end{align} Invalid: $\badcommand{x}$ Unsafe: $\href{javascript:alert(1)}{x}$'''
upsert_papers('molecules',papers)
with Session.begin() as s:
    s.add(Analysis(paper_id=papers[0]['id'],domain_id='molecules',version=1,taxonomy_version=1,model='TEST FIXTURE',content_hash='fixture',result={'summary':'这是浏览器测试数据，不是真实模型分析。ρ_init 与 ρ_env 用于测试旧记法。','topics':['性质预测'],'methods':['等变 GNN'],'claims':[{'kind':'method','text':'等变图网络预测分子性质','basis':'author','page':1,'quote':'equivariant graph neural networks'}],'rejected_evidence':0,'pages':1,'coverage':'测试夹具','section_summaries':[]}))
(DATA/'documents').mkdir(exist_ok=True)
(DATA/'documents'/'fixture.json').write_text(json.dumps([{'page':1,'text':papers[0]['abstract']}]),encoding='utf-8')
from pypdf import PdfWriter
import hashlib
pdf=PdfWriter()
pdf.add_blank_page(width=612,height=792)
pdf.add_blank_page(width=612,height=792)
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
pdf.pages[0][NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})})})
stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 50 700 Td (Selectable original paper text.) Tj ET')
pdf.pages[0][NameObject('/Contents')]=pdf._add_object(stream)
pdf.write(DATA/'documents'/f"{hashlib.sha256(papers[0]['id'].encode()).hexdigest()}v1.pdf")
# Separate trend-intake fixtures do not change the existing preset scopes.
from backend.trends import buckets,key
from backend.trend_signals import period_key
with Session.begin() as s:
    fixture_query='ti:"intake fixture"'
    s.add(TrendSeries(id='qa-intake',name='趋势收录隔离夹具',query=fixture_query,color='#327c72'))
    _,lo,hi=buckets('2025','2025','year')[0]
    s.add(TrendCount(key=key(fixture_query,lo,hi),count=2,source='fixture-only'))
    samples=[{'id':pid,'title':title,'quote':'Isolated intake fixture, not a scientific finding.','bottleneck':'仅用于验证收录流程的隔离样本。','novelty':50,'rigor':50,'headroom':None,'family':'图神经网络','relevant':True} for pid,title in [('2609.09999','External intake fixture paper'),('2609.00000',papers[0]['title'])]]
    s.add(TrendEvidence(key=period_key(fixture_query,lo,hi,'codex-source-review'),result={'population':2,'sample':2,'papers':samples,'model':'fixture-only','rubric':'fixture-only','created':now()}))
import uvicorn
uvicorn.run('backend.app:app',host='127.0.0.1',port=8770)
