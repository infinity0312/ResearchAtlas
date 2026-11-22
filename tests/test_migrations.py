from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, inspect, select
from sqlalchemy.exc import OperationalError

from backend.db import Base
from backend.migrations import (
    LEDGER_TABLE, MIGRATIONS, Migration, MigrationError,
    migration_status, run_migrations,
)
from scripts.atlas_backup import backup_database, main, verify_database


@pytest.fixture
def migration_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}", connect_args={"timeout": 10})
    yield engine
    engine.dispose()


def test_fresh_schema_and_repeat_startup(migration_engine):
    assert run_migrations(migration_engine, Base.metadata) == [1, 2, 3, 4, 5, 6, 7, 8]
    assert run_migrations(migration_engine, Base.metadata) == []
    assert migration_status(migration_engine) == {
        "current_version": 8, "latest_version": 8, "pending_versions": [], "compatible": True,
    }
    inspector = inspect(migration_engine)
    assert "ix_analyses_current" in {i["name"] for i in inspector.get_indexes("analyses")}
    assert "ix_jobs_queue" in {i["name"] for i in inspector.get_indexes("jobs")}


def test_legacy_schema_adds_columns_without_rewriting_records(migration_engine):
    with migration_engine.begin() as connection:
        for table, definition in (
            ("paper_conversations", "id TEXT PRIMARY KEY, question TEXT"),
            ("trend_counts", "key TEXT PRIMARY KEY, count INTEGER"),
            ("domains", "id TEXT PRIMARY KEY, name TEXT"),
            ("papers", "id TEXT PRIMARY KEY, title TEXT"),
            ("taxonomies", "domain_id TEXT, version INTEGER, PRIMARY KEY(domain_id,version)"),
        ):
            connection.exec_driver_sql(f"CREATE TABLE {table} ({definition})")
        connection.exec_driver_sql("INSERT INTO papers(id,title) VALUES ('preserved', 'Existing evidence')")
        connection.exec_driver_sql("INSERT INTO domains(id,name) VALUES ('existing', 'Existing domain')")
    assert run_migrations(migration_engine, Base.metadata) == [1, 2, 3, 4, 5, 6, 7, 8]
    with migration_engine.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT title, date_basis FROM papers WHERE id='preserved'"
        ).one() == ("Existing evidence", "submitted")
        assert connection.exec_driver_sql(
            "SELECT name, definitions, sync_note FROM domains WHERE id='existing'"
        ).one() == ("Existing domain", "[]", "等待首次同步")


def test_changed_manifest_fails_closed(migration_engine):
    run_migrations(migration_engine, Base.metadata)
    with migration_engine.begin() as connection:
        connection.exec_driver_sql("UPDATE schema_migrations SET checksum='tampered' WHERE version=1")
    with pytest.raises(MigrationError, match="checksum"):
        run_migrations(migration_engine, Base.metadata)


def test_newer_database_is_rejected_before_creating_application_tables(migration_engine):
    run_migrations(migration_engine, Base.metadata)
    with migration_engine.begin() as connection:
        connection.exec_driver_sql("UPDATE schema_migrations SET version=9 WHERE version=8")
    metadata = MetaData()
    Table("must_not_be_created", metadata, Column("id", Integer, primary_key=True))
    with pytest.raises(MigrationError, match="newer"):
        run_migrations(migration_engine, metadata)
    assert not inspect(migration_engine).has_table("must_not_be_created")


def test_migration_ddl_and_history_roll_back_together(migration_engine):
    run_migrations(migration_engine, Base.metadata)
    broken = Migration(9, "broken", statements=(
        "CREATE TABLE should_rollback (id INTEGER)",
        "INSERT INTO table_that_does_not_exist VALUES (1)",
    ))
    with pytest.raises(OperationalError):
        run_migrations(migration_engine, Base.metadata, (*MIGRATIONS, broken))
    assert not inspect(migration_engine).has_table("should_rollback")
    assert migration_status(migration_engine)["current_version"] == 8


