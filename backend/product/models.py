"""Project aggregates and immutable review/delivery history.

Project IDs scope product objects inside one local installation. They are not
tenant boundaries or authenticated user identities.
"""
import uuid
from sqlalchemy import String, Text, Integer, Boolean, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base, now


def uid():
    return uuid.uuid4().hex


class ResearchProject(Base):
    __tablename__ = 'research_projects'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(160))
    scenario: Mapped[str] = mapped_column(String(60))
    owner: Mapped[str] = mapped_column(String(100), default='')
    question: Mapped[str] = mapped_column(Text)
    constraints: Mapped[str] = mapped_column(Text, default='')
    criteria: Mapped[list] = mapped_column(JSON)
    recommendation: Mapped[str] = mapped_column(Text, default='')
    open_questions: Mapped[str] = mapped_column(Text, default='')
    status: Mapped[str] = mapped_column(String(30), default='draft')
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created: Mapped[str] = mapped_column(String, default=now)
    updated: Mapped[str] = mapped_column(String, default=now)


class ProjectEvidence(Base):
    __tablename__ = 'project_evidence'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('research_projects.id'), index=True)
    analysis_id: Mapped[int] = mapped_column(Integer)
    paper_id: Mapped[str] = mapped_column(String)
    claim_index: Mapped[int] = mapped_column(Integer)
    criterion_id: Mapped[str] = mapped_column(String(60))
    stance: Mapped[str] = mapped_column(String(30))
    context: Mapped[str] = mapped_column(Text)
    snapshot: Mapped[dict] = mapped_column(JSON)
    created: Mapped[str] = mapped_column(String, default=now)
    __table_args__ = (UniqueConstraint('project_id', 'analysis_id', 'claim_index', 'criterion_id'),)


class AgentArtsReview(Base):
    __tablename__ = 'agentarts_reviews'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('research_projects.id'), index=True)
    project_revision: Mapped[int] = mapped_column(Integer)
    expected_revision: Mapped[int] = mapped_column(Integer)
    query: Mapped[str] = mapped_column(String(160))
    state: Mapped[str] = mapped_column(String(16), default='running')
    execution_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    assessments: Mapped[list] = mapped_column(JSON, default=list)
    bindings: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default='')
    created: Mapped[str] = mapped_column(String, default=now)


class ProjectReview(Base):
    __tablename__ = 'project_reviews'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('research_projects.id'), index=True)
    project_revision: Mapped[int] = mapped_column(Integer)
    evidence_fingerprint: Mapped[str] = mapped_column(String(64))
    reviewer: Mapped[str] = mapped_column(String(100))
    note: Mapped[str] = mapped_column(Text)
    created: Mapped[str] = mapped_column(String, default=now)


class ProjectDelivery(Base):
    __tablename__ = 'project_deliveries'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('research_projects.id'), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    source_revision: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(180))
    created: Mapped[str] = mapped_column(String, default=now)
    digest: Mapped[str] = mapped_column(String(64))
    manifest: Mapped[dict] = mapped_column(JSON)
    markdown: Mapped[str] = mapped_column(Text)
    __table_args__ = (UniqueConstraint('project_id', 'sequence'),)


class ProductEvent(Base):
    __tablename__ = 'product_events'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('research_projects.id'), index=True)
    action: Mapped[str] = mapped_column(String(60))
    revision: Mapped[int] = mapped_column(Integer)
    actor: Mapped[str] = mapped_column(String(100), default='本机操作者')
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[str] = mapped_column(String, default=now)


class ProjectValidation(Base):
    __tablename__ = 'project_validations'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('research_projects.id'), index=True)
    criterion_id: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(180))
    success_criteria: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default='planned')
    outcome: Mapped[str] = mapped_column(String(30), default='pending')
    observation: Mapped[str] = mapped_column(Text, default='')
    created: Mapped[str] = mapped_column(String, default=now)
    updated: Mapped[str] = mapped_column(String, default=now)


class ProjectCandidate(Base):
    """Discovery shortlist; it never changes reviewed decision evidence."""
    __tablename__ = 'project_candidates'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('research_projects.id'), index=True)
    paper_id: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(Text)
    paper_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default='pending')
    reason: Mapped[str] = mapped_column(Text, default='')
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created: Mapped[str] = mapped_column(String, default=now)
    updated: Mapped[str] = mapped_column(String, default=now)
    __table_args__ = (UniqueConstraint('project_id', 'paper_id'),)


class ProjectTrendLead(Base):
    """A frozen discovery provenance record, never reviewed project evidence."""
    __tablename__ = 'project_trend_leads'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('research_projects.id'), index=True)
    source_key: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default='pending')
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created: Mapped[str] = mapped_column(String, default=now)
    updated: Mapped[str] = mapped_column(String, default=now)
    candidate_ids: Mapped[list] = mapped_column(JSON, default=list)
    __table_args__ = (UniqueConstraint('project_id', 'source_key'),)


class ProjectPaperIntake(Base):
    __tablename__ = 'project_paper_intakes'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('research_projects.id'), index=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey('project_trend_leads.id'), index=True)
    paper_id: Mapped[str] = mapped_column(String(200))
    domain_id: Mapped[str] = mapped_column(String(200))
    source_key: Mapped[str] = mapped_column(String(64))
    judgment_snapshot: Mapped[dict] = mapped_column(JSON)
    metadata_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    pdf_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pdf_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pdf_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    download_job_id: Mapped[str] = mapped_column(String(100), index=True)
    analysis_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    analysis_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    candidate_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    analysis_target: Mapped[dict] = mapped_column(JSON, default=dict)
    analysis_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default='queued')
    analysis_status: Mapped[str] = mapped_column(String(30), default='not_requested')
    analysis_blocker: Mapped[str] = mapped_column(Text, default='')
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created: Mapped[str] = mapped_column(String, default=now)
    updated: Mapped[str] = mapped_column(String, default=now)
    __table_args__ = (UniqueConstraint('project_id', 'lead_id', 'paper_id', 'domain_id'),)
