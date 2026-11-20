"""B3 immutable-native schedule adapter smoke against real DocumentRevision model."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from src.analysis.application.extract_native_schedule_revision_candidates_use_case import (
    ExtractNativeScheduleRevisionCandidatesUseCase,
)
from src.documents.adapters.parsers.mpxj_schedule_candidate_adapter import ScheduleCandidateError
from src.documents.application.document_source import RevisionSourceError
from src.documents.domain.models import Document, DocumentStatus, DocumentType
from src.temporal.domain.document_revision import DocumentRevision
from test_b3_source_inventory_bridge import FakeProject, PROJECT, TENANT


class B3NativeRevisionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="b3-immutable-test-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/"schedule-source.bin"
        self.bytes = b"XER-SYNTHETIC-LAB-EXAMPLE"
        self.path.write_bytes(self.bytes)
        self.doc = Document(
            id=UUID(int=24), tenant_id=TENANT, project_id=PROJECT,
            document_type=DocumentType.SCHEDULE,
            filename="user-visible-schedule.xlsx",
            upload_status=DocumentStatus.UPLOADED,
        )
        now = datetime.now(UTC)
        self.revision = DocumentRevision(
            revision_id=UUID(int=25), document_id=self.doc.id,
            tenant_id=TENANT, project_id=PROJECT, rev_no=3,
            blob_hash=hashlib.sha256(self.bytes).hexdigest(),
            blob_key="immutable/schedules/source-3.xer",
            valid_from=now, created_at=now,
        )

    async def test_actual_immutable_revision_is_hashed_and_candidates_enter_b3(self):
        result = await ExtractNativeScheduleRevisionCandidatesUseCase(
            reader=lambda _: FakeProject(),
        ).execute(document=self.doc, revision=self.revision, source_path=self.path)
        self.assertEqual(result["source"]["format"], ".xer")
        self.assertEqual(result["source"]["sha256"], self.revision.blob_hash)
        self.assertEqual(result["scope"]["revision_id"], str(self.revision.revision_id))
        self.assertEqual(result["coverage"]["candidate_activities"], 1)
        self.assertFalse(result["coverage"]["wbs_node_authority_verified"])
        self.assertIsNone(result["activities"][0]["wbs_node_id"])
        self.assertFalse(result["effects_allowed"])

    async def test_wrong_hash_fail_closed_before_native_reader(self):
        self.path.write_bytes(b"file changed after revision selected")
        called = []
        with self.assertRaises(RevisionSourceError):
            await ExtractNativeScheduleRevisionCandidatesUseCase(
                reader=lambda _: called.append(True)
            ).execute(document=self.doc, revision=self.revision, source_path=self.path)
        self.assertEqual(called, [])

    async def test_type_and_scope_mismatch_rejected(self):
        with self.assertRaises(ScheduleCandidateError):
            await ExtractNativeScheduleRevisionCandidatesUseCase(
                reader=lambda _: FakeProject(),
            ).execute(document=replace(self.doc, document_type=DocumentType.BUDGET),
                      revision=self.revision,source_path=self.path)
        with self.assertRaises(ScheduleCandidateError):
            await ExtractNativeScheduleRevisionCandidatesUseCase(
                reader=lambda _: FakeProject(),
            ).execute(document=replace(self.doc, tenant_id=UUID(int=789)),
                      revision=self.revision,source_path=self.path)

    async def test_revision_extension_must_be_native_and_immutable(self):
        rev = self.revision.model_copy(update={"blob_key": "revision/final.xlsx"})
        with self.assertRaisesRegex(ScheduleCandidateError, "immutable MPP/XER"):
            await ExtractNativeScheduleRevisionCandidatesUseCase(
                reader=lambda _: FakeProject(),
            ).execute(document=self.doc, revision=rev, source_path=self.path)


if __name__ == "__main__":
    unittest.main()
