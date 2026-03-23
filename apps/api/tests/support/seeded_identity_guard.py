"""TS-OPS-SEED-ISO-001

Helpers that prevent deterministic seeded identities from targeting shared runtime databases.
"""

from __future__ import annotations

from urllib.parse import urlparse


def assert_seeded_identity_isolation_safe(database_url: str) -> None:
    database_name = urlparse(database_url).path.rsplit("/", 1)[-1].lower().strip()
    if not any(marker in database_name for marker in ("test", "pytest", "spec")):
        raise RuntimeError(
            "Seeded auth identities may only run against test databases; "
            f"refusing database '{database_name}'."
        )
