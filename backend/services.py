import uuid
from .query_identity import payload_identity
from sqlalchemy import select
from .db import Session, Paper, Version, Membership, Job, now, touch

def enqueue(kind,payload):
    with Session.begin() as s:
        if s.bind.dialect.name=='sqlite': s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        for existing in s.scalars(select(Job).where(Job.status.in_(['queued','running','waiting','paused']),Job.kind==kind)):
            if payload_identity(existing.payload)==payload_identity(payload): return existing.id
        job=Job(id=uuid.uuid4().hex,kind=kind,payload=payload)
        s.add(job)
        return job.id

def upsert_papers(domain_id,items):
    new=0; updates=0
    with Session.begin() as s:
        for item in items:
            paper=s.get(Paper,item['id'])
            if not paper:
                paper=Paper(**item); s.add(paper); new+=1
            elif item['version']>=paper.version:
                if item['version']>paper.version: updates+=1
                for k,v in item.items():
                    if item.get('date_basis')=='announcement' and paper.date_basis=='submitted' and k in ('published','date_basis'): continue
                    setattr(paper,k,v)
            if not s.get(Version,(item['id'],item['version'])):
                s.add(Version(paper_id=item['id'],version=item['version'],metadata_json=item))
            if not s.get(Membership,(domain_id,item['id'])):
                s.add(Membership(domain_id=domain_id,paper_id=item['id']))
        touch(s)
    return new,updates
