import os,uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, event, String, Text, Integer, Boolean, JSON, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .migrations import register_migration_table, run_migrations

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('ATLAS_DATA', ROOT / 'data'))
DATA.mkdir(parents=True, exist_ok=True)
engine = create_engine(os.environ.get('ATLAS_DATABASE_URL', f'sqlite:///{DATA / "atlas.db"}'), connect_args={'check_same_thread': False, 'timeout': 20} if not os.environ.get('ATLAS_DATABASE_URL') else {})
if engine.dialect.name == 'sqlite':
    @event.listens_for(engine, 'connect')
    def pragmas(conn, _):
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA foreign_keys=ON')
Session = sessionmaker(engine, expire_on_commit=False)
def now(): return datetime.now(timezone.utc).isoformat()
class Base(DeclarativeBase): pass
register_migration_table(Base.metadata)

class Domain(Base):
    __tablename__ = 'domains'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default='')
    query: Mapped[str] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String, default='#496983')
    topics: Mapped[list] = mapped_column(JSON, default=list)
    definitions: Mapped[list] = mapped_column(JSON, default=list)
    taxonomy_version: Mapped[int] = mapped_column(Integer, default=1)
    taxonomy_origin: Mapped[str] = mapped_column(String, default='手动预设')
    auto_sync: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync: Mapped[str | None] = mapped_column(String, nullable=True)
    sync_note: Mapped[str] = mapped_column(Text, default='等待首次同步')

class Paper(Base):
    __tablename__ = 'papers'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(Text)
    abstract: Mapped[str] = mapped_column(Text)
    authors: Mapped[list] = mapped_column(JSON, default=list)
    categories: Mapped[list] = mapped_column(JSON, default=list)
    published: Mapped[str] = mapped_column(String, index=True)
    updated: Mapped[str] = mapped_column(String)
    first_seen: Mapped[str] = mapped_column(String, default=now)
    saved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    date_basis: Mapped[str] = mapped_column(String, default='submitted')

class Membership(Base):
    __tablename__ = 'memberships'
    domain_id: Mapped[str] = mapped_column(String, primary_key=True)
    paper_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)

class Version(Base):
    __tablename__ = 'paper_versions'
    paper_id: Mapped[str] = mapped_column(String, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    metadata_json: Mapped[dict] = mapped_column(JSON)

class Analysis(Base):
    __tablename__ = 'analyses'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[str] = mapped_column(String, index=True)
    domain_id: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[int] = mapped_column(Integer)
    taxonomy_version: Mapped[int] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String)
    content_hash: Mapped[str] = mapped_column(String)
    result: Mapped[dict] = mapped_column(JSON)
    created: Mapped[str] = mapped_column(String, default=now)

class Survey(Base):
    __tablename__ = 'surveys'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    domain_id: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    filename: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default='uploaded')
    draft: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[str] = mapped_column(String, default=now)

class Taxonomy(Base):
    __tablename__ = 'taxonomies'
    domain_id: Mapped[str] = mapped_column(String, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    topics: Mapped[list] = mapped_column(JSON)
    definitions: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String)
    created: Mapped[str] = mapped_column(String, default=now)

class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, index=True, default='queued')
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default='等待后台处理')
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[str] = mapped_column(String, default=now, index=True)
    finished: Mapped[str | None] = mapped_column(String, nullable=True)

class Note(Base):
    __tablename__='notes'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=lambda:uuid.uuid4().hex)
    title: Mapped[str]=mapped_column(String(160))
    series: Mapped[str]=mapped_column(String(100),default='随手记')
    content: Mapped[str]=mapped_column(Text,default='')
    revision: Mapped[int]=mapped_column(Integer,default=1)
    archived: Mapped[bool]=mapped_column(Boolean,default=False)
    created: Mapped[str]=mapped_column(String,default=now)
    updated: Mapped[str]=mapped_column(String,default=now,index=True)

