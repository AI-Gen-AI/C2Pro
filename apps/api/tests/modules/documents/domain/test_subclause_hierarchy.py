"""
TS-UD-DOC-CLS-003: SubClause Hierarchy tests.
"""

from uuid import UUID, uuid4

import pytest

from src.documents.domain.entities.subclause import SubClause


class TestSubClauseHierarchy:
    """Refers to Suite ID: TS-UD-DOC-CLS-003"""

    def test_001_subclause_creation_root_level(self):
        clause_id = uuid4()
        sub = SubClause.create(clause_id=clause_id, code="1")
        assert isinstance(sub.id, UUID)
        assert sub.clause_id == clause_id
        assert sub.code == "1"
        assert sub.level == 1
        assert sub.parent_id is None

    def test_002_subclause_creation_nested_level(self):
        clause_id = uuid4()
        sub = SubClause.create(clause_id=clause_id, code="1.2.3")
        assert sub.level == 3

    def test_003_subclause_letter_suffix_level(self):
        clause_id = uuid4()
        sub = SubClause.create(clause_id=clause_id, code="1.2.a")
        assert sub.code == "1.2.a"
        assert sub.level == 3

    @pytest.mark.parametrize("invalid_code", ["A.1", "1..2", "1.2..3", ""])
    def test_004_subclause_invalid_code_rejected(self, invalid_code):
        with pytest.raises(ValueError, match="Invalid subclause code"):
            SubClause.create(clause_id=uuid4(), code=invalid_code)

    def test_005_root_with_parent_rejected(self):
        with pytest.raises(ValueError, match="Root subclause cannot have a parent"):
            SubClause.create(clause_id=uuid4(), code="1", parent_id=uuid4())

    def test_006_child_requires_parent_prefix(self):
        clause_id = uuid4()
        parent = SubClause.create(clause_id=clause_id, code="1.2")
        child = SubClause.create(clause_id=clause_id, code="1.3.1")
        assert child.can_be_child_of(parent) is False

    def test_007_parent_reference_valid(self):
        clause_id = uuid4()
        parent = SubClause.create(clause_id=clause_id, code="1.2")
        child = SubClause.create(clause_id=clause_id, code="1.2.1")
        assert child.can_be_child_of(parent) is True

    def test_008_parent_reference_clause_mismatch(self):
        parent = SubClause.create(clause_id=uuid4(), code="1.2")
        child = SubClause.create(clause_id=uuid4(), code="1.2.1")
        assert child.can_be_child_of(parent) is False

    def test_009_parent_reference_level_mismatch(self):
        clause_id = uuid4()
        parent = SubClause.create(clause_id=clause_id, code="1.2")
        child = SubClause.create(clause_id=clause_id, code="1.2.1.1")
        assert child.can_be_child_of(parent) is False

    def test_010_validate_parent_raises_on_invalid(self):
        clause_id = uuid4()
        parent = SubClause.create(clause_id=clause_id, code="1.2")
        child = SubClause.create(clause_id=clause_id, code="1.3.1")
        with pytest.raises(ValueError, match="Invalid parent reference"):
            child.validate_parent(parent)
