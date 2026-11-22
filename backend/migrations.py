"""Ordered, additive SQLite schema migrations with an immutable audit ledger.

The ledger is registered with application metadata so test database resets also
reset migration history. No ORM entity or application-data rewrite is required.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Sequence

from sqlalchemy import Column, Integer, MetaData, String, Table, inspect
from sqlalchemy.engine import Connection, Engine


LEDGER_TABLE = "schema_migrations"


class MigrationError(RuntimeError):
    """The database cannot safely be opened by this schema version."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    columns: tuple[tuple[str, str, str], ...] = ()
    statements: tuple[str, ...] = ()
    indexes: tuple[str, ...] = ()
    required_columns: tuple[tuple[str, str], ...] = ()

    @property
    def checksum(self) -> str:
        manifest = json.dumps(
            {"version": self.version, "name": self.name,
             "columns": self.columns, "statements": self.statements,
             "indexes": self.indexes, "required_columns": self.required_columns},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        return hashlib.sha256(manifest.encode("utf-8")).hexdigest()


# Applied manifests are immutable. Append a migration instead of editing one.
MIGRATIONS = (
    Migration(1, "adopt_legacy_additive_columns", columns=(
        ("paper_conversations", "selected_text", "TEXT NOT NULL DEFAULT ''"),
        ("paper_conversations", "selected_page", "INTEGER NOT NULL DEFAULT 0"),
        ("paper_conversations", "deleted", "BOOLEAN NOT NULL DEFAULT 0"),
        ("trend_counts", "source", "VARCHAR NOT NULL DEFAULT 'arxiv-api'"),
        ("domains", "sync_note", "TEXT NOT NULL DEFAULT '等待首次同步'"),
        ("papers", "date_basis", "VARCHAR NOT NULL DEFAULT 'submitted'"),
        ("domains", "definitions", "JSON NOT NULL DEFAULT '[]'"),
        ("taxonomies", "definitions", "JSON NOT NULL DEFAULT '[]'"),
    )),
    Migration(2, "analysis_lookup_and_job_queue_indexes", statements=(
        "CREATE INDEX IF NOT EXISTS ix_analyses_current "
        "ON analyses(paper_id, domain_id, version, taxonomy_version, id DESC)",
        "CREATE INDEX IF NOT EXISTS ix_analyses_domain_latest "
        "ON analyses(domain_id, paper_id, id DESC)",
        "CREATE INDEX IF NOT EXISTS ix_jobs_queue "
        "ON jobs(status, kind, created)",
    ), indexes=("ix_analyses_current", "ix_analyses_domain_latest", "ix_jobs_queue")),
    Migration(3, "persistent_model_usage_ledger", required_columns=tuple(
        ("model_usage", column) for column in (
            "id", "created", "settled", "day", "task_id", "job_id", "paper_id",
            "run_id", "stage", "model", "status", "reserved_tokens", "input_allowance",
            "output_limit", "prompt_tokens", "completion_tokens", "total_tokens",
        )
    )),
    Migration(4, "local_research_decision_projects", required_columns=(
        ("research_projects", "id"), ("research_projects", "revision"),
        ("research_projects", "criteria"), ("research_projects", "recommendation"),
        ("project_evidence", "project_id"), ("project_evidence", "snapshot"),
        ("project_evidence", "analysis_id"),
        ("project_reviews", "project_revision"), ("project_reviews", "evidence_fingerprint"),
        ("project_deliveries", "manifest"), ("project_deliveries", "digest"),
        ("product_events", "project_id"), ("product_events", "revision"),
    )),
    Migration(5, "project_validation_feedback", required_columns=(
        ("project_validations", "id"), ("project_validations", "project_id"),
        ("project_validations", "criterion_id"), ("project_validations", "success_criteria"),
        ("project_validations", "outcome"), ("project_validations", "observation"),
    )),
    Migration(6, "project_candidate_shortlists", required_columns=tuple(
        ("project_candidates", column) for column in (
            "id", "project_id", "paper_id", "title", "paper_version", "status",
            "reason", "revision", "created", "updated",
        )
    ), indexes=("ix_project_candidates_project_id",)),
    Migration(7, "project_trend_discovery_leads", required_columns=tuple(
        ("project_trend_leads", column) for column in (
            "id", "project_id", "source_key", "snapshot", "reason", "status",
            "revision", "created", "updated", "candidate_ids",
        )
    ), indexes=("ix_project_trend_leads_project_id",)),
    Migration(8, "project_scoped_paper_intakes", required_columns=tuple(
        ("project_paper_intakes", column) for column in (
            "id", "project_id", "lead_id", "paper_id", "domain_id", "source_key",
            "judgment_snapshot", "metadata_snapshot", "pdf_version", "pdf_sha256", "pdf_pages",
            "download_job_id", "analysis_job_id", "analysis_id", "candidate_id", "analysis_target",
            "analysis_requested", "status", "analysis_status", "analysis_blocker", "revision", "created", "updated",
        )
    ), indexes=("ix_project_paper_intakes_project_id", "ix_project_paper_intakes_download_job_id")),
)


def register_migration_table(metadata: MetaData) -> Table:
    """Include the non-ORM ledger in create_all/drop_all lifecycle operations."""
    if LEDGER_TABLE in metadata.tables:
        return metadata.tables[LEDGER_TABLE]
    return Table(
        LEDGER_TABLE, metadata,
        Column("version", Integer, primary_key=True),
        Column("name", String, nullable=False),
        Column("checksum", String(64), nullable=False),
        Column("applied_at", String, nullable=False),
    )


def _validate_manifests(migrations: Sequence[Migration]) -> None:
    if [m.version for m in migrations] != list(range(1, len(migrations) + 1)):
        raise MigrationError("Migration versions must be contiguous and ordered from 1")


def _read_applied(connection: Connection) -> list[dict]:
    if not inspect(connection).has_table(LEDGER_TABLE):
        return []
    return [dict(row) for row in connection.exec_driver_sql(
        f"SELECT version, name, checksum, applied_at FROM {LEDGER_TABLE} ORDER BY version"
    ).mappings()]


def _validate_applied(applied: list[dict], migrations: Sequence[Migration]) -> None:
    versions = [row["version"] for row in applied]
    if versions and versions[-1] > len(migrations):
        raise MigrationError(
            f"Database schema version {versions[-1]} is newer than supported "
            f"version {len(migrations)}; use a matching application release"
        )
    if versions != list(range(1, len(applied) + 1)):
        raise MigrationError("Migration history is incomplete or out of order")
    for row, migration in zip(applied, migrations):
        if row["name"] != migration.name or row["checksum"] != migration.checksum:
            raise MigrationError(f"Migration {migration.version} checksum or name mismatch")


def _validate_migration_schema(connection: Connection, migration: Migration) -> None:
    inspector = inspect(connection)
    for table, column in (*((table, column) for table, column, _ in migration.columns),
                          *migration.required_columns):
        if not inspector.has_table(table) or column not in {
            item["name"] for item in inspector.get_columns(table)
        }:
            raise MigrationError(f"Migration {migration.version} is missing {table}.{column}")
    for index in migration.indexes:
        exists = connection.exec_driver_sql(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (index,)
        ).first()
        if not exists:
            raise MigrationError(f"Migration {migration.version} is missing index {index}")


def _validate_existing_schema(connection: Connection, applied: list[dict],
                              migrations: Sequence[Migration]) -> None:
    """Reject ledger/schema drift instead of silently treating it as an upgrade."""
    for migration in migrations[:len(applied)]:
        _validate_migration_schema(connection, migration)


def run_migrations(engine: Engine, metadata: MetaData,
                   migrations: Sequence[Migration] = MIGRATIONS) -> list[int]:
    """Create current tables and apply pending migrations in one write transaction.

    BEGIN IMMEDIATE serializes competing application startups. The ledger is
    checked before application schema DDL, so an older release fails closed.
    SQLite DDL and ledger writes roll back together on any migration failure.
    """
    if engine.dialect.name != "sqlite":
        raise MigrationError("Research Atlas schema migrations require SQLite")
    _validate_manifests(migrations)
    register_migration_table(metadata)
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            applied = _read_applied(connection)
            _validate_applied(applied, migrations)
            _validate_existing_schema(connection, applied, migrations)
            metadata.create_all(connection)
            completed = []
            for migration in migrations[len(applied):]:
                for table, column, ddl in migration.columns:
                    columns = {item["name"] for item in inspect(connection).get_columns(table)}
                    if column not in columns:
                        connection.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {ddl}')
                for statement in migration.statements:
                    connection.exec_driver_sql(statement)
                _validate_migration_schema(connection, migration)
                connection.exec_driver_sql(
                    f"INSERT INTO {LEDGER_TABLE}(version, name, checksum, applied_at) VALUES (?, ?, ?, ?)",
                    (migration.version, migration.name, migration.checksum,
                     datetime.now(timezone.utc).isoformat()),
                )
                completed.append(migration.version)
            connection.commit()
            return completed
        except Exception:
            connection.rollback()
            raise


def migration_status(engine: Engine) -> dict:
    """Read-only schema health for diagnostics; does not create or upgrade tables."""
    with engine.connect() as connection:
        applied = _read_applied(connection)
        _validate_applied(applied, MIGRATIONS)
        _validate_existing_schema(connection, applied, MIGRATIONS)
    current = len(applied)
    return {"current_version": current, "latest_version": len(MIGRATIONS),
            "pending_versions": [m.version for m in MIGRATIONS[current:]],
            "compatible": True}
