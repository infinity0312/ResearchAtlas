"""Query semantics and bounded work; no machine-specific latency threshold."""
from sqlalchemy import func, insert, select

from backend.app import filter_analysis_fields, paper_query
from backend.db import Analysis, Domain, Membership, Paper, Session, engine, now


def _count(domain_id=None, topic=None, method=None):
    query=filter_analysis_fields(paper_query(domain_id, days=0),domain_id,topic,method)
    return select(func.count()).select_from(query.subquery())


def test_topic_filter_uses_indexed_paper_lookup_at_library_scale():
    stamp=now()
    with Session.begin() as s:
        s.execute(insert(Paper),[{'id':f'p{i}', 'version':1, 'title':f'Paper {i}',
            'abstract':'fixture', 'published':stamp, 'updated':stamp} for i in range(5000)])
        s.execute(insert(Membership),[{'paper_id':f'p{i}','domain_id':'molecules'} for i in range(5000)])
        s.execute(insert(Analysis),[{'paper_id':f'p{i}','domain_id':'molecules','version':1,
            'taxonomy_version':1,'model':'fixture','content_hash':'fixture',
            'result':{'topics':['Prediction'],'methods':['GNN']}} for i in range(500)])
    sql=str(_count('molecules','Prediction','GNN').compile(engine,compile_kwargs={'literal_binds':True}))
    with engine.connect() as connection:
        plan=[row[3] for row in connection.exec_driver_sql('EXPLAIN QUERY PLAN '+sql)]
        assert not any('CORRELATED LIST SUBQUERY' in row for row in plan)
        assert any('SEARCH analyses' in row and 'paper_id=?' in row for row in plan)
        # The old version-only correlated IN scanned 500 analyses for each of
        # 5,000 papers. Stop that quadratic behavior without waiting or timing.
        raw=connection.connection.driver_connection
        ticks=0
        def bound_work():
            nonlocal ticks
            ticks+=1
            return int(ticks>1000)
        raw.set_progress_handler(bound_work,1000)
        try:
            assert connection.exec_driver_sql(sql).scalar_one()==500
        finally:
            raw.set_progress_handler(None,0)
        assert ticks<1000


def test_labels_must_match_one_current_analysis_in_the_selected_domain():
    stamp=now()
    with Session.begin() as s:
        s.get(Domain,'life').taxonomy_version=2
        s.add_all([Paper(id='p',version=2,title='Paper',abstract='fixture',published=stamp,updated=stamp),
                   Membership(paper_id='p',domain_id='molecules'),Membership(paper_id='p',domain_id='life')])
        def row(domain,version,taxonomy,topics,methods):
            return Analysis(paper_id='p',domain_id=domain,version=version,taxonomy_version=taxonomy,
                            model='fixture',content_hash='fixture',result={'topics':topics,'methods':methods})
        s.add_all([
            row('molecules',1,1,['OldTopic'],['OldMethod']),
            row('molecules',2,1,['Prediction'],['GNN']),
            row('molecules',2,1,['SeparateTopic'],['SeparateMethod']),
            row('life',2,1,['StaleTaxonomy'],['StaleMethod']),
            row('life',2,2,['LifeTopic'],['LifeMethod']),
        ])
    with Session() as s:
        assert s.scalar(_count('molecules','Prediction','GNN'))==1
        assert s.scalar(_count(None,'LifeTopic','LifeMethod'))==1
        assert s.scalar(_count('molecules','Prediction','SeparateMethod'))==0
        assert s.scalar(_count('molecules','OldTopic','OldMethod'))==0
        assert s.scalar(_count('life','StaleTaxonomy','StaleMethod'))==0
        assert s.scalar(_count('life','Prediction','GNN'))==0
        assert s.scalar(_count(None,'Prediction','LifeMethod'))==0
