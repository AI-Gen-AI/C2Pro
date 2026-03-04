"""
Domain exceptions for documents bounded context.

Refers to Suite ID: TS-UD-DOC-CLS-001.
"""


class DomainValidationError(ValueError):
    """Raised when a domain entity violates invariant rules."""

