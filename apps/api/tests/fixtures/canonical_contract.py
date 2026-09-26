"""The canonical R1 contract regression fixture (P0b-R1).

One pinned piece of **realistic** EPC contract prose, used as the single reference input
for the ingestion-splitter → clause-adapter → CategoryRouter boundary. Pinning it here,
rather than restating prose inside each test, is what makes "the boundary still behaves"
a regression signal instead of a property of whichever text a given test happened to use.

**Why realistic prose matters — the 6-of-6 vs 5-of-6 discrepancy.**
An earlier architecture-audit probe reported six of six categories evidenced from a single
document. That probe used the *purpose-crafted* category texts from the L4-2 router suite:
dense, lexicon-saturated one-liners written specifically to clear the prior-free
``insufficient_evidence`` threshold for one category each. Real contract prose is more
diluted. Measured on the current router, with no threshold or lexicon change:

* the crafted L4-2 QUALITY text ("Quality plan and quality control: the ITP defines
  inspection, test plan, FAT and SAT acceptance, non-conformity handling and defects
  liability under ISO 9001.") routes to ``QUALITY`` — ``has_evidence``;
* this fixture's QUALITY clause, and any comparably natural phrasing of it, does **not**
  clear the prior-free threshold.

So the two numbers come from two different fixtures, not from a behaviour change: 6/6 was
a property of crafted single-category texts, 5/6 is what realistic prose yields. Neither
number is a target. The regression test below asserts the *structural* guarantees R1 is
responsible for and deliberately does not demand 6/6, because reaching 6/6 on prose like
this would require exactly the threshold/lexicon tuning that is out of scope.
"""

from __future__ import annotations

# Seven clauses: six substantive, plus one deliberate boilerplate clause (CLAUSE 7) that
# must NOT fabricate category coverage.
CANONICAL_EPC_CONTRACT = """
CLAUSE 1 - SCOPE OF WORK. The Contractor shall perform the design, supply, installation and
commissioning of the wastewater treatment plant, including all deliverables described in the
statement of work and the work breakdown structure. Any variation of the scope requires a
written change order approved by the Employer's representative.

CLAUSE 2 - CONTRACT PRICE AND PAYMENT. The contract price is EUR 12,500,000 (twelve million
five hundred thousand euros). The Employer shall pay each certified invoice within 30 days of
receipt. The bill of quantities (BoQ) and the approved budget govern all cost and price
adjustments to the contract amount.

CLAUSE 3 - TIME FOR COMPLETION. The completion date is 2027-06-30. The Contractor shall submit
a baseline schedule showing all milestones and the critical path, and shall update it monthly.
Delay to any milestone deadline entitles the Employer to liquidated damages of 0.15% of the
contract price per day of delay.

CLAUSE 4 - QUALITY ASSURANCE. All works shall be subject to inspection, testing and acceptance
in accordance with the quality assurance plan. Non-conformities shall be recorded and the
quality control records submitted for approval before handover of the works.

CLAUSE 5 - TECHNICAL REQUIREMENTS. The technical specification requires that all equipment
comply with the applicable design standards, the material requirements and the performance
tolerances set out in the specification documents and the approved drawings.

CLAUSE 6 - LIABILITY AND TERMINATION. In the event of breach, the party in default shall
indemnify the other party. Termination for convenience, warranty obligations, the liability cap
and the governing law and dispute resolution provisions apply to this agreement.

CLAUSE 7 - NOTICES. All notices under this agreement shall be given in writing.
"""

# Pure boilerplate with no category substance. Segmented and persisted like any other
# clause, it must stay INSUFFICIENT_EVIDENCE rather than manufacture coverage.
BOILERPLATE_ONLY_CONTRACT = """
CLAUSE 1 - NOTICES. All notices under this agreement shall be given in writing and
delivered to the address stated above.

CLAUSE 2 - COUNTERPARTS. This agreement may be executed in any number of counterparts,
each of which shall be deemed an original.

CLAUSE 3 - HEADINGS. Headings are for convenience only and shall not affect the
interpretation of this agreement.
"""

__all__ = ["BOILERPLATE_ONLY_CONTRACT", "CANONICAL_EPC_CONTRACT"]
