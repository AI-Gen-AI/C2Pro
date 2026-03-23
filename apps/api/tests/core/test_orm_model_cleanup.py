"""
TS-INT-DB-CLS-001: ORM relationship cleanup coverage.
"""

from src.analysis.adapters.persistence.models import Alert, Analysis
from src.core.database import Base
from src.documents.adapters.persistence.models import ClauseORM, DocumentORM
from src.procurement.adapters.persistence.models import BOMItemORM, WBSItemORM
from src.stakeholders.adapters.persistence.models import StakeholderORM


def test_cross_module_tables_register_on_shared_metadata() -> None:
    assert "analyses" in Base.metadata.tables
    assert "alerts" in Base.metadata.tables
    assert "documents" in Base.metadata.tables
    assert "clauses" in Base.metadata.tables
    assert "stakeholders" in Base.metadata.tables
    assert "procurement_wbs_items" in Base.metadata.tables
    assert "procurement_bom_items" in Base.metadata.tables


def test_analysis_and_documents_relationships_are_restored() -> None:
    assert "alerts" in Analysis.__mapper__.relationships
    assert Analysis.__mapper__.relationships["alerts"].mapper.class_ is Alert

    assert "analysis" in Alert.__mapper__.relationships
    assert Alert.__mapper__.relationships["analysis"].mapper.class_ is Analysis

    assert "clauses" in DocumentORM.__mapper__.relationships
    assert DocumentORM.__mapper__.relationships["clauses"].mapper.class_ is ClauseORM

    assert "document" in ClauseORM.__mapper__.relationships
    assert ClauseORM.__mapper__.relationships["document"].mapper.class_ is DocumentORM


def test_reenabled_foreign_keys_reference_real_tables() -> None:
    assert str(next(iter(Analysis.__table__.c.project_id.foreign_keys)).target_fullname) == "projects.id"
    assert str(next(iter(Alert.__table__.c.project_id.foreign_keys)).target_fullname) == "projects.id"
    assert str(next(iter(Alert.__table__.c.analysis_id.foreign_keys)).target_fullname) == "analyses.id"
    assert str(next(iter(Alert.__table__.c.source_clause_id.foreign_keys)).target_fullname) == "clauses.id"
    assert str(next(iter(DocumentORM.__table__.c.project_id.foreign_keys)).target_fullname) == "projects.id"
    assert str(next(iter(ClauseORM.__table__.c.project_id.foreign_keys)).target_fullname) == "projects.id"
    assert str(next(iter(ClauseORM.__table__.c.document_id.foreign_keys)).target_fullname) == "documents.id"
    assert str(next(iter(StakeholderORM.__table__.c.project_id.foreign_keys)).target_fullname) == "projects.id"
    assert str(next(iter(StakeholderORM.__table__.c.source_clause_id.foreign_keys)).target_fullname) == "clauses.id"
    assert (
        str(next(iter(StakeholderORM.__table__.c.extracted_from_document_id.foreign_keys)).target_fullname)
        == "documents.id"
    )
    assert str(next(iter(WBSItemORM.__table__.c.project_id.foreign_keys)).target_fullname) == "projects.id"
    assert str(next(iter(BOMItemORM.__table__.c.project_id.foreign_keys)).target_fullname) == "projects.id"
