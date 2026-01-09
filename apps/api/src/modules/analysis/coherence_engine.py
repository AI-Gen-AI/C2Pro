from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_session_with_tenant
from src.modules.documents.models import Clause, Document
from src.modules.projects.models import Project
from src.modules.stakeholders.models import BOMItem, WBSItem


class CoherenceEngine:
    """
    Motor principal de coherencia para analizar proyectos y generar alertas.
    Este es un placeholder, la implementación completa se realizará en fases posteriores.
    """

    def __init__(self):
        # Placeholder for initialization logic
        pass

    async def analyze_project(self, db: AsyncSession, project_id: UUID) -> dict[str, Any]:
        """
        Ejecuta el análisis completo de coherencia para un proyecto dado.
        Esta es una implementación placeholder.
        """
        # In a real implementation, this would:
        # 1. Fetch documents and extractions
        # 2. Generate WBS and BOM
        # 3. Apply coherence rules
        # 4. Calculate coherence score
        # 5. Save analysis and alerts
        print(f"Placeholder: Analyzing project {project_id} for coherence...")

        documents = await self._fetch_documents_and_extractions(db, project_id)
        # Placeholder calls for subsequent steps
        wbs, bom = await self._generate_wbs_and_bom(
            db, project_id, documents
        )  # extractions will be derived from documents
        coherence_results = await self._apply_coherence_rules(project_id, wbs, bom)
        coherence_score, alerts = await self._calculate_coherence_score(
            project_id, coherence_results
        )
        await self._save_analysis_and_alerts(project_id, coherence_score, alerts)

        return {
            "project_id": str(project_id),
            "status": "completed",
            "coherence_score": coherence_score,
            "alerts_count": len(alerts),
            "message": "Coherence analysis executed (placeholder).",
        }

    async def _fetch_documents_and_extractions(
        self, db: AsyncSession, project_id: UUID
    ) -> list["Document"]:
        """
        Fetches documents and their associated clauses for a given project.
        Uses tenant-aware session to ensure RLS is applied.
        """
        print(f"Fetching documents and extractions for project {project_id}")

        # Fetch the project first to get the tenant_id
        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()

        if not project:
            print(f"Project with ID {project_id} not found.")
            return []

        async with get_session_with_tenant(project.tenant_id) as tenant_db:
            documents_result = await tenant_db.execute(
                select(Document)
                .where(Document.project_id == project_id)
                .options(selectinload(Document.clauses))
            )
            documents = documents_result.scalars().all()
            print(f"Found {len(documents)} documents for project {project_id}")
            return documents, []


from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml  # Assuming PyYAML is available or will be added
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class CoherenceRule:
    rule_id: str
    name: str
    description: str
    severity: str
    documents: list[str]
    message: str
    suggested_action: str


class CoherenceEngine:
    """
    Motor principal de coherencia para analizar proyectos y generar alertas.
    Este es un placeholder, la implementación completa se realizará en fases posteriores.
    """

    def __init__(self):
        # Placeholder for initialization logic
        self.coherence_rules = self._load_coherence_rules()
        pass

    def _load_coherence_rules(self) -> dict[str, CoherenceRule]:
        """Loads coherence rules from the YAML file."""
        # Use __file__ to get the path relative to the current file
        rules_path = Path(__file__).parent / "coherence_rules.yaml"
        with open(rules_path, encoding="utf-8") as f:
            rules_data = yaml.safe_load(f)

        loaded_rules = {}
        for rule_id, rule_content in rules_data.items():
            loaded_rules[rule_id] = CoherenceRule(rule_id=rule_id, **rule_content)
        return loaded_rules


from datetime import datetime

# ... (rest of imports) ...