class MethodLesson(Base):
    __tablename__='method_lessons'
    analysis_id: Mapped[int]=mapped_column(Integer,primary_key=True)
    claim_index: Mapped[int]=mapped_column(Integer,primary_key=True)
    result: Mapped[dict]=mapped_column(JSON)
    model: Mapped[str]=mapped_column(String)
    created: Mapped[str]=mapped_column(String,default=now)

class Setting(Base):
    __tablename__ = 'settings'
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)

class Tag(Base):
    __tablename__='tags'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=lambda:uuid.uuid4().hex)
    name: Mapped[str]=mapped_column(String(100))
    normalized: Mapped[str]=mapped_column(String(100))
    kind: Mapped[str]=mapped_column(String)
    description: Mapped[str]=mapped_column(Text,default='')
    archived: Mapped[bool]=mapped_column(Boolean,default=False)
    aliases: Mapped[list]=mapped_column(JSON,default=list)
    __table_args__=(UniqueConstraint('kind','normalized'),)

class PaperTag(Base):
    __tablename__='paper_tags'
    paper_id: Mapped[str]=mapped_column(String,primary_key=True)
    tag_id: Mapped[str]=mapped_column(String,primary_key=True,index=True)
    source: Mapped[str]=mapped_column(String,default='manual')
    removed: Mapped[bool]=mapped_column(Boolean,default=False)

class GraphLabel(Base):
    __tablename__='graph_labels'
    paper_id: Mapped[str]=mapped_column(String,primary_key=True)
    label: Mapped[str]=mapped_column(String(24),default='')

class TrendSeries(Base):
    __tablename__='trend_series'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=lambda:uuid.uuid4().hex)
    name: Mapped[str]=mapped_column(String(80))
    query: Mapped[str]=mapped_column(Text)
    color: Mapped[str]=mapped_column(String,default='#496983')

class TrendCount(Base):
    __tablename__='trend_counts'
    key: Mapped[str]=mapped_column(String,primary_key=True)
    count: Mapped[int]=mapped_column(Integer)
    source: Mapped[str]=mapped_column(String,default='arxiv-api')
    fetched: Mapped[str]=mapped_column(String,default=now)

class CatalogPaper(Base):
    __tablename__='catalog_papers'
    id: Mapped[str]=mapped_column(String,primary_key=True)
    metadata_json: Mapped[dict]=mapped_column(JSON)
    fetched: Mapped[str]=mapped_column(String,default=now)

class SearchSnapshot(Base):
    __tablename__='search_snapshots'
    key: Mapped[str]=mapped_column(String,primary_key=True)
    query: Mapped[str]=mapped_column(Text)
    start: Mapped[str]=mapped_column(String)
    end: Mapped[str]=mapped_column(String)
    paper_ids: Mapped[list]=mapped_column(JSON,default=list)
    source: Mapped[str]=mapped_column(String)
    complete: Mapped[bool]=mapped_column(Boolean,default=False)
    fetched: Mapped[str]=mapped_column(String,default=now)

class SearchPage(Base):
    __tablename__='search_pages'
    key: Mapped[str]=mapped_column(String,primary_key=True)
    result: Mapped[dict]=mapped_column(JSON)
    fetched: Mapped[str]=mapped_column(String,default=now)

class ExplorationRank(Base):
    __tablename__='exploration_ranks'
    key: Mapped[str]=mapped_column(String,primary_key=True)
    paper_id: Mapped[str]=mapped_column(String,index=True)
    result: Mapped[dict]=mapped_column(JSON)
    created: Mapped[str]=mapped_column(String,default=now)

