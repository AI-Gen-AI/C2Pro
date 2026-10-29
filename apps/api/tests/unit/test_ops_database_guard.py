"""The pure guard can also be run with unittest without loading pytest plugins."""
import importlib.util
import unittest
from pathlib import Path
from urllib.parse import urlencode

SOURCE = Path(__file__).resolve().parents[1] / "support/test_database_guard.py"
spec = importlib.util.spec_from_file_location("ops_database_guard", SOURCE)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class OpsDatabaseGuardTests(unittest.TestCase):
    job = "a" * 24
    dsn = ("postgresql://aigenadmin@/c2pro_ops_" + "a" * 16 + "?" + urlencode({
        "host": "/srv/c2pro/ops-c2pro-runner/jobs/" + "a" * 24 + "/pg-socket", "port": "55432"
    }))

    def test_owned_socket_accepted(self):
        guard.assert_ops_database_binding(self.dsn, self.job)
        guard.assert_ops_database_binding(self.dsn.replace("postgresql:", "postgresql+asyncpg:"), self.job)

    def test_tcp_canonical_or_foreign_target_rejected(self):
        candidates = [
            "postgresql://aigenadmin@127.0.0.1:55432/c2pro_test",
            self.dsn.replace("c2pro_ops_" + "a" * 16, "c2pro_test"),
            self.dsn.replace("a" * 24, "b" * 24),
            self.dsn + "&host=127.0.0.1",
            self.dsn + "&service=production",
            self.dsn.replace("aigenadmin@", "aigenadmin:unexpected@"),
        ]
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                with self.assertRaises(RuntimeError):
                    guard.assert_ops_database_binding(candidate, self.job)

    def test_invalid_job_id_rejected(self):
        for job in ("", "../", "a" * 23):
            with self.assertRaises(RuntimeError):
                guard.assert_ops_database_binding(self.dsn, job)

    def test_existing_non_ops_profile_preserved(self):
        guard.assert_ops_database_binding("postgresql://localhost/c2pro_test", None)

    def test_validation_root_must_match_socket_and_job(self):
        directory = "/tmp/c2pro-validation/jobs/" + self.job
        dsn = "postgresql://aigenadmin@/c2pro_ops_" + "a" * 16 + "?" + urlencode({
            "host": directory + "/pg-socket", "port": "55432"
        })
        guard.assert_ops_database_binding(dsn, self.job, directory)
        for invalid in (directory + "/extra", "relative/jobs/" + self.job,
                        "/tmp/../tmp/jobs/" + self.job, directory.replace("a" * 24, "b" * 24)):
            with self.assertRaises(RuntimeError):
                guard.assert_ops_database_binding(dsn, self.job, invalid)


if __name__ == "__main__":
    unittest.main()
