"""
WBS hierarchy and code helper rules.

Test Suite: TS-UD-WBS-002
Phase: REFACTOR (Triangulation complete)

This module provides deterministic helpers for WBS (Work Breakdown Structure)
hierarchy and code operations, including validation, generation, and tree traversal.

Example:
    >>> WBSHierarchy.validate_code("1.2.3")
    True
    >>> WBSHierarchy.parent_code("1.2.3")
    "1.2"
    >>> WBSHierarchy.next_child_code("1", ["1.1", "1.2"])
    "1.3"
"""

from __future__ import annotations

import re
from typing import Final


class WBSCodeError(ValueError):
    """Base exception for WBS code validation errors."""
    pass


class InvalidWBSCodeError(WBSCodeError):
    """Raised when a WBS code has invalid format."""
    
    def __init__(self, code: str) -> None:
        super().__init__(f"Invalid WBS code format: '{code}'. Expected format: '1', '1.2', '1.2.3'")
        self.code = code


class MissingParentCodeError(WBSCodeError):
    """Raised when a child code references a non-existent parent."""
    
    def __init__(self, child_code: str, parent_code: str) -> None:
        super().__init__(f"Missing parent code '{parent_code}' for child '{child_code}'")
        self.child_code = child_code
        self.parent_code = parent_code


