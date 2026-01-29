from __future__ import annotations

from typing import Iterable
from uuid import UUID

from src.analysis.adapters.persistence.models import AlertSeverity
from src.analysis.application.schemas import AlertCreate
from src.coherence.rules_engine.context_rules import CoherenceRuleResult

TEMPLATES: dict[str, str] = {
    "R14": (
        "El material '{material}' tiene un Lead Time de {lead_time} dias, "
        "lo que retrasa la entrega en {delay_days} dias (fecha requerida: {needed_date})."
    ),
    "R2": "La partida presupuestaria supera el monto contractual en {variance_percentage:.1f}%.",
    "R02": "La partida presupuestaria supera el monto contractual en {variance_percentage:.1f}%.",
    "R12": (
        "La tarea '{successor_name}' inicia el {successor_start_date} antes de que "
        "termine su predecesora '{predecessor_name}' ({predecessor_end_date})."
    ),
    "R15": "El item del BOM '{item_name}' no tiene partida presupuestaria asociada.",
    "R20": "La tarea '{task_name}' no tiene responsable asignado.",
    "R6": "Falta una licencia o permiso requerido en el contrato.",
}

RULE_TITLES: dict[str, str] = {
    "R14": "Orden de material critica retrasada",
    "R2": "Desviacion presupuestaria",
    "R02": "Desviacion presupuestaria",
    "R12": "Dependencias de cronograma invalidas",
    "R15": "Material sin presupuesto",
    "R20": "Tarea sin responsable",
    "R6": "Permisos contractuales incompletos",
}

RULE_SEVERITIES: dict[str, AlertSeverity] = {
    "R14": AlertSeverity.CRITICAL,
    "R12": AlertSeverity.CRITICAL,
    "R2": AlertSeverity.HIGH,
    "R02": AlertSeverity.HIGH,
    "R15": AlertSeverity.HIGH,
    "R20": AlertSeverity.MEDIUM,
    "R6": AlertSeverity.MEDIUM,
}


class AlertGenerator:
    def __init__(self, project_id: UUID, analysis_id: UUID | None = None) -> None:
        self._project_id = project_id
        self._analysis_id = analysis_id

    def generate(self, rule_result: CoherenceRuleResult) -> list[AlertCreate]:
        """
        Builds alert payloads from a single rule result.

        TODO: Group repeated findings into a summary alert when needed.
        """
        if not rule_result.is_violated:
            return []

        rule_id = rule_result.rule_id
        evidence = rule_result.evidence or {}

        items = self._expand_evidence_items(rule_id, evidence)
        alerts: list[AlertCreate] = []
        for item in items:
            description = self._render_message(rule_id, item)
            alerts.append(
                AlertCreate(
                    project_id=self._project_id,
                    analysis_id=self._analysis_id,
                    title=self._title_for(rule_id),
                    description=description,
                    severity=self._severity_for(rule_id, item),
                    rule_id=rule_id,
                    category=self._category_for(rule_id),
                    source_clause_id=self._source_clause_id(item),
                    related_clause_ids=self._related_clause_ids(item),
                    affected_entities=self._affected_entities(rule_id, item),
                    alert_metadata={"evidence": item},
                )
            )
        return alerts

    def _expand_evidence_items(self, rule_id: str, evidence: dict) -> list[dict]:
        if rule_id == "R12":
            return [self._merge_evidence(evidence, item) for item in evidence.get("violations", [])]
        if rule_id == "R14":
            return [self._merge_evidence(evidence, item) for item in evidence.get("risks", [])]
        if rule_id == "R15":
            return [
                self._merge_evidence(evidence, {"item_name": item})
                for item in evidence.get("unbudgeted_items", [])
            ]
        if rule_id == "R20":
            return [
                self._merge_evidence(evidence, {"task_name": item})
                for item in evidence.get("orphan_tasks", [])
            ]
        return [evidence]

    def _merge_evidence(self, base: dict, item: dict) -> dict:
        merged = dict(base)
        merged.update(item)
        return merged

    def _render_message(self, rule_id: str, evidence: dict) -> str:
        template = TEMPLATES.get(rule_id)
        if not template:
            return f"Regla {rule_id} detecto una inconsistencia."
        try:
            return template.format(**evidence)
        except Exception:
            return template

    def _title_for(self, rule_id: str) -> str:
        return RULE_TITLES.get(rule_id, f"Alerta {rule_id}")

    def _severity_for(self, rule_id: str, evidence: dict) -> AlertSeverity:
        severity = str(evidence.get("severity", "")).lower()
        if severity:
            for candidate in AlertSeverity:
                if candidate.value == severity:
                    return candidate
        return RULE_SEVERITIES.get(rule_id, AlertSeverity.LOW)

    def _category_for(self, rule_id: str) -> str | None:
        if rule_id in {"R12", "R14"}:
            return "schedule"
        if rule_id in {"R2", "R02", "R15"}:
            return "financial"
        if rule_id in {"R6"}:
            return "legal"
        return None

    def _source_clause_id(self, evidence: dict) -> UUID | None:
        clause_id = evidence.get("source_clause_id")
        if clause_id:
            try:
                return UUID(str(clause_id))
            except ValueError:
                return None
        return None

    def _related_clause_ids(self, evidence: dict) -> list[UUID] | None:
        clause_ids = evidence.get("related_clause_ids")
        if not clause_ids:
            return None
        result: list[UUID] = []
        for clause_id in clause_ids:
            try:
                result.append(UUID(str(clause_id)))
            except ValueError:
                continue
        return result or None

    def _affected_entities(self, rule_id: str, evidence: dict) -> dict:
        entities: dict[str, list[str]] = {}
        if rule_id == "R12":
            ids = []
            if evidence.get("successor_id"):
                ids.append(str(evidence.get("successor_id")))
            if evidence.get("predecessor_id"):
                ids.append(str(evidence.get("predecessor_id")))
            if ids:
                entities["schedule_item_ids"] = ids
        if rule_id == "R14" and evidence.get("material"):
            entities["bom_items"] = [str(evidence["material"])]
        return entities