class PaperConversation(Base):
    __tablename__='paper_conversations'
    id:Mapped[str]=mapped_column(String,primary_key=True)
    paper_id:Mapped[str]=mapped_column(String,index=True)
    version:Mapped[int]=mapped_column(Integer)
    question:Mapped[str]=mapped_column(Text)
    selected_text:Mapped[str]=mapped_column(Text,default='')
    selected_page:Mapped[int]=mapped_column(Integer,default=0)
    deleted:Mapped[bool]=mapped_column(Boolean,default=False)
    answer:Mapped[str]=mapped_column(Text,default='')
    sources:Mapped[list]=mapped_column(JSON,default=list)
    scope:Mapped[str]=mapped_column(String,default='')
    model:Mapped[str]=mapped_column(String,default='')
    status:Mapped[str]=mapped_column(String,default='pending')
    error:Mapped[str]=mapped_column(String,default='')
    created:Mapped[str]=mapped_column(String,default=now)


def init_db():
    # Register optional runtime models after Base/Session are defined; importing
    # the module does not initialize or mutate the database.
    from . import model_runtime
    from .product import models as product_models
    run_migrations(engine, Base.metadata)
    with Session.begin() as s:
        if not s.get(Domain, 'molecules'):
            for d in [
                Domain(id='molecules', name='分子与材料', description='分子设计、材料发现与科学机器学习', query='(cat:cond-mat.mtrl-sci OR cat:physics.chem-ph) AND (all:"machine learning" OR all:"neural" OR all:"generative")', color='#496983', topics=['性质预测','分子生成','材料逆向设计','势能与模拟']),
                Domain(id='life', name='生命科学', description='蛋白质、基因组与细胞智能', query='(cat:q-bio.BM OR cat:q-bio.GN OR cat:q-bio.QM) AND (all:"learning" OR all:"model" OR all:"prediction")', color='#9b7cbd', topics=['蛋白质结构','蛋白质设计','基因组学','单细胞分析']),
                Domain(id='ml', name='机器学习', description='表示学习、模型方法与基础研究', query='cat:cs.LG', color='#ba8741', topics=['表示学习','生成模型','优化与泛化','强化学习'], auto_sync=False),
            ]:
                s.add(d)
                s.add(Taxonomy(domain_id=d.id, version=1, topics=d.topics, source='手动预设'))
        if not s.get(Setting, 'llm'):
            s.add(Setting(key='llm', value={'model':'deepseek-flash','base_url':'https://api.deepseek.com','auto_analyze':False,'daily_limit':20}))
        if not s.get(Setting,'revision'): s.add(Setting(key='revision',value={'id':uuid.uuid4().hex}))

    from .search import init_search
    init_search(engine)
    from .trends import seed_series
    seed_series()

def touch(s):
    row=s.get(Setting,'revision')
    if row: row.value={'id':uuid.uuid4().hex}

def serialize(obj): return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


class PdfHighlight(Base):
    __tablename__='pdf_highlights'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:str(uuid.uuid4()))
    paper_id:Mapped[str]=mapped_column(String,index=True)
    version:Mapped[int]=mapped_column(Integer)
    page:Mapped[int]=mapped_column(Integer)
    quote:Mapped[str]=mapped_column(Text)
    rects:Mapped[list]=mapped_column(JSON)
    note:Mapped[str]=mapped_column(Text,default='')
    created:Mapped[str]=mapped_column(String,default=now)

class TrendEvidence(Base):
    __tablename__='trend_evidence'
    key:Mapped[str]=mapped_column(String,primary_key=True)
    result:Mapped[dict]=mapped_column(JSON)
    created:Mapped[str]=mapped_column(String,default=now)

class PaperRelation(Base):
    __tablename__='paper_relations'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:uuid.uuid4().hex)
    source_id:Mapped[str]=mapped_column(String,index=True)
    target_id:Mapped[str]=mapped_column(String,index=True)
    kind:Mapped[str]=mapped_column(String,default='cites')
    evidence:Mapped[dict]=mapped_column(JSON,default=dict)
    status:Mapped[str]=mapped_column(String,default='confirmed')
    revision:Mapped[int]=mapped_column(Integer,default=1)
    origin:Mapped[str]=mapped_column(String,default='manual')
    created:Mapped[str]=mapped_column(String,default=now)
    __table_args__=(UniqueConstraint('source_id','target_id','kind'),)
