"""
TS-I6-COH-SVC-001: Coherence alert generator.
"""

from __future__ import annotations

from typing import Any

from uuid import UUID

from src.analysis.application.dtos import AlertCreate
from src.analysis.domain.risk_categories import normalize_category
from src.coherence.rules_engine.context_rules import CoherenceRuleResult
from src.shared_kernel.enums import AlertSeverity, AlertType

template_locale_default = "es"  # TASK-COH-V1-06: Bilingualization


def get_template(rule_id: str, locale: str | None = None) -> str:
    """Get template for rule_id, optionally in specified locale."""
    loc = locale or template_locale_default
    templates = TEMPLATES_EN if loc == "en" else TEMPLATES
    return templates.get(rule_id, TEMPLATES.get(rule_id, ""))


TEMPLATES: dict[str, str] = {
    "DET-SCP-DELIVERABLES": "El alcance menciona entregables o trabajos sin definicion estructurada verificable.",
    "DET-CRS-SCPBUD": "Hay entregables de alcance sin partida presupuestaria asociada.",
    "DET-BUD-OVERRUN": "El presupuesto actual supera el presupuesto planificado.",
    "DET-BUD-LINEITEM": "La partida presupuestaria no cuadra con precio unitario por cantidad.",
    "DET-BUD-SUM": "La suma de partidas presupuestarias difiere del importe contractual ({deviation_pct:.1f}%).",
    "DET-BUD-INTERNAL": "La suma de partidas presupuestarias difiere del total declarado del presupuesto ({deviation_pct:.1f}%).",
    "DET-TIM-STATUS": "El cronograma tiene estado de riesgo o retraso.",
    "DET-TIM-DURATION": "La duracion del hito o actividad es incoherente.",
    "DET-TEC-SPEC": "La clausula tecnica no referencia una especificacion o norma verificable.",
    "DET-TEC-BOMBUDGET": "Hay items de BOM sin partida presupuestaria asociada.",
    "DET-LEG-PENALTY": "La clausula de penalizacion expone responsabilidad no acotada o excesiva.",
    "DET-LEG-NOTICE": "El periodo de notificacion contractual esta fuera de rango.",
    "DET-QUA-STANDARD": "La clausula de calidad usa estandares genericos sin referencia especifica.",
    "DET-QUA-INSPECT": "La clausula de inspeccion no define frecuencia o metodo.",
    "R-SCOPE-CLARITY-01": "El alcance contiene ambiguedades que impiden validar entregables.",
    "R-PAYMENT-CLARITY-01": "Las condiciones de pago no especifican montos, plazos o condiciones suficientes.",
    "R-SCHEDULE-CLARITY-01": "Los plazos o hitos del cronograma son ambiguos o incompletos.",
    "R-TECHNICAL-SPEC-CLARITY-01": "La especificacion tecnica no permite verificar cumplimiento de forma objetiva.",
    "R-RESPONSIBILITY-01": "Las responsabilidades no estan asignadas a una parte especifica.",
    "R-QUALITY-STANDARDS-01": "Los estandares de calidad no estan definidos con referencias verificables.",
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
    "AUDIT_INCOMPLETE": "Coherence Score withheld: missing dimensions {missing_dimensions}. Supply schedule and/or budget to obtain a defensible score.",  # TBD-EN
    "ADV-BUDGET-EXHAUSTED": "Deep semantic analysis paused: tenant analysis budget exhausted. Resets {reset_date}.",
}

RULE_TITLES: dict[str, str] = {
    "DET-SCP-DELIVERABLES": "Entregables de alcance incompletos",
    "DET-CRS-SCPBUD": "Alcance sin cobertura presupuestaria",
    "DET-BUD-OVERRUN": "Sobrecoste presupuestario",
    "DET-BUD-LINEITEM": "Error aritmetico de partida",
    "DET-BUD-SUM": "Descuadre presupuesto vs contrato",
    "DET-BUD-INTERNAL": "Descuadre interno del presupuesto",
    "DET-TIM-STATUS": "Cronograma en riesgo",
    "DET-TIM-DURATION": "Duracion incoherente",
    "DET-TEC-SPEC": "Especificacion tecnica incompleta",
    "DET-TEC-BOMBUDGET": "BOM sin presupuesto",
    "DET-LEG-PENALTY": "Penalizacion contractual riesgosa",
    "DET-LEG-NOTICE": "Periodo de notificacion fuera de rango",
    "DET-QUA-STANDARD": "Estandar de calidad generico",
    "DET-QUA-INSPECT": "Inspeccion incompleta",
    "R-SCOPE-CLARITY-01": "Alcance ambiguo",
    "R-PAYMENT-CLARITY-01": "Pagos ambiguos",
    "R-SCHEDULE-CLARITY-01": "Cronograma ambiguo",
    "R-TECHNICAL-SPEC-CLARITY-01": "Especificacion tecnica ambigua",
    "R-RESPONSIBILITY-01": "Responsabilidad ambigua",
    "R-QUALITY-STANDARDS-01": "Calidad ambigua",
    "R14": "Orden de material critica retrasada",
    "R2": "Desviacion presupuestaria",
    "R02": "Desviacion presupuestaria",
    "R12": "Dependencias de cronograma invalidas",
    "R15": "Material sin presupuesto",
    "R20": "Tarea sin responsable",
    "R6": "Permisos contractuales incompletos",
    "AUDIT_INCOMPLETE": "Audit incomplete — full triplet not provided",  # TBD-EN
    "ADV-BUDGET-EXHAUSTED": "Deep semantic analysis paused",
}

