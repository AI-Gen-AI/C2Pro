"""
Shared Kernel — types shared across bounded contexts.

Contains enums, DTOs, and value objects that multiple contexts
depend on. Each owning context re-exports these for backward
compatibility, but new code should import from here.
"""
