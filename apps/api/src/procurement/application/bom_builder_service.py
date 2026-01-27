from __future__ import annotations
from typing import List, TypedDict
from uuid import UUID
import structlog
from pydantic import BaseModel
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

# Import from the new domain models file
from src.procurement.domain.models import WBSItem, BOMItem, BOMItemList, BudgetItem

logger = structlog.get_logger(__name__)

# This is the state for the LangGraph orchestrator, belongs in the application layer.
class BOMBuildingState(TypedDict):
    """Represents the state of the BOM generation process."""
    wbs_items: List[WBSItem]
    budget_items: List[BudgetItem]
    bom_items: List[BOMItem]

class BOMBuilderService:
    """
    Application service to build a Bill of Materials from a WBS using an AI graph.
    """
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
        self.workflow = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(BOMBuildingState)
        graph.add_node("materializer_node", self.materializer_node)
        graph.set_entry_point("materializer_node")
        graph.add_edge("materializer_node", END)
        return graph.compile()

    def materializer_node(self, state: BOMBuildingState) -> dict:
        logger.info("Materializing BOM from WBS...")

        wbs_codes_that_are_parents = {item.parent_code for item in state["wbs_items"] if item.parent_code}
        leaf_wbs_items = [item for item in state["wbs_items"] if item.code not in wbs_codes_that_are_parents]
        
        all_bom_items = []
        
        batch_size = 5
        for i in range(0, len(leaf_wbs_items), batch_size):
            batch = leaf_wbs_items[i:i+batch_size]
            
            system_prompt = """
You are a Senior Supply Chain Architect and expert in EPC projects. Your task is to analyze a list of Work Breakdown Structure (WBS) work packages and a list of budget items to create a detailed Bill of Materials (BOM).

**CRITICAL REQUIREMENTS:**

1.  **Material Deduction:** For each WBS work package, deduce the necessary materials, equipment, and services required for its execution.
2.  **Logistical Inference:** For each BOM item, you MUST estimate `production_time_days`, `transit_time_days`, and `lead_time_days`.
3.  **Budgetary Linking:** For each BOM item, attempt to find a corresponding `budget_item_id` from the provided list.
4.  **Traceability:** Each BOM item MUST inherit the `contract_clause_id` from its parent WBS item's `source_clause_id`.
5.  **Structured Output:** You MUST format your output as a `BOMItemList` object containing a list of `BOMItem` objects.

**INPUT:**
*   **WBS Work Packages:** {wbs_items}
*   **Budget Items:** {budget_items}

**INSTRUCTIONS:**
1.  For each WBS work package, generate a list of required BOM items.
2.  Estimate lead times for each BOM item.
3.  Find the corresponding `budget_item_id` for each BOM item.
4.  Set the `contract_clause_id` from the parent WBS item.
5.  Return a single `BOMItemList` object.
"""
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("user", "Generate the BOM for the provided WBS work packages and budget items."),
            ])
            structured_llm = self.llm.with_structured_output(BOMItemList)
            chain = prompt | structured_llm

            wbs_text = "\n".join([f"Code: {item.code}, Name: {item.name}, Desc: {item.description}, Clause ID: {item.source_clause_id}" for item in batch])
            budget_text = "\n".join([f"ID: {item.id}, Code: {item.code}, Name: {item.name}, Amount: {item.amount}" for item in state["budget_items"]])

            bom_item_list = chain.invoke({"wbs_items": wbs_text, "budget_items": budget_text})
            
            for bom_item in bom_item_list.items:
                if batch:
                    bom_item.project_id = batch[0].project_id
            
            all_bom_items.extend(bom_item_list.items)

        return {"bom_items": all_bom_items}

    def run(self, wbs_items: List[WBSItem], budget_items: List[BudgetItem]) -> dict:
        """Entry point to run the BOM building graph."""
        initial_state: BOMBuildingState = {
            "wbs_items": wbs_items,
            "budget_items": budget_items,
            "bom_items": [],
        }
        return self.workflow.invoke(initial_state)