def test_missing_history_and_schema_drift_are_detected(migration_engine):
    run_migrations(migration_engine, Base.metadata)
    with migration_engine.begin() as connection:
        connection.exec_driver_sql("DROP INDEX ix_jobs_queue")
    with pytest.raises(MigrationError, match="missing index"):
        migration_status(migration_engine)
    with migration_engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM schema_migrations WHERE version=1")
    with pytest.raises(MigrationError, match="incomplete"):
        run_migrations(migration_engine, Base.metadata)


def test_metadata_reset_also_resets_migration_history(migration_engine):
    run_migrations(migration_engine, Base.metadata)
    Base.metadata.drop_all(migration_engine)
    assert not inspect(migration_engine).has_table(LEDGER_TABLE)
    assert run_migrations(migration_engine, Base.metadata) == [1, 2, 3, 4, 5, 6, 7, 8]


def test_competing_startups_serialize_migrations(migration_engine):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run_migrations(migration_engine, Base.metadata), range(2)))
    assert sorted(results, key=len) == [[], [1, 2, 3, 4, 5, 6, 7, 8]]
    assert migration_status(migration_engine)["current_version"] == 8


def test_model_usage_ledger_is_versioned_and_missing_columns_fail_closed(migration_engine):
    run_migrations(migration_engine, Base.metadata)
    with migration_engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE model_usage DROP COLUMN input_allowance")
    with pytest.raises(MigrationError, match='model_usage.input_allowance'):
        run_migrations(migration_engine, Base.metadata)


def test_legacy_v3_upgrade_adds_product_tables_without_rewriting_research(migration_engine):
    product_tables = {table for m in MIGRATIONS[3:] for table, _ in m.required_columns}
    assert len(product_tables) == 9
    legacy = MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name not in product_tables:
            table.to_metadata(legacy)
    assert run_migrations(migration_engine, legacy, MIGRATIONS[:3]) == [1, 2, 3]
    with migration_engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO settings(key,value) VALUES ('preserved-product-upgrade', '{\"source\":\"old-evidence\"}')")
    assert not any(inspect(migration_engine).has_table(name) for name in product_tables)
    assert run_migrations(migration_engine, Base.metadata) == [4, 5, 6, 7, 8]
    with migration_engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT value FROM settings WHERE key='preserved-product-upgrade'").scalar() == '{"source":"old-evidence"}'
    assert all(inspect(migration_engine).has_table(name) for name in product_tables)
    assert run_migrations(migration_engine, Base.metadata) == []


@pytest.mark.parametrize('table', ['research_projects', 'project_validations', 'project_candidates', 'project_trend_leads', 'project_paper_intakes'])
def test_applied_product_migration_missing_table_fails_closed(migration_engine, table):
    run_migrations(migration_engine, Base.metadata)
    with migration_engine.begin() as connection:
        connection.exec_driver_sql(f'DROP TABLE "{table}"')
    with pytest.raises(MigrationError, match='missing'):
        run_migrations(migration_engine, Base.metadata)
    assert not inspect(migration_engine).has_table(table)


def legacy_with_validation():
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name not in ('project_candidates', 'project_trend_leads', 'project_paper_intakes'):
            table.to_metadata(metadata)
    return metadata


def test_v4_to_v5_preserves_existing_project_revision(migration_engine):
    from backend.product.models import ResearchProject
    legacy = MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name not in ('project_validations', 'project_candidates', 'project_trend_leads', 'project_paper_intakes'):
            table.to_metadata(legacy)
    assert run_migrations(migration_engine, legacy, MIGRATIONS[:4]) == [1, 2, 3, 4]
    with migration_engine.begin() as connection:
        connection.execute(ResearchProject.__table__.insert().values(id='existing-project', title='Existing project',
            scenario='route_review', question='Existing decision question', criteria=[{'id': 'cost', 'label': 'Cost'}],
            recommendation='Existing recommendation', revision=7, status='reviewed'))
    assert run_migrations(migration_engine, legacy_with_validation(), MIGRATIONS[:5]) == [5]
    with migration_engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT revision,status,recommendation FROM research_projects WHERE id='existing-project'").one() == (7, 'reviewed', 'Existing recommendation')
    assert inspect(migration_engine).has_table('project_validations')


def metadata_through_v6():
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name not in ('project_trend_leads', 'project_paper_intakes'):
            table.to_metadata(metadata)
    return metadata


