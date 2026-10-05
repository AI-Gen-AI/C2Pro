# Architecture Note: WBS Qualification, Alignment and Readiness (future contract)

**Authority:** supporting note to [ADR-029](../decisions/ADR-029-wbs-governance-identity-baseline.md). The ADR wins on any conflict.
**Status:** future product/read-model contract. **Nothing here is implemented or scheduled** by PC-1R or PC-2a; WBS intelligence is PC-2b and alignment engines come later.

## 1. WBS Reviewer / Optimizer — qualification dimensions

The Reviewer/Optimizer evaluates an existing WBS against project evidence. The WBS may be imported, a draft, or a baseline. The Reviewer/Optimizer emits **qualifications and proposals, never authority**. Dimensions:

| Dimension | Question |
|---|---|
| Contract / scope coverage | Is every contractual scope item covered by some node? |
| Missing scope | Does evidence describe scope with no node? |
| Duplicate / overlapping scope | Do two nodes claim the same scope? |
| Decomposition consistency | Are sibling branches decomposed along a consistent axis? |
| Granularity / controllability | Are work packages small enough to control and large enough to manage? |
| Interfaces | Are boundaries between packages stated (`interface_notes`, later interface links)? |
| Deliverable coverage | Does every deliverable have a node, and every package a deliverable? |
| Acceptance criteria | Do work packages define acceptance? |
| Schedule mapping coverage | Share of activities with confirmed mappings to approved nodes |
| Budget/cost mapping coverage | Share of structured cost mapped to control accounts or work packages |
| Procurement/BOM mapping coverage | Packages and BOM items with confirmed node links |
| Responsibility (RACI) coverage | Work packages with an Accountable and a Responsible role |
| Obligation coverage | Critical obligations with a governed scope link |
| Evidence / quality coverage | Deliverables with an evidence or acceptance definition |

Each finding is a structured observation carrying evidence refs, a confidence and a proposed change-set edit, which a human may accept, modify or reject.

## 2. Baseline approval → alignment analysis (trigger contract)

Applying Baseline #1 or #N+1 **may trigger** alignment engines. Their outputs are **observations, proposals, qualifications and alerts**. They are never canonical writes into Schedule, Budget, Procurement, RACI, Obligations, Risk or Evidence. Each of those domains keeps its own authority and governance.

Illustrative outputs:

- Schedule: "342/387 activities mapped to the approved WBS; 31 proposed mappings need review; 14 unmapped."
- Budget: "91% of structured cost mapped; €X unassigned."
- Procurement: "7 procurement/BOM packages have no confirmed WBS mapping."
- RACI: "12 work packages have no Accountable role."
- Contract: "3 critical obligations have no governed WBS scope link."
- Evidence: "4 deliverables have no acceptance/evidence definition."
- Risk: "2 critical packages have upcoming contractual dates and incomplete Schedule/Procurement coverage."

Trigger rules:

- Triggering is asynchronous and idempotent per `(project_id, baseline_id, engine_version)`.
- A stale result, meaning one tied to a superseded baseline, is labelled stale and is never authoritative.

## 3. WBS / Project Controls Readiness (read-model concept, no enum)

`DRAFT → STRUCTURALLY_VALID → REVIEWED → APPROVED_BASELINE → ALIGNED`

- The stages are derived from authority state, validation results and alignment coverage. They are **not stored**.
- `ALIGNED` means the approved WBS has sufficient governed relationships to the relevant Project Controls domains, judged against thresholds defined later per domain profile. It never means merely "approved".

## 4. Software / SDD future compatibility (boundary only)

For software projects a WBS may follow Product/Domain → Capability → Service/Component → Deliverable → Work Package. Future AI-Gen / SDD integration may **link** WBS nodes to specifications, architecture, implementation work and validation evidence.

SDD objects remain their own domain objects: `SDD node != WBS node`, analogous to `SCHEDULE ACTIVITY != WBS NODE`. This integration is out of scope for PC-1R, PC-2a and PC-2b.