class CoherenceEngine:
    # ... (rest of class definition) ...

    async def analyze_project(self, db: AsyncSession, project_id: UUID) -> dict[str, Any]:
        """
        Ejecuta el análisis completo de coherencia para un proyecto dado.
        """
        print(f"Starting coherence analysis for project {project_id}")
        started_at = datetime.utcnow()

        documents = await self._fetch_documents_and_extractions(db, project_id)
        wbs_items, bom_items = await self._generate_wbs_and_bom(db, project_id, documents)
        coherence_results = await self._apply_coherence_rules(
            db, project_id, documents, wbs_items, bom_items
        )
        coherence_score, alerts = await self._calculate_coherence_score(
            project_id, coherence_results
        )
        await self._save_analysis_and_alerts(db, project_id, started_at, coherence_score, alerts)
        completed_at = datetime.utcnow()  # Assuming saving is the last step of analysis

        return {
            "project_id": str(project_id),
            "status": "completed",
            "coherence_score": coherence_score,
            "alerts_count": len(alerts),
            "message": "Coherence analysis executed.",
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
        }

    async def _fetch_documents_and_extractions(
        self, db: AsyncSession, project_id: UUID
    ) -> list["Document"]:
        """
        Fetches documents and their associated clauses for a given project.
        Uses tenant-aware session to ensure RLS is applied.
        """
        print(f"Fetching documents and extractions for project {project_id}")

        # Fetch the project first to get the tenant_id
        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()

        if not project:
            print(f"Project with ID {project_id} not found.")
            return []

        async with get_session_with_tenant(project.tenant_id) as tenant_db:
            documents_result = await tenant_db.execute(
                select(Document)
                .where(Document.project_id == project_id)
                .options(selectinload(Document.clauses))
            )
            documents = documents_result.scalars().all()
            print(f"Found {len(documents)} documents for project {project_id}")
            return documents

    async def _generate_wbs_and_bom(
        self, db: AsyncSession, project_id: UUID, documents: list["Document"]
    ) -> (list["WBSItem"], list["BOMItem"]):
        """
        Generates WBS and BOM items from the extracted entities in document clauses.
        Persists newly generated items to the database.
        """
        print(f"Generating WBS and BOM for project {project_id}")

        # Fetch the project first to get the tenant_id
        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()

        if not project:
            print(f"Project with ID {project_id} not found for WBS/BOM generation.")
            return [], []

        generated_wbs_items: list[WBSItem] = []
        generated_bom_items: list[BOMItem] = []

        async with get_session_with_tenant(project.tenant_id) as tenant_db:
            for doc in documents:
                for clause in doc.clauses:
                    extracted_entities = clause.extracted_entities

                    # Assume 'wbs_elements' key in extracted_entities for WBS items
                    if "wbs_elements" in extracted_entities and isinstance(
                        extracted_entities["wbs_elements"], list
                    ):
                        for wbs_data in extracted_entities["wbs_elements"]:
                            # Basic validation and creation for WBSItem
                            if "wbs_code" in wbs_data and "name" in wbs_data:
                                # Check if item already exists to prevent duplicates (simple check for now)
                                existing_wbs = await tenant_db.scalar(
                                    select(WBSItem).where(
                                        WBSItem.project_id == project_id,
                                        WBSItem.wbs_code == wbs_data["wbs_code"],
                                    )
                                )
                                if not existing_wbs:
                                    wbs_item = WBSItem(
                                        project_id=project_id,
                                        wbs_code=wbs_data["wbs_code"],
                                        name=wbs_data["name"],
                                        description=wbs_data.get("description"),
                                        level=wbs_data.get("level", 1),
                                        item_type=wbs_data.get("item_type"),
                                        funded_by_clause_id=clause.id,
                                        metadata={"source_document_id": str(doc.id)},
                                    )
                                    tenant_db.add(wbs_item)
                                    generated_wbs_items.append(wbs_item)
                                else:
                                    print(
                                        f"WBSItem with code {wbs_data['wbs_code']} already exists, skipping."
                                    )

                    # Assume 'bom_elements' key in extracted_entities for BOM items
                    if "bom_elements" in extracted_entities and isinstance(
                        extracted_entities["bom_elements"], list
                    ):
                        for bom_data in extracted_entities["bom_elements"]:
                            # Basic validation and creation for BOMItem
                            if "item_name" in bom_data and "quantity" in bom_data:
                                # Check if item already exists
                                existing_bom = await tenant_db.scalar(
                                    select(BOMItem).where(
                                        BOMItem.project_id == project_id,
                                        BOMItem.item_name == bom_data["item_name"],
                                        BOMItem.unit
                                        == bom_data.get(
                                            "unit"
                                        ),  # include unit in check for uniqueness
                                    )
                                )
                                if not existing_bom:
                                    bom_item = BOMItem(
                                        project_id=project_id,
                                        item_name=bom_data["item_name"],
                                        quantity=bom_data[
                                            "quantity"
                                        ],  # assuming Decimal conversion handled by SQLAlchemy
                                        unit=bom_data.get("unit"),
                                        description=bom_data.get("description"),
                                        category=bom_data.get("category"),
                                        unit_price=bom_data.get("unit_price"),
                                        total_price=bom_data.get("total_price"),
                                        currency=bom_data.get("currency", "EUR"),
                                        contract_clause_id=clause.id,
                                        metadata={"source_document_id": str(doc.id)},
                                    )
                                    tenant_db.add(bom_item)
                                    generated_bom_items.append(bom_item)
                                else:
                                    print(
                                        f"BOMItem '{bom_data['item_name']}' already exists, skipping."
                                    )
            await tenant_db.commit()  # Commit all new WBS and BOM items
            print(
                f"Generated {len(generated_wbs_items)} WBS items and {len(generated_bom_items)} BOM items."
            )

            # Refresh all generated items to ensure relationships are loaded and IDs are present
            for item in generated_wbs_items:
                await tenant_db.refresh(item)
            for item in generated_bom_items:
                await tenant_db.refresh(item)

        return generated_wbs_items, generated_bom_items

    async def _apply_coherence_rules(
        self,
        db: AsyncSession,
        project_id: UUID,
        documents: list["Document"],
        wbs: list["WBSItem"],
        bom: list["BOMItem"],
    ) -> list[dict]:
        """
        Applies predefined coherence rules to the project's documents, WBS, and BOM.
        """
        print(f"Applying coherence rules for project {project_id}")

        coherence_results: list[dict] = []

        # Helper to find a document by type
        def get_document_by_type(doc_type: str) -> Document | None:
            return next((doc for doc in documents if doc.document_type.value == doc_type), None)

        # Helper to find clauses by type
        def get_clauses_by_type(clause_type: str) -> list[Clause]:
            all_clauses = [clause for doc in documents for clause in doc.clauses]
            return [
                clause
                for clause in all_clauses
                if clause.clause_type and clause.clause_type.value == clause_type
            ]

        for rule_id, rule in self.coherence_rules.items():
            print(f"Checking rule: {rule.name} (ID: {rule_id})")

            # Placeholder for actual rule logic
            # This is where the specific checks for each rule (R1-R18) would go.
            # For demonstration, let's implement a very simple check for R1
            if rule_id == "R1":
                contract_doc = get_document_by_type("contract")
                schedule_doc = get_document_by_type("schedule")

                if contract_doc and schedule_doc:
                    # In a real scenario, extract duration from contract and end date from schedule
                    # For now, simulate a discrepancy
                    if project_id.int % 2 == 0:  # Simulate a rule failure for even project IDs
                        coherence_results.append(
                            {
                                "rule_id": rule.rule_id,
                                "severity": rule.severity,
                                "message": rule.message.format(
                                    contract_duration="365", schedule_end_date="2026-01-01"
                                ),
                                "suggested_action": rule.suggested_action,
                                "affected_entities": [
                                    {"type": "project", "id": str(project_id)},
                                    {"type": "document", "id": str(contract_doc.id)},
                                    {"type": "document", "id": str(schedule_doc.id)},
                                ],
                            }
                        )
                elif not contract_doc:
                    coherence_results.append(
                        {
                            "rule_id": rule.rule_id,
                            "severity": "low",  # Adjust severity for missing document
                            "message": f"Cannot check '{rule.name}': Contract document is missing.",
                            "suggested_action": "Upload the contract document.",
                            "affected_entities": [
                                {"type": "project", "id": str(project_id)},
                            ],
                        }
                    )
                elif not schedule_doc:
                    coherence_results.append(
                        {
                            "rule_id": rule.rule_id,
                            "severity": "low",  # Adjust severity for missing document
                            "message": f"Cannot check '{rule.name}': Schedule document is missing.",
                            "suggested_action": "Upload the schedule document.",
                            "affected_entities": [
                                {"type": "project", "id": str(project_id)},
                            ],
                        }
                    )

            # More rule implementations would follow here...
            # Example: R2 - Milestone Contractual sin Actividad
            if rule_id == "R2":
                contract_clauses = get_clauses_by_type("milestone")
                if contract_clauses:
                    # For a real check, compare with WBS/schedule activities
                    # Simulate a failure
                    if project_id.int % 3 == 0:
                        coherence_results.append(
                            {
                                "rule_id": rule.rule_id,
                                "severity": rule.severity,
                                "message": rule.message.format(
                                    milestone_name="Phase 1 Completion", milestone_date="2025-06-30"
                                ),
                                "suggested_action": rule.suggested_action,
                                "affected_entities": [
                                    {"type": "project", "id": str(project_id)},
                                    {"type": "clause", "id": str(contract_clauses[0].id)},
                                ],
                            }
                        )
                else:
                    print(f"No milestone clauses found for rule R2 for project {project_id}")

        print(
            f"Finished applying coherence rules. Found {len(coherence_results)} potential inconsistencies."
        )
        return coherence_results

    async def _calculate_coherence_score(
        self, project_id: UUID, coherence_results: list[dict]
    ) -> (float, list[dict]):
        """
        Calculates a coherence score based on the detected inconsistencies and generates alerts.
        """
        print(f"Calculating coherence score for project {project_id}")

        # Simple scoring mechanism: deduct points based on severity
        score = 100.0  # Start with a perfect score
        alerts: list[dict] = []

        severity_weights = {
            "critical": 20,
            "high": 10,
            "medium": 5,
            "low": 1,
        }

        for result in coherence_results:
            severity = result.get("severity", "low")
            score -= severity_weights.get(severity, 0)
            alerts.append(result)  # For now, all coherence results are considered alerts

        # Ensure score does not go below zero
        score = max(0.0, score)
        print(f"Coherence score for project {project_id}: {score}. Number of alerts: {len(alerts)}")
        return score, alerts

    async def _save_analysis_and_alerts(
        self,
        db: AsyncSession,
        project_id: UUID,
        started_at: datetime,
        coherence_score: float,
        alerts: list[dict],
    ):
        """
        Saves the analysis results, including the coherence score and individual alerts, to the database.
        Also updates the project's coherence score and last analysis timestamp.
        """
        print(f"Saving analysis results for project {project_id}")

        # Fetch the project first to get the tenant_id and update it
        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()

        if not project:
            print(f"Project with ID {project_id} not found for saving analysis.")
            return

        async with get_session_with_tenant(project.tenant_id) as tenant_db:
            # 1. Create Analysis record
            new_analysis = Analysis(
                project_id=project_id,
                analysis_type=AnalysisType.COHERENCE,
                status=AnalysisStatus.COMPLETED,
                coherence_score=int(coherence_score),  # Score is an integer in Analysis model
                alerts_count=len(alerts),
                started_at=started_at,
                completed_at=datetime.utcnow(),
                result_json={
                    "message": f"Coherence analysis completed with score {coherence_score}"
                },  # Placeholder for more detailed results
            )
            tenant_db.add(new_analysis)
            await tenant_db.flush()  # Flush to get the ID of the new_analysis
            print(f"Created Analysis record with ID: {new_analysis.id}")

            # 2. Create Alert records
            for alert_data in alerts:
                # Extract affected entities from the alert_data dictionary
                affected_document_ids = [
                    UUID(e["id"])
                    for e in alert_data.get("affected_entities", [])
                    if e["type"] == "document"
                ]
                affected_wbs_ids = [
                    UUID(e["id"])
                    for e in alert_data.get("affected_entities", [])
                    if e["type"] == "wbs"
                ]
                affected_bom_ids = [
                    UUID(e["id"])
                    for e in alert_data.get("affected_entities", [])
                    if e["type"] == "bom"
                ]
                source_clause_id = next(
                    (
                        UUID(e["id"])
                        for e in alert_data.get("affected_entities", [])
                        if e["type"] == "clause"
                    ),
                    None,
                )

                new_alert = Alert(
                    project_id=project_id,
                    analysis_id=new_analysis.id,
                    severity=AlertSeverity[alert_data.get("severity", "LOW").upper()],
                    rule_id=alert_data.get("rule_id"),
                    title=f"Inconsistency Detected: {alert_data.get('rule_id')}",  # A more descriptive title can be generated
                    message=alert_data.get("message", "No message provided."),
                    suggested_action=alert_data.get("suggested_action"),
                    source_clause_id=source_clause_id,
                    affected_document_ids=affected_document_ids,
                    affected_wbs_ids=affected_wbs_ids,
                    affected_bom_ids=affected_bom_ids,
                    requires_human_review=(
                        alert_data.get("severity", "LOW").upper() in ["CRITICAL", "HIGH"]
                    ),
                )
                tenant_db.add(new_alert)
            print(f"Created {len(alerts)} Alert records.")

            # 3. Update Project with latest coherence score
            project.coherence_score = int(coherence_score)
            project.last_analysis_at = new_analysis.completed_at
            tenant_db.add(project)
            print(f"Updated Project {project_id} with coherence score {coherence_score}.")

            await tenant_db.commit()
            print("Analysis results saved successfully.")