RULE_SEVERITIES: dict[str, AlertSeverity] = {
    "DET-SCP-DELIVERABLES": AlertSeverity.MEDIUM,
    "DET-CRS-SCPBUD": AlertSeverity.HIGH,
    "DET-BUD-OVERRUN": AlertSeverity.HIGH,
    "DET-BUD-LINEITEM": AlertSeverity.HIGH,
    "DET-BUD-SUM": AlertSeverity.HIGH,
    "DET-BUD-INTERNAL": AlertSeverity.HIGH,
    "DET-TIM-STATUS": AlertSeverity.HIGH,
    "DET-TIM-DURATION": AlertSeverity.CRITICAL,
    "DET-TEC-SPEC": AlertSeverity.MEDIUM,
    "DET-TEC-BOMBUDGET": AlertSeverity.HIGH,
    "DET-LEG-PENALTY": AlertSeverity.HIGH,
    "DET-LEG-NOTICE": AlertSeverity.HIGH,
    "DET-QUA-STANDARD": AlertSeverity.MEDIUM,
    "DET-QUA-INSPECT": AlertSeverity.MEDIUM,
    "R-SCOPE-CLARITY-01": AlertSeverity.HIGH,
    "R-PAYMENT-CLARITY-01": AlertSeverity.HIGH,
    "R-SCHEDULE-CLARITY-01": AlertSeverity.HIGH,
    "R-TECHNICAL-SPEC-CLARITY-01": AlertSeverity.HIGH,
    "R-RESPONSIBILITY-01": AlertSeverity.MEDIUM,
    "R-QUALITY-STANDARDS-01": AlertSeverity.MEDIUM,
    "R14": AlertSeverity.CRITICAL,
    "R12": AlertSeverity.CRITICAL,
    "R2": AlertSeverity.HIGH,
    "R02": AlertSeverity.HIGH,
    "R15": AlertSeverity.HIGH,
    "R20": AlertSeverity.MEDIUM,
    "R6": AlertSeverity.MEDIUM,
    "AUDIT_INCOMPLETE": AlertSeverity.MEDIUM,
    "ADV-BUDGET-EXHAUSTED": AlertSeverity.LOW,
}

SUMMARY_TEMPLATES: dict[str, str] = {
    "R12": "Se detectaron {count} dependencias de cronograma invalidas. Ejemplos: {examples}.",
    "R14": "Se detectaron {count} materiales con riesgo de lead time. Ejemplos: {examples}.",
    "R15": "Se detectaron {count} items del BOM sin partida presupuestaria asociada. Ejemplos: {examples}.",
    "R20": "Se detectaron {count} tareas sin responsable asignado. Ejemplos: {examples}.",
}

# TASK-COH-V1-06: English templates for bilingualization (TBD-EN = skeleton only)
TEMPLATES_EN: dict[str, str] = {
    "AUDIT_INCOMPLETE": "Coherence Score withheld: missing dimensions {missing_dimensions}. Supply schedule and/or budget to obtain a defensible score.",
    # TBD-EN: Add full translations here as they're completed
}


