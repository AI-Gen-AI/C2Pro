"""
WBS item DTO contract for cross-module communication.

Canonical definition lives in shared_kernel.dtos; this module
re-exports for backward compatibility.

Refers to Suite ID: TS-UD-PRJ-DTO-001.
"""

from src.shared_kernel.dtos import WBSItemDTO  # noqa: F401 — re-export