class WBSHierarchy:
    """
    Deterministic helpers for WBS hierarchy and code operations.
    
    This class provides static methods for:
    - Code validation
    - Parent/child relationships
    - Code generation
    - Tree traversal and sorting
    
    All methods are pure functions with no side effects.
    """

    # Compiled regex pattern for WBS code validation
    # Matches: "1", "1.2", "1.2.3", etc.
    _CODE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\d+(\.\d+)*$")
    
    # Maximum depth for WBS hierarchy
    MAX_DEPTH: Final[int] = 10
    
    # Maximum code segment value
    MAX_SEGMENT_VALUE: Final[int] = 9999

    @classmethod
    def validate_code(cls, code: str, *, max_depth: int | None = None) -> bool:
        """
        Validate a WBS code format.
        
        Valid codes consist of numeric segments separated by dots:
        - "1" - Root level
        - "1.2" - Second level
        - "1.2.3" - Third level
        
        Args:
            code: The WBS code to validate
            max_depth: Optional maximum depth (defaults to MAX_DEPTH)
            
        Returns:
            True if code is valid, False otherwise
            
        Examples:
            >>> WBSHierarchy.validate_code("1")
            True
            >>> WBSHierarchy.validate_code("1.2.3")
            True
            >>> WBSHierarchy.validate_code("A.1")
            False
            >>> WBSHierarchy.validate_code("1.2", max_depth=1)
            False
        """
        if not code or not isinstance(code, str):
            return False
            
        if not cls._CODE_PATTERN.match(code):
            return False
            
        # Check depth if specified
        depth = code.count(".") + 1
        max_allowed = max_depth if max_depth is not None else cls.MAX_DEPTH
        if depth > max_allowed:
            return False
            
        # Check segment values
        for segment in code.split("."):
            # Prevent leading zeros (except "0" itself)
            if len(segment) > 1 and segment[0] == "0":
                return False
            # Check max segment value
            if int(segment) > cls.MAX_SEGMENT_VALUE:
                return False
                
        return True

    @classmethod
    def next_child_code(
        cls, 
        parent_code: str, 
        existing_codes: list[str],
        *,
        validate_parent: bool = True
    ) -> str:
        """
        Generate the next child code for a parent.
        
        Finds the highest existing sibling code and increments by 1.
        Handles gaps in numbering (e.g., ["1.1", "1.3"] → "1.4").
        
        Args:
            parent_code: The parent WBS code
            existing_codes: List of existing codes in the hierarchy
            validate_parent: Whether to validate the parent code (default: True)
            
        Returns:
            The next available child code
            
        Raises:
            InvalidWBSCodeError: If parent_code is invalid and validate_parent is True
            
        Examples:
            >>> WBSHierarchy.next_child_code("1", [])
            "1.1"
            >>> WBSHierarchy.next_child_code("1", ["1.1", "1.2"])
            "1.3"
            >>> WBSHierarchy.next_child_code("1", ["1.1", "1.3"])
            "1.4"
        """
        if validate_parent and not cls.validate_code(parent_code):
            raise InvalidWBSCodeError(parent_code)
            
        prefix = f"{parent_code}."
        max_suffix = 0
        
        for code in existing_codes:
            if not code.startswith(prefix):
                continue
                
            # Extract suffix after prefix
            suffix = code[len(prefix):]
            
            # Only consider direct children (not grandchildren)
            if "." in suffix:
                continue
                
            # Validate suffix is numeric
            if suffix.isdigit():
                max_suffix = max(max_suffix, int(suffix))
                
        next_suffix = max_suffix + 1
        return f"{parent_code}.{next_suffix}"

    @staticmethod
    def parent_code(code: str) -> str | None:
        """
        Extract the parent code from a child code.
        
        Args:
            code: The WBS code
            
        Returns:
            The parent code, or None if this is a root code
            
        Examples:
            >>> WBSHierarchy.parent_code("1.2.3")
            "1.2"
            >>> WBSHierarchy.parent_code("1")
            None
        """
        if "." not in code:
            return None
        return code.rsplit(".", 1)[0]

    @staticmethod
    def is_descendant(parent_code: str, candidate_code: str) -> bool:
        """
        Check if candidate_code is a descendant of parent_code.
        
        A descendant is a direct or indirect child. This method correctly
        handles the "prefix trap" (e.g., "1.1" is NOT a descendant of "1.10").
        
        Args:
            parent_code: The potential ancestor code
            candidate_code: The code to check
            
        Returns:
            True if candidate_code is a descendant of parent_code
            
        Examples:
            >>> WBSHierarchy.is_descendant("1", "1.1")
            True
            >>> WBSHierarchy.is_descendant("1", "1.2.3")
            True
            >>> WBSHierarchy.is_descendant("1.1", "1.10")  # Prefix trap
            False
            >>> WBSHierarchy.is_descendant("1", "2.1")
            False
        """
        separator = f"{parent_code}."
        return (
            candidate_code.startswith(separator) 
            and candidate_code != parent_code
        )

    @staticmethod
    def get_ancestors(code: str) -> list[str]:
        """
        Get all ancestor codes from root to immediate parent.
        
        Args:
            code: The WBS code
            
        Returns:
            List of ancestor codes in order from root to parent
            
        Examples:
            >>> WBSHierarchy.get_ancestors("1.2.3")
            ["1", "1.2"]
            >>> WBSHierarchy.get_ancestors("1")
            []
        """
        if "." not in code:
            return []
            
        parts = code.split(".")
        ancestors = []
        
        for i in range(1, len(parts)):
            ancestor = ".".join(parts[:i])
            ancestors.append(ancestor)
            
        return ancestors

    @staticmethod
    def get_depth(code: str) -> int:
        """
        Get the depth level of a WBS code.
        
        Root codes (e.g., "1") have depth 1.
        
        Args:
            code: The WBS code
            
        Returns:
            The depth level (1-based)
            
        Examples:
            >>> WBSHierarchy.get_depth("1")
            1
            >>> WBSHierarchy.get_depth("1.2.3")
            3
        """
        return code.count(".") + 1

    @staticmethod
    def sort_codes(codes: list[str]) -> list[str]:
        """
        Sort WBS codes numerically by segments.
        
        Unlike alphabetical sorting, this correctly orders:
        "1.1", "1.2", "1.10" (not "1.1", "1.10", "1.2")
        
        Args:
            codes: List of WBS codes to sort
            
        Returns:
            Sorted list of codes
            
        Examples:
            >>> WBSHierarchy.sort_codes(["1.10", "1.2", "1.1"])
            ["1.1", "1.2", "1.10"]
        """
        def key_func(code: str) -> tuple[int, ...]:
            return tuple(int(part) for part in code.split("."))

        return sorted(codes, key=key_func)

    @classmethod
    def validate_hierarchy_codes(
        cls, 
        codes: list[str],
        *,
        strict: bool = True
    ) -> None:
        """
        Validate a list of WBS codes forms a consistent hierarchy tree.
        
        Checks:
        - All codes have valid format
        - No orphan children (all parents exist)
        - No duplicates
        
        Args:
            codes: List of WBS codes to validate
            strict: If True, raises on validation error (default).
                   If False, returns without raising.
            
        Raises:
            InvalidWBSCodeError: If any code has invalid format
            MissingParentCodeError: If a child references non-existent parent
            
        Examples:
            >>> WBSHierarchy.validate_hierarchy_codes(["1", "1.1", "1.2"])
            # No error
            >>> WBSHierarchy.validate_hierarchy_codes(["1.1"])
            MissingParentCodeError: Missing parent code '1' for child '1.1'
        """
        if not codes:
            return
            
        sorted_codes = cls.sort_codes(codes)
        code_set = set(sorted_codes)
        
        # Check for duplicates
        if len(code_set) != len(codes):
            seen = set()
            for code in codes:
                if code in seen:
                    raise InvalidWBSCodeError(f"Duplicate code: {code}")
                seen.add(code)
        
        for code in sorted_codes:
            if not cls.validate_code(code):
                raise InvalidWBSCodeError(code)
                
            parent = cls.parent_code(code)
            if parent is not None and parent not in code_set:
                raise MissingParentCodeError(code, parent)

    @classmethod
    def get_root_codes(cls, codes: list[str]) -> list[str]:
        """
        Get all root-level codes from a list.
        
        Args:
            codes: List of WBS codes
            
        Returns:
            List of root codes (codes with no parent in the list)
            
        Examples:
            >>> WBSHierarchy.get_root_codes(["1", "1.1", "2", "2.1"])
            ["1", "2"]
        """
        code_set = set(codes)
        roots = []
        
        for code in codes:
            parent = cls.parent_code(code)
            if parent is None or parent not in code_set:
                roots.append(code)
                
        return cls.sort_codes(list(set(roots)))

    @classmethod
    def get_children(cls, parent_code: str, codes: list[str]) -> list[str]:
        """
        Get all direct children of a parent code.
        
        Args:
            parent_code: The parent WBS code
            codes: List of WBS codes to search
            
        Returns:
            List of direct child codes (sorted)
            
        Examples:
            >>> WBSHierarchy.get_children("1", ["1.1", "1.2", "1.2.1", "2.1"])
            ["1.1", "1.2"]
        """
        prefix = f"{parent_code}."
        children = []
        
        for code in codes:
            if code.startswith(prefix):
                # Only direct children (one more segment)
                suffix = code[len(prefix):]
                if "." not in suffix:
                    children.append(code)
                    
        return cls.sort_codes(children)
