"""Immutable source blocks: models select IDs, application supplies exact evidence."""
import hashlib,json,re
from pydantic import BaseModel,Field
from typing import Literal
from .contracts import Extraction

class ClaimRef(BaseModel):
    kind:Literal['method','contribution','limitation']
    basis:Literal['author','observation','hypothesis']='author'
    text:str=Field(min_length=1,max_length=1500)
    evidence_id:str
    context_evidence_ids:list[str]=Field(default_factory=list,max_length=8,description='Source blocks supplying table title, column headers, units, footnotes, symbol definitions or continuation needed to understand the primary evidence. Preserve separate quotations; never fabricate a joined quote.')

def claim_row(claim,blocks):
    ids=[claim.evidence_id]+claim.context_evidence_ids
    if len(set(ids))!=len(ids):raise ValueError('Duplicate claim evidence IDs')
    if any(i not in blocks for i in ids):raise ValueError('Claim evidence ID is unknown')
    primary=blocks[claim.evidence_id]
    return dict(kind=claim.kind,basis=claim.basis,text=claim.text,page=primary['page'],quote=primary['text'].strip(),
                supporting_evidence=[dict(page=blocks[i]['page'],quote=blocks[i]['text'].strip()) for i in claim.context_evidence_ids])

class EvidenceReview(BaseModel):
    summary:str=Field(max_length=3000)
    topics:list[str]=Field(min_length=1,max_length=3)
    methods:list[str]=Field(min_length=1,max_length=15)
    problems:list[str]=Field(default_factory=list,max_length=8)
    claims:list[ClaimRef]=Field(min_length=8,max_length=35)
    fulltext_markdown:str=Field(min_length=3000,max_length=50000)

HEADINGS=['研究问题与核心贡献','方法与数学机制','实验设计与关键结果','局限、适用边界与复现','研究脉络与实践启示']
def source_blocks(pages):
    result={}
    for page in pages:
        text=page['text'];start=0;index=0
        while start<len(text):
            end=min(len(text),start+1200)
            if end<len(text):
                split=text.rfind('\n',start+600,end)
                if split>start:end=split+1
            excerpt=text[start:end]
            if len(excerpt.strip())<12 and index:
                result[f"p{page['page']}b{index}"]['text']+=excerpt
            elif len(excerpt.strip())>=12:
                index+=1;result[f"p{page['page']}b{index}"]={'page':page['page'],'text':excerpt}
            start=end
    return result

def resolve(review,blocks,topics):
    if set(review.topics)-set(topics):raise ValueError('Invalid taxonomy IDs/names')
    headings=re.findall(r'^## (.+)$',review.fulltext_markdown,re.M)
    if headings!=HEADINGS:raise ValueError('Use the five required chapters in order')
    rows=[]
    for i,claim in enumerate(review.claims):
        if claim.evidence_id not in blocks:raise ValueError(f'claims.{i}.evidence_id is unknown')
        rows.append(claim_row(claim,blocks))
    result=Extraction(summary=review.summary,topics=review.topics,methods=review.methods,problems=review.problems,claims=rows).model_dump()
    result['fulltext_markdown']=review.fulltext_markdown
    return result