def test_v5_to_v6_adds_shortlist_without_rewriting_project(migration_engine):
    from backend.product.models import ResearchProject
    assert run_migrations(migration_engine, legacy_with_validation(), MIGRATIONS[:5]) == [1, 2, 3, 4, 5]
    with migration_engine.begin() as connection:
        connection.execute(ResearchProject.__table__.insert().values(
            id='shortlist-upgrade', title='Preserve scientific decision', scenario='route_review',
            question='Existing project question', criteria=[{'id': 'cost', 'label': 'Cost'}],
            recommendation='Existing reviewed recommendation', revision=9, status='reviewed'))
    assert not inspect(migration_engine).has_table('project_candidates')
    assert run_migrations(migration_engine, metadata_through_v6(), MIGRATIONS[:6]) == [6]
    with migration_engine.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT revision,status,recommendation FROM research_projects WHERE id='shortlist-upgrade'"
        ).one() == (9, 'reviewed', 'Existing reviewed recommendation')
        assert connection.exec_driver_sql('SELECT COUNT(*) FROM project_candidates').scalar() == 0
    assert 'ix_project_candidates_project_id' in {
        index['name'] for index in inspect(migration_engine).get_indexes('project_candidates')}
    assert run_migrations(migration_engine, metadata_through_v6(), MIGRATIONS[:6]) == []


def metadata_through_v7():
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name != 'project_paper_intakes':
            table.to_metadata(metadata)
    return metadata


def test_v6_to_v7_adds_trend_snapshots_without_rewriting_decisions_or_candidates(migration_engine):
    from backend.product.models import ResearchProject, ProjectCandidate
    assert run_migrations(migration_engine, metadata_through_v6(), MIGRATIONS[:6]) == [1, 2, 3, 4, 5, 6]
    with migration_engine.begin() as connection:
        connection.execute(ResearchProject.__table__.insert().values(
            id='trend-upgrade', title='Existing decision', scenario='route_review',
            question='Existing decision question', criteria=[{'id': 'cost', 'label': 'Cost'}],
            recommendation='Existing reviewed recommendation', revision=11, status='reviewed'))
        connection.execute(ProjectCandidate.__table__.insert().values(
            id='preserved-candidate', project_id='trend-upgrade', paper_id='historical-paper',
            title='Existing shortlist item', paper_version=2, status='excluded',
            reason='Existing exclusion reason', revision=3))
    assert not inspect(migration_engine).has_table('project_trend_leads')
    assert run_migrations(migration_engine, metadata_through_v7(), MIGRATIONS[:7]) == [7]
    with migration_engine.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT revision,status,recommendation FROM research_projects WHERE id='trend-upgrade'"
        ).one() == (11, 'reviewed', 'Existing reviewed recommendation')
        assert connection.exec_driver_sql(
            "SELECT revision,status,reason,paper_version FROM project_candidates WHERE id='preserved-candidate'"
        ).one() == (3, 'excluded', 'Existing exclusion reason', 2)
        assert connection.exec_driver_sql('SELECT COUNT(*) FROM project_trend_leads').scalar() == 0
    assert run_migrations(migration_engine, metadata_through_v7(), MIGRATIONS[:7]) == []


