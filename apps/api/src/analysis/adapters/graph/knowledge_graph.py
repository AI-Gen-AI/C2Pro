from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
from uuid import UUID

import networkx as nx

from src.analysis.adapters.persistence.models import Alert
from src.analysis.ports.alert_repository import AlertRepository
from src.analysis.ports.knowledge_graph import KnowledgeGraphPort
from src.documents.domain.models import Clause
from src.documents.ports.document_repository import IDocumentRepository
from src.procurement.domain.models import WBSItem
from src.procurement.ports.wbs_repository import IWBSRepository
from src.stakeholders.domain.models import RACIRole, RaciAssignment, Stakeholder
from src.stakeholders.ports.stakeholder_repository import IStakeholderRepository


@dataclass
class GraphPath:
    nodes: list[str]
    edges: list[str]


class ProjectKnowledgeGraph(KnowledgeGraphPort):
    def __init__(
        self,
        *,
        stakeholder_repository: IStakeholderRepository,
        wbs_repository: IWBSRepository,
        alert_repository: AlertRepository,
        document_repository: IDocumentRepository,
    ) -> None:
        self.stakeholder_repository = stakeholder_repository
        self.wbs_repository = wbs_repository
        self.alert_repository = alert_repository
        self.document_repository = document_repository
        self.graph = nx.DiGraph()

    async def build_graph(self, project_id: UUID, tenant_id: UUID) -> nx.DiGraph:
        self.graph.clear()

        stakeholders = await self._load_stakeholders(project_id)
        tasks = await self._load_tasks(project_id, tenant_id)
        risks = await self._load_risks(project_id)
        clauses = await self._load_clauses(risks, tasks)
        raci_rows = await self._load_raci(project_id)

        for stakeholder in stakeholders:
            self._add_node(
                _stakeholder_node_id(stakeholder.id),
                node_type="STAKEHOLDER",
                label=stakeholder.name or "Stakeholder",
                properties={
                    "role": stakeholder.role,
                    "organization": stakeholder.organization,
                    "quadrant": getattr(stakeholder.quadrant, "value", None),
                },
            )

        code_to_id = {task.code: task.id for task in tasks if task.code}
        for task in tasks:
            parent_id = code_to_id.get(task.parent_code) if task.parent_code else None
            self._add_node(
                _task_node_id(task.id),
                node_type="TASK",
                label=task.name,
                properties={
                    "wbs_code": task.code,
                    "parent_id": str(parent_id) if parent_id else None,
                },
            )
            if parent_id:
                self._add_edge(
                    _task_node_id(task.id),
                    _task_node_id(parent_id),
                    relation="DEPENDS_ON",
                    properties={"relation_type": "parent"},
                )

        for risk in risks:
            self._add_node(
                _risk_node_id(risk.id),
                node_type="RISK",
                label=risk.title,
                properties={
                    "severity": risk.severity.value,
                    "category": risk.category,
                },
            )

        for clause in clauses:
            self._add_node(
                _clause_node_id(clause.id),
                node_type="CLAUSE",
                label=clause.title or clause.clause_code,
                properties={"clause_code": clause.clause_code},
            )

        for assignment in raci_rows:
            if assignment.raci_role not in {RACIRole.RESPONSIBLE, RACIRole.ACCOUNTABLE}:
                continue
            self._add_edge(
                _stakeholder_node_id(assignment.stakeholder_id),
                _task_node_id(assignment.wbs_item_id),
                relation="MANAGES",
                properties={"raci_role": assignment.raci_role.value},
            )

        for risk in risks:
            if risk.source_clause_id:
                self._add_edge(
                    _risk_node_id(risk.id),
                    _clause_node_id(risk.source_clause_id),
                    relation="DERIVED_FROM",
                )
            for wbs_id in _extract_wbs_ids(risk):
                self._add_edge(
                    _risk_node_id(risk.id),
                    _task_node_id(wbs_id),
                    relation="IMPACTS",
                )

        return self.graph

    def find_impact_chain(
        self,
        source_id: str,
        target_id: str,
        *,
        max_paths: int = 1,
        cutoff: int = 6,
        allow_undirected: bool = True,
    ) -> list[GraphPath]:
        if source_id not in self.graph or target_id not in self.graph:
            return []

        def _collect_paths(graph: nx.Graph) -> list[GraphPath]:
            found: list[GraphPath] = []
            for path in nx.all_simple_paths(
                graph, source=source_id, target=target_id, cutoff=cutoff
            ):
                edges = []
                for idx in range(len(path) - 1):
                    edge = graph.get_edge_data(path[idx], path[idx + 1]) or {}
                    edges.append(edge.get("relation", "RELATED_TO"))
                found.append(GraphPath(nodes=path, edges=edges))
                if len(found) >= max_paths:
                    break
            return found

        try:
            paths = _collect_paths(self.graph)
        except nx.NetworkXNoPath:
            paths = []

        if paths or not allow_undirected:
            return paths

        undirected = self.graph.to_undirected()
        try:
            return _collect_paths(undirected)
        except nx.NetworkXNoPath:
            return []

    def degree_centrality(self) -> dict[str, float]:
        return nx.degree_centrality(self.graph)

    async def _load_stakeholders(self, project_id: UUID) -> list[Stakeholder]:
        stakeholders, _ = await self.stakeholder_repository.get_stakeholders_by_project(
            project_id=project_id,
            skip=0,
            limit=1000,
        )
        return list(stakeholders)

    async def _load_tasks(self, project_id: UUID, tenant_id: UUID) -> list[WBSItem]:
        return await self.wbs_repository.get_by_project(project_id, tenant_id)

    async def _load_risks(self, project_id: UUID) -> list[Alert]:
        page = await self.alert_repository.list_for_project(
            project_id=project_id,
            category="risk",
            limit=500,
        )
        return list(page.items)

    async def _load_clauses(
        self,
        risks: Iterable[Alert],
        tasks: Iterable[WBSItem],
    ) -> list[Clause]:
        clause_ids = {risk.source_clause_id for risk in risks if risk.source_clause_id}
        clause_ids.update({task.source_clause_id for task in tasks if task.source_clause_id})
        if not clause_ids:
            return []
        return await self.document_repository.get_clauses_by_ids(list(clause_ids))

    async def _load_raci(self, project_id: UUID) -> list[RaciAssignment]:
        return await self.stakeholder_repository.list_raci_assignments(project_id)

    def _add_node(self, node_id: str, *, node_type: str, label: str, properties: dict[str, Any]):
        self.graph.add_node(
            node_id,
            type=node_type,
            label=label,
            properties=properties,
        )

    def _add_edge(
        self,
        source_id: str,
        target_id: str,
        *,
        relation: str,
        properties: dict[str, Any] | None = None,
    ):
        self.graph.add_edge(
            source_id,
            target_id,
            relation=relation,
            properties=properties or {},
        )


def _stakeholder_node_id(stakeholder_id: UUID) -> str:
    return f"stk_{stakeholder_id}"


def _task_node_id(task_id: UUID) -> str:
    return f"tsk_{task_id}"


def _risk_node_id(risk_id: UUID) -> str:
    return f"rsk_{risk_id}"


def _clause_node_id(clause_id: UUID) -> str:
    return f"cl_{clause_id}"


def _extract_wbs_ids(risk: Alert) -> list[UUID]:
    wbs_ids: list[UUID] = []
    payload = risk.affected_entities or {}
    candidates = payload.get("wbs") or payload.get("wbs_items") or []
    for value in candidates:
        try:
            wbs_ids.append(UUID(str(value)))
        except Exception:
            continue
    return wbs_ids
