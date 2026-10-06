"""WBS HTTP adapters.

The canonical project WBS is served by the projects router (GET /projects/{id}/wbs) and the
procurement WBS API through the canonical WBS repository. The dormant ``/wbs-tree`` router was
removed by PC-1R (#886): it allowed cross-project parents and disagreed with canonical ordering.
"""

__all__: list[str] = []
