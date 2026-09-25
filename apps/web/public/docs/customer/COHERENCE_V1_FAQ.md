# Coherence Score v1 FAQ

## What changed?

Coherence Score v1 is the scoring model C2Pro uses for new audits created on or after **2026-05-01**. It replaces the older flag-based score with a weighted model that considers finding severity, confidence, and project scope.

## Why do some projects show no score?

C2Pro now withholds the score when there is not enough evidence to calculate it defensibly. A contract-only upload creates an `AUDIT_INCOMPLETE` alert and shows which dimensions are missing, typically schedule and budget.

## What should I upload?

For a full score, upload the complete audit triplet:

- Contract
- Schedule
- Budget

The dashboard will calculate the v1 score after those dimensions are available.

## What happens to older scores?

Historical v0 scores are not recalculated. They remain visible with a v0 badge so teams can distinguish older flag-based results from new v1 results.

## How should procurement teams use alerts?

Open alerts can be filtered by status, sorted by severity, and copied into vendor communications. Use the copied message as a starting point for the vendor response request, then attach the relevant evidence or clause references.
