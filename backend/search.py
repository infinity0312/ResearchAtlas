"""Local paper search: transactional trigram index, literal AND terms."""
import base64
import hashlib
import json
import re

from fastapi import HTTPException
from sqlalchemy import and_, case, func, literal_column, or_, select, text
from sqlalchemy.orm import aliased

from .db import Analysis, Paper, PaperRelation, Setting, Version

def init_search(engine):
    with engine.begin() as c:
        ready=c.scalar(text("SELECT count(*) FROM sqlite_master WHERE name='papers_search_insert'"))
        c.exec_driver_sql("CREATE VIRTUAL TABLE IF NOT EXISTS papers_search USING fts5(id,title,abstract,authors,tokenize='trigram')")
        insert="INSERT INTO papers_search(rowid,id,title,abstract,authors) VALUES(new.rowid,new.id,new.title,new.abstract,(SELECT group_concat(value,' ') FROM json_each(new.authors)));"
        for event,body in [('insert',insert),('delete','DELETE FROM papers_search WHERE rowid=old.rowid;'),('update','DELETE FROM papers_search WHERE rowid=old.rowid; '+insert)]:
            c.exec_driver_sql(f'CREATE TRIGGER IF NOT EXISTS papers_search_{event} AFTER {event} ON papers BEGIN {body} END')
        if not ready:
            c.exec_driver_sql('DELETE FROM papers_search')
            c.exec_driver_sql("INSERT INTO papers_search(rowid,id,title,abstract,authors) SELECT rowid,id,title,abstract,(SELECT group_concat(value,' ') FROM json_each(papers.authors)) FROM papers")
        c.exec_driver_sql('CREATE INDEX IF NOT EXISTS ix_papers_feed ON papers(published DESC,id ASC)')

def search_terms(value):
    return list(dict.fromkeys(a or b for a,b in re.findall(r'"([^"]+)"|(\S+)', value.strip())))[:24]


def search_filter(query, value):
    # Quotes allow phrases. FTS operators are never executed from user input.
    terms=search_terms(value)
    indexed=[t for t in terms if len(t)>=3]
    if indexed:
        match=' AND '.join('"'+t.replace('"','""')+'"' for t in indexed)
        query=query.where(Paper.id.in_(text('SELECT id FROM papers_search WHERE papers_search MATCH :paper_search').bindparams(paper_search=match)))
    for term in terms:
        if len(term)<3:
            query=query.where(or_(*(col.icontains(term,autoescape=True) for col in (Paper.id,Paper.title,Paper.abstract,literal_column("(SELECT group_concat(value,' ') FROM json_each(papers.authors))")))))
    return query


def citation_signals():
    """Count distinct citing papers whose recorded evidence still matches their source."""
    source = aliased(Paper)
    latest = select(Analysis.content_hash).where(
        Analysis.paper_id == source.id, Analysis.version == source.version,
    ).order_by(Analysis.created.desc(), Analysis.id.desc()).limit(1).correlate(source).scalar_subquery()
    corrected = select(Setting.value['digest'].as_string()).where(
        Setting.key == 'source-edit:' + latest,
    ).correlate(source).scalar_subquery()
    return select(
        PaperRelation.target_id.label('paper_id'),
        func.count(func.distinct(PaperRelation.source_id)).label('citations'),
    ).join(source, source.id == PaperRelation.source_id).where(
        PaperRelation.kind == 'cites', PaperRelation.status == 'confirmed',
        PaperRelation.source_id != PaperRelation.target_id,
        PaperRelation.evidence['version'].as_integer() == source.version,
        PaperRelation.evidence['page'].as_integer() >= 1,
        func.length(PaperRelation.evidence['quote'].as_string()) >= 12,
        PaperRelation.evidence['content_hash'].as_string() == func.coalesce(corrected, latest),
    ).group_by(PaperRelation.target_id).subquery('incoming_citations')


def ranked_page(s, query, q, *, scope, page, size, feed, cursor):
    """Rank the already matched set by documented local research impact."""
    terms = search_terms(q)
    signals = citation_signals()
    id_hit = case((func.lower(Paper.id) == q.strip().strip('"').lower(), 1), else_=0)
    title_score = sum(case((Paper.title.icontains(t, autoescape=True), 1), else_=0) for t in terms)
    rationale = func.substr(func.trim(Version.metadata_json['historical_curation']['reason'].as_string()), 1, 200)
    curated = case((func.length(rationale) > 0, 1), else_=0)
    citations = func.coalesce(signals.c.citations, 0)
    impact = citations + curated * 5
    candidates = query.with_only_columns(
        Paper.id, Paper.published, id_hit.label('id_hit'), title_score.label('title_hits'),
        impact.label('impact'), rationale.label('curation_reason'), citations.label('citations'),
    ).outerjoin(Version, and_(Version.paper_id == Paper.id, Version.version == Paper.version)).outerjoin(
        signals, signals.c.paper_id == Paper.id,
    ).subquery('ranked_matches')
    c = candidates.c
    columns = (c.id_hit, c.impact, c.title_hits, c.published, c.id)
    ranked = select(Paper, c.id_hit, c.impact, c.title_hits, c.citations, c.curation_reason).join(candidates, c.id == Paper.id)
    scope_key = hashlib.sha256(json.dumps(['impact-v2', terms, q.strip().lower(), scope], ensure_ascii=False).encode()).hexdigest()[:20]
    if feed and cursor:
        try:
            key, exact, score, hits, published, pid = json.loads(base64.urlsafe_b64decode(cursor))
            if (key != scope_key or type(exact) is not int or exact not in (0, 1)
                    or type(hits) is not int or not 0 <= hits <= len(terms)
                    or type(score) is not int or score < 0
                    or not isinstance(published, str) or not isinstance(pid, str)):
                raise ValueError('Invalid ranking cursor')
        except (TypeError, ValueError) as exc:
            raise HTTPException(422, '滚动位置与当前检索不符，请重新搜索') from exc
        values = (exact, score, hits, published, pid)
        ranked = ranked.where(or_(*(
            and_(*(columns[j] == values[j] for j in range(i)),
                 column > values[i] if i == len(columns)-1 else column < values[i])
            for i, column in enumerate(columns)
        )))
    ranked = ranked.order_by(*(column.desc() for column in columns[:-1]), c.id)
    rows = list(s.execute(ranked.offset(0 if feed else (page-1)*size).limit(size+int(feed))))
    next_cursor = None
    if feed and len(rows) > size:
        paper, exact, score, hits, _, _ = rows[size-1]
        next_cursor = base64.urlsafe_b64encode(
            json.dumps([scope_key, exact, score, hits, paper.published, paper.id]).encode()
        ).decode()
    return [paper for paper, *_ in rows[:size]], next_cursor, {
        paper.id: {'exact_id': bool(exact), 'title_hits': hits, 'terms': len(terms), 'local_citations': cites,
                   'curation_reason': reason or None}
        for paper, exact, _, hits, cites, reason in rows[:size]
    }
