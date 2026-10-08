"""PC-2b.3 (#922): external WBS import -- immutable source, deterministic parser, imported candidate.

IMPORTED SOURCE != DRAFT CANDIDATE != APPROVED WBS. A parsed import is input only: it creates no
DRAFT, writes no canonical WBS and never approves anything. A human explicitly turns a valid
import into a governed DRAFT through the PC-2a commands (ADR-029); the baseline still needs the
unchanged submit + human approval.
"""
