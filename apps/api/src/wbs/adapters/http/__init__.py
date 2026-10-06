"""WBS HTTP adapters.

The canonical project WBS is served by the projects router (GET /projects/{id}/wbs) and the
procurement WBS API through the canonical WBS repository. The dormant ``/wbs-tree`` router was
removed by PC-1R (#886): it allowed cross-project parents and disagreed with canonical ordering.
``governance_router`` (PC-2a.1, #895) serves the read-only governance API: derived authority,
change sets and immutable baseline history.
"""

__all__: list[str] = []
