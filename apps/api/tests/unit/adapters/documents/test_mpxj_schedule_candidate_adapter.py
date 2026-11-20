"""I-01: MPXJ schedule candidates remain immutable and non-authoritative.

These tests do not start JVM, touch private project files, or write to DB.
"""
from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from uuid import UUID

from src.documents.adapters.parsers.mpxj_schedule_candidate_adapter import (
    ScheduleCandidateError,
    ScheduleSourceScope,
    parse_verified_mpxj_candidates,
)


SCOPE = ScheduleSourceScope(
    tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
    project_id=UUID("22222222-2222-2222-2222-222222222222"),
    document_id=UUID("33333333-3333-3333-3333-333333333333"),
    revision_id=UUID("44444444-4444-4444-4444-444444444444"),
)


class FakeRelation:
    def __init__(self, predecessor):
        self.predecessor = predecessor

    def getPredecessorTask(self):
        return self.predecessor


class FakeTask:
    def __init__(self, uid, name, start=None, finish=None, predecessors=(), milestone=False):
        self.uid, self.name = uid, name
        self.start, self.finish = start, finish
        self.predecessors = predecessors
        self.milestone = milestone

    def getUniqueID(self):
        return self.uid

    def getName(self):
        return self.name

    def getStart(self):
        return self.start

    def getFinish(self):
        return self.finish

    def getPredecessors(self):
        return [FakeRelation(t) for t in self.predecessors]

    def getDuration(self):
        return "5 days"

    def getWBS(self):
        return "1.2"

    def getMilestone(self):
        return self.milestone


class FakeProject:
    def __init__(self, tasks):
        self.tasks = tasks

    def getTasks(self):
        return self.tasks

    def getCalendars(self):
        return ["Standard"]

    def getResources(self):
        return []


def run(candidate_reader, source_bytes=b"synthetic-schedule", suffix=".mpp", expected_sha=None):
    return parse_verified_mpxj_candidates(
        source_bytes=source_bytes,
        expected_sha256=expected_sha or hashlib.sha256(source_bytes).hexdigest(),
        file_extension=suffix,
        scope=SCOPE,
        reader=candidate_reader,
    )


class MpxjCandidateAdapterTests(unittest.TestCase):
    def test_verified_file_scope_and_source_locators(self):
        first = FakeTask("501", "Foundation", "2026-11-01T08:00", "2026-11-04T17:00")
        second = FakeTask("502", "Installation", "2026-11-05T08:00", "2026-11-10T17:00", (first,))
        result = run(lambda p: FakeProject([first, second]))
        self.assertEqual(result["scope"]["tenant_id"], str(SCOPE.tenant_id))
        self.assertEqual(result["source"]["format"], ".mpp")
        self.assertEqual(result["activities"][0]["source_locator"], "MPXJ:task_uid:501")
        self.assertEqual(result["activities"][1]["predecessor_source_ids"], ["501"])
        self.assertEqual(result["coverage"]["candidate_activities"], 2)
        self.assertEqual(result["coverage"]["candidate_predecessor_links"], 1)
        self.assertEqual(result["time_assessment"], "NOT_ASSESSED")
        self.assertFalse(result["effects_allowed"])
        self.assertEqual(result["trusted_promotions"], 0)
        self.assertTrue(all(x["wbs_node_id"] is None for x in result["activities"]))
        self.assertTrue(all(x["date_state"] == "NOT_ASSESSED" for x in result["activities"]))

    def test_sha_mismatch_fails_before_reader_is_invoked(self):
        seen = []
        def reader(path):
            seen.append(path)
            raise AssertionError("reader was invoked")
        with self.assertRaisesRegex(ScheduleCandidateError, "SHA256 mismatch"):
            run(reader, expected_sha="0" * 64)
        self.assertEqual(seen, [])

    def test_rejects_unknown_extension(self):
        with self.assertRaisesRegex(ScheduleCandidateError, "unsupported"):
            run(lambda _: FakeProject([]), suffix=".pdf")

    def test_rejects_bad_scope(self):
        with self.assertRaisesRegex(ScheduleCandidateError, "scope"):
            parse_verified_mpxj_candidates(
                source_bytes=b"x", expected_sha256=hashlib.sha256(b"x").hexdigest(),
                file_extension=".xer", scope=None, reader=lambda _: FakeProject([]),
            )

    def test_rejects_duplicate_native_unique_ids(self):
        a, b = FakeTask("1", "A"), FakeTask("1", "B")
        with self.assertRaisesRegex(ScheduleCandidateError, "duplicate"):
            run(lambda _: FakeProject([a, b]))

    def test_rejects_missing_id_and_unlinked_predecessor(self):
        with self.assertRaisesRegex(ScheduleCandidateError, "no native unique"):
            run(lambda _: FakeProject([FakeTask(None, "A")]))
        unknown = FakeTask(None, "missing predecessor")
        with self.assertRaisesRegex(ScheduleCandidateError, "predecessor.*lacks"):
            run(lambda _: FakeProject([FakeTask("1", "A", predecessors=(unknown,))]))

    def test_missing_dates_are_explicitly_unassessed(self):
        result = run(lambda _: FakeProject([FakeTask("1", "No dates")]))
        self.assertEqual(result["coverage"]["activities_with_missing_source_dates"], 1)
        self.assertIsNone(result["activities"][0]["start_source_local"])
        self.assertEqual(result["activities"][0]["date_state"], "NOT_ASSESSED")

    def test_rejects_empty_and_oversized_sources(self):
        with self.assertRaisesRegex(ScheduleCandidateError, "nonempty"):
            parse_verified_mpxj_candidates(
                source_bytes=b"", expected_sha256="0"*64,
                file_extension=".xer", scope=SCOPE, reader=lambda _: FakeProject([]),
            )
        # Do not allocate a 24 MiB+ buffer in unit tests: patch the module
        # constant through unittest.mock to prove the size guard.
        from unittest.mock import patch
        with patch(
            "src.documents.adapters.parsers.mpxj_schedule_candidate_adapter.MAX_FILE_BYTES", 1
        ):
            with self.assertRaisesRegex(ScheduleCandidateError, "size limit"):
                run(lambda _: FakeProject([]))

    def test_temp_source_is_removed_after_reader(self):
        files = []
        def reader(path):
            files.append(path)
            self.assertTrue(path.exists())
            self.assertEqual(path.read_bytes(), b"synthetic-schedule")
            return FakeProject([FakeTask("2", "Ready")])
        run(reader)
        self.assertFalse(files[0].exists())

    def test_absence_of_activities_fails_closed(self):
        with self.assertRaisesRegex(ScheduleCandidateError, "no named activities"):
            run(lambda _: FakeProject([]))


if __name__ == "__main__":
    unittest.main()