class AlertGenerator:
    def __init__(self, project_id: UUID, analysis_id: UUID | None = None) -> None:
        self._project_id = project_id
        self._analysis_id = analysis_id

    def generate(self, rule_result: CoherenceRuleResult) -> list[AlertCreate]:
        """
        Builds alert payloads from a single rule result.
        """
        if not rule_result.is_violated:
            return []

        rule_id = rule_result.rule_id
        evidence = rule_result.evidence or {}

        items = self._expand_evidence_items(rule_id, evidence)
        if self._should_group(rule_id, items):
            return [self._build_summary_alert(rule_id, evidence, items)]

        alerts: list[AlertCreate] = []
        for item in items:
            description = self._render_message(rule_id, item, grouped=False, item_count=1)
            alerts.append(
                AlertCreate(
                    project_id=self._project_id,
                    analysis_id=self._analysis_id,
                    alert_type=AlertType.COHERENCE,  # TASK-BCK-026: Set alert type
                    title=self._title_for(rule_id),
                    description=description,
                    severity=self._severity_for(rule_id, item),
                    rule_id=rule_id,
                    category=self._category_for(rule_id),
                    source_clause_id=self._source_clause_id(item),
                    related_clause_ids=self._related_clause_ids(item),
                    affected_entities=self._affected_entities(rule_id, item),
                    alert_metadata={
                        "evidence": item,
                        "grouped": False,
                        "group_size": 1,
                    },
                    recommendation=None,
                    impact_level=None,
                )
            )
        return alerts

    def generate_risk_alerts(self, risk_items: list[dict[str, Any]]) -> list[AlertCreate]:
        """
        Generate risk alerts from AI extraction (TASK-BCK-026).

        Args:
            risk_items: List of risk dictionaries from AI extraction

        Returns:
            List of AlertCreate DTOs
        """
        alerts: list[AlertCreate] = []

        for item in risk_items:
            severity = self._map_risk_severity(item)
            title = item.get("summary") or item.get("title") or "Risk identified"
            description = item.get("description") or "Risk detected by AI extraction."
            canonical = normalize_category(item.get("category"))
            category = canonical.value if canonical is not None else None
            impact_level = item.get("impact_level")
            confidence = item.get("confidence")

            alerts.append(
                AlertCreate(
                    project_id=self._project_id,
                    analysis_id=self._analysis_id,
                    alert_type=AlertType.RISK,
                    title=title,
                    description=description,
                    severity=severity,
                    category=category,
                    impact_level=impact_level,
                    alert_metadata={
                        "confidence": confidence,
                        "raw": item,
                    },
                                    recommendation=None,
                    rule_id=None,
                    source_clause_id=None,
                    related_clause_ids=None,
                )
            )

        return alerts

    def _map_risk_severity(self, risk_item: dict[str, Any]) -> AlertSeverity:
        """
        Map risk impact_level to AlertSeverity.

        Args:
            risk_item: Risk dictionary with impact_level field

        Returns:
            AlertSeverity enum value
        """
        impact_level = str(risk_item.get("impact_level", "")).lower()

        severity_mapping = {
            "critical": AlertSeverity.CRITICAL,
            "high": AlertSeverity.HIGH,
            "medium": AlertSeverity.MEDIUM,
            "low": AlertSeverity.LOW,
        }

        return severity_mapping.get(impact_level, AlertSeverity.LOW)

    def _should_group(self, rule_id: str, items: list[dict[str, Any]]) -> bool:
        return rule_id in SUMMARY_TEMPLATES and len(items) > 1

    def _build_summary_alert(
        self,
        rule_id: str,
        evidence: dict[str, Any],
        items: list[dict[str, Any]],
    ) -> AlertCreate:
        summary_evidence = dict(evidence)
        group_size = len(items)
        summary_evidence["grouped"] = True
        summary_evidence["group_size"] = group_size
        summary_evidence["sample_items"] = items[:2]

        return AlertCreate(
            project_id=self._project_id,
            analysis_id=self._analysis_id,
            alert_type=AlertType.COHERENCE,  # TASK-BCK-026: Set alert type
            title=self._title_for(rule_id),
            description=self._render_message(
                rule_id,
                summary_evidence,
                grouped=True,
                item_count=group_size,
            ),
            severity=self._severity_for(rule_id, summary_evidence),
            rule_id=rule_id,
            category=self._category_for(rule_id),
            source_clause_id=self._summary_source_clause_id(items),
            related_clause_ids=self._summary_related_clause_ids(items),
            affected_entities=self._summary_affected_entities(rule_id, items),
            alert_metadata={
                "evidence": summary_evidence,
                "grouped": True,
                "group_size": group_size,
            },
            recommendation=None,
            impact_level=None,
        )

    def _expand_evidence_items(self, rule_id: str, evidence: dict[str, Any]) -> list[dict[str, Any]]:
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

    def _merge_evidence(self, base: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        merged.update(item)
        return merged

    def _render_message(
        self,
        rule_id: str,
        evidence: dict[str, Any],
        *,
        grouped: bool,
        item_count: int,
    ) -> str:
        if grouped and rule_id in SUMMARY_TEMPLATES:
            examples = self._summary_examples(rule_id, evidence)
            return SUMMARY_TEMPLATES[rule_id].format(count=item_count, examples=examples)

        template = TEMPLATES.get(rule_id)
        if not template:
            return f"Regla {rule_id} detecto una inconsistencia."
        try:
            return template.format(**evidence)
        except Exception:
            return template

    def _title_for(self, rule_id: str) -> str:
        return RULE_TITLES.get(rule_id, f"Alerta {rule_id}")

    def _severity_for(self, rule_id: str, evidence: dict[str, Any]) -> AlertSeverity:
        severity = str(evidence.get("severity", "")).lower()
        if severity:
            for candidate in AlertSeverity:
                if candidate.value == severity:
                    return candidate
        return RULE_SEVERITIES.get(rule_id, AlertSeverity.LOW)

    def _category_for(self, rule_id: str) -> str | None:
        """Return a canonical RiskCategory value for a coherence rule.

        Coherence rules internally speak the legacy ``TIME`` / ``BUDGET``
        vocabulary; at the alert-persistence boundary we emit canonical
        names (``SCHEDULE``, ``BUDGET``, ``LEGAL``) so the API and frontend
        see a single taxonomy.
        """
        rule_to_raw: dict[str, str] = {
            "DET-SCP-DELIVERABLES": "SCOPE",
            "DET-CRS-SCPBUD": "SCOPE",
            "DET-BUD-OVERRUN": "BUDGET",
            "DET-BUD-LINEITEM": "BUDGET",
            "DET-BUD-SUM": "BUDGET",
            "DET-TIM-STATUS": "SCHEDULE",
            "DET-TIM-DURATION": "SCHEDULE",
            "DET-TEC-SPEC": "TECHNICAL",
            "DET-TEC-BOMBUDGET": "TECHNICAL",
            "DET-LEG-PENALTY": "LEGAL",
            "DET-LEG-NOTICE": "LEGAL",
            "DET-QUA-STANDARD": "QUALITY",
            "DET-QUA-INSPECT": "QUALITY",
            "R-SCOPE-CLARITY-01": "SCOPE",
            "R-PAYMENT-CLARITY-01": "BUDGET",
            "R-SCHEDULE-CLARITY-01": "SCHEDULE",
            "R-TECHNICAL-SPEC-CLARITY-01": "TECHNICAL",
            "R-RESPONSIBILITY-01": "LEGAL",
            "R-QUALITY-STANDARDS-01": "QUALITY",
            "R12": "SCHEDULE",
            "R14": "SCHEDULE",
            "R2": "BUDGET",
            "R02": "BUDGET",
            "R15": "BUDGET",
            "R6": "LEGAL",
        }
        raw = rule_to_raw.get(rule_id)
        if raw is None:
            return None
        canonical = normalize_category(raw)
        return canonical.value if canonical is not None else None

    def _source_clause_id(self, evidence: dict[str, Any]) -> UUID | None:
        clause_id = evidence.get("source_clause_id")
        if clause_id:
            try:
                return UUID(str(clause_id))
            except ValueError:
                return None
        return None

    def _related_clause_ids(self, evidence: dict[str, Any]) -> list[UUID] | None:
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

    def _affected_entities(self, rule_id: str, evidence: dict[str, Any]) -> dict[str, Any]:
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
        if rule_id == "R15" and evidence.get("item_name"):
            entities["bom_items"] = [str(evidence["item_name"])]
        if rule_id == "R20" and evidence.get("task_name"):
            entities["task_names"] = [str(evidence["task_name"])]
        return entities

    def _summary_source_clause_id(self, items: list[dict[str, Any]]) -> UUID | None:
        source_clause_ids = {
            parsed
            for item in items
            if (parsed := self._source_clause_id(item)) is not None
        }
        if len(source_clause_ids) == 1:
            return next(iter(source_clause_ids))
        return None

    def _summary_related_clause_ids(self, items: list[dict[str, Any]]) -> list[UUID] | None:
        related: list[UUID] = []
        for item in items:
            parsed = self._related_clause_ids(item)
            if parsed:
                related.extend(parsed)
        if not related:
            return None
        return list(dict.fromkeys(related))

    def _summary_affected_entities(self, rule_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        merged: dict[str, list[str]] = {}
        for item in items:
            entities = self._affected_entities(rule_id, item)
            for key, values in entities.items():
                merged.setdefault(key, [])
                merged[key].extend(values)
        return {key: list(dict.fromkeys(values)) for key, values in merged.items()}

    def _summary_examples(self, rule_id: str, evidence: dict[str, Any]) -> str:
        sample_items = evidence.get("sample_items") or []
        if rule_id == "R12":
            labels = [
                f"{item.get('predecessor_name', 'tarea previa')} -> {item.get('successor_name', 'tarea siguiente')}"
                for item in sample_items
            ]
        elif rule_id == "R14":
            labels = [str(item.get("material", "material")) for item in sample_items]
        elif rule_id == "R15":
            labels = [str(item.get("item_name", "item")) for item in sample_items]
        elif rule_id == "R20":
            labels = [str(item.get("task_name", "tarea")) for item in sample_items]
        else:
            labels = []

        cleaned = [label for label in labels if label]
        return ", ".join(cleaned) if cleaned else "sin ejemplos"