def test_v7_to_v8_adds_intakes_without_rewriting_frozen_trend_sources(migration_engine):
    from backend.product.models import ResearchProject, ProjectTrendLead
    assert run_migrations(migration_engine, metadata_through_v7(), MIGRATIONS[:7]) == [1, 2, 3, 4, 5, 6, 7]
    frozen = {'scope': {'start': '2001', 'end': '2002', 'interval': 'year', 'period': '2002'},
              'papers': [{'id': '9999.00001', 'local_version': None, 'quote': 'Original recorded quotation'}]}
    with migration_engine.begin() as connection:
        connection.execute(ResearchProject.__table__.insert().values(
            id='intake-upgrade', title='Existing decision', scenario='change_review',
            question='Existing decision question', criteria=[{'id': 'impact', 'label': 'Impact'}],
            recommendation='Existing recommendation', revision=12, status='reviewed'))
        connection.execute(ProjectTrendLead.__table__.insert().values(
            id='frozen-lead', project_id='intake-upgrade', source_key='a' * 64,
            snapshot=frozen, reason='Original attention reason', status='kept', revision=4))
    assert not inspect(migration_engine).has_table('project_paper_intakes')
    assert run_migrations(migration_engine, Base.metadata) == [8]
    with migration_engine.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT revision,status FROM research_projects WHERE id='intake-upgrade'"
        ).one() == (12, 'reviewed')
        row = connection.execute(select(ProjectTrendLead.__table__).where(
            ProjectTrendLead.__table__.c.id == 'frozen-lead')).mappings().one()
        assert row['snapshot'] == frozen
        assert (row['reason'], row['status'], row['revision']) == ('Original attention reason', 'kept', 4)
        assert connection.exec_driver_sql('SELECT COUNT(*) FROM project_paper_intakes').scalar() == 0
    assert run_migrations(migration_engine, Base.metadata) == []


def test_backup_includes_committed_wal_and_excludes_uncommitted_data(tmp_path):
    source = tmp_path / "source.db"
    output = tmp_path / "snapshot.db"
    writer = sqlite3.connect(source)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("CREATE TABLE facts (id INTEGER PRIMARY KEY, text TEXT)")
        writer.execute("INSERT INTO facts(text) VALUES ('committed in WAL')")
        writer.commit()
        assert source.with_name(source.name + "-wal").exists()
        writer.execute("INSERT INTO facts(text) VALUES ('not committed')")
        result = backup_database(source, output)
        assert result["integrity"] == "ok" and result["scope"] == "database_only"
        assert not output.with_name(output.name + "-wal").exists()
        with sqlite3.connect(output) as restored:
            assert restored.execute("SELECT text FROM facts").fetchall() == [("committed in WAL",)]
        assert writer.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 2
    finally:
        writer.close()


def test_backup_refuses_overwrite_and_preserves_configuration(tmp_path, capsys):
    source = tmp_path / "source.db"
    output = tmp_path / "snapshot.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE settings (key TEXT, value TEXT)")
        connection.execute("INSERT INTO settings VALUES ('llm', 'private-test-key')")
    assert main(["--database", str(source), "--output", str(output)]) == 0
    assert "private-test-key" not in capsys.readouterr().out
    with sqlite3.connect(output) as restored:
        assert restored.execute("SELECT value FROM settings").fetchone()[0] == "private-test-key"
    previous_bytes = output.read_bytes()
    with pytest.raises(FileExistsError):
        backup_database(source, output)
    assert output.read_bytes() == previous_bytes
    assert verify_database(output)["integrity"] == "ok"


def test_backup_never_creates_missing_source_and_cleans_failed_output(tmp_path):
    source = tmp_path / "missing.db"
    output = tmp_path / "snapshot.db"
    with pytest.raises(FileNotFoundError):
        backup_database(source, output)
    assert not source.exists() and not output.exists()
    source.write_bytes(b"not a SQLite database")
    with pytest.raises(sqlite3.DatabaseError):
        backup_database(source, output)
    assert source.read_bytes() == b"not a SQLite database"
    assert not output.exists()


def test_backup_refuses_existing_destination_sidecar(tmp_path):
    source = tmp_path / "source.db"
    output = tmp_path / "snapshot.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE facts (id INTEGER)")
    sidecar = output.with_name(output.name + "-wal")
    sidecar.write_bytes(b"preserve this existing sidecar")
    with pytest.raises(FileExistsError, match="sidecar"):
        backup_database(source, output)
    assert sidecar.read_bytes() == b"preserve this existing sidecar"
    assert not output.exists()


def test_offline_verify_does_not_change_schema_or_snapshot_bytes(tmp_path):
    snapshot = tmp_path / "snapshot.db"
    with sqlite3.connect(snapshot) as connection:
        connection.execute("CREATE TABLE legacy (id INTEGER)")
        connection.execute("INSERT INTO legacy VALUES (1)")
    before = snapshot.read_bytes()
    assert verify_database(snapshot)["schema_version"] == 0
    assert snapshot.read_bytes() == before
    with sqlite3.connect(snapshot) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall() == [("legacy",)]
