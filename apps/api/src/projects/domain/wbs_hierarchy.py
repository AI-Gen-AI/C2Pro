"""
WBS hierarchy and code helper rules.

Refers to Suite ID: TS-UD-PRJ-WBS-002.
"""

from __future__ import annotations

import re


class WBSHierarchy:
    """Deterministic helpers for WBS hierarchy and code operations."""

    _CODE_PATTERN = re.compile(r"^\d+(\.\d+)*$")

    @classmethod
    def validate_code(cls, code: str) -> bool:
        return bool(cls._CODE_PATTERN.match(code))

    @classmethod
    def next_child_code(cls, parent_code: str, existing_codes: list[str]) -> str:
        prefix = f"{parent_code}."
        siblings: list[int] = []
        for code in existing_codes:
            if not code.startswith(prefix):
                continue
            suffix = code[len(prefix) :]
            if suffix.isdigit():
                siblings.append(int(suffix))
        next_suffix = max(siblings, default=0) + 1
        return f"{parent_code}.{next_suffix}"

    @staticmethod
    def parent_code(code: str) -> str | None:
        if "." not in code:
            return None
        return code.rsplit(".", 1)[0]

    @staticmethod
    def is_descendant(parent_code: str, candidate_code: str) -> bool:
        return candidate_code.startswith(f"{parent_code}.")

    @staticmethod
    def sort_codes(codes: list[str]) -> list[str]:
        def key_func(code: str) -> tuple[int, ...]:
            return tuple(int(part) for part in code.split("."))

        return sorted(codes, key=key_func)

    @classmethod
    def validate_hierarchy_codes(cls, codes: list[str]) -> None:
        sorted_codes = cls.sort_codes(codes)
        code_set = set(sorted_codes)
        for code in sorted_codes:
            if not cls.validate_code(code):
                raise ValueError(f"Invalid WBS code: {code}")
            parent = cls.parent_code(code)
            if parent is not None and parent not in code_set:
                raise ValueError(f"Missing parent code: {parent}")
