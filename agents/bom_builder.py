
from __future__ import annotations
from typing import List, TypedDict
from uuid import UUID
import structlog
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from src.modules.projects.schemas import WBSItemCreate, BOMItemCreate

logger = structlog.get_logger(__name__)

class BudgetItem(BaseModel):
    """Represents a single item from the project budget."""
    id: UUID
    name: str
    code: str
    amount: float

class BOMItemList(BaseModel):
    """A list of BOM items."""
    items: List[BOMItemCreate]

class BOMAgentState(TypedDict):
    """Represents the state of the BOM generation agent."""
    wbs_items: List[WBSItemCreate]
    budget_items: List[BudgetItem]
    bom_items: List[BOMItemCreate]

class BOMBuilderAgent:
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
        self.workflow = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(BOMAgentState)
        graph.add_node("materializer_node", self.materializer_node)
        graph.set_entry_point("materializer_node")
        graph.add_edge("materializer_node", END)
        return graph.compile()

    def materializer_node(self, state: BOMAgentState) -> dict:
        logger.info("Materializing BOM from WBS...")

        leaf_wbs_items = [item for item in state["wbs_items"] if not any(i.parent_code == item.code for i in state["wbs_items"])]
        
        all_bom_items = []
        
        batch_size = 5 # Process 5 WBS items at a time to avoid large context windows
        for i in range(0, len(leaf_wbs_items), batch_size):
            batch = leaf_wbs_items[i:i+batch_size]
            
            system_prompt = """
You are a Senior Supply Chain Architect and expert in EPC projects. Your task is to analyze a list of Work Breakdown Structure (WBS) work packages and a list of budget items to create a detailed Bill of Materials (BOM).

**CRITICAL REQUIREMENTS:**

1.  **Material Deduction:** For each WBS work package, deduce the necessary materials, equipment, and services required for its execution.
2.  **Logistical Inference:** For each BOM item, you MUST estimate the following logistical parameters:
    *   `production_time_days`: Estimated time for manufacturing.
    *   `transit_time_days`: Estimated time for transportation. Assume international shipping for complex or specialized items.
    *   `lead_time_days`: The total lead time, which should be the sum of production and transit times, plus a small buffer (e.g., 10%).
3.  **Budgetary Linking:** For each BOM item, you MUST try to find a corresponding budget item from the provided list. Base the match on name/code similarity. If a clear match is found, set the `budget_item_id`. If no clear match is found, leave `budget_item_id` as `null`.
4.  **Traceability:** Each BOM item MUST inherit the `contract_clause_id` from its parent WBS item.
5.  **Structured Output:** You MUST format your output as a `BOMItemList` object, which contains a list of `BOMItemCreate` objects.

**INPUT:**

*   **WBS Work Packages:**
    {wbs_items}
*   **Budget Items:**
    {budget_items}

**INSTRUCTIONS:**

1.  For each WBS work package, generate a list of required BOM items.
2.  For each BOM item, estimate the lead times as described above.
3.  For each BOM item, find the corresponding `budget_item_id`.
4.  For each BOM item, set the `contract_clause_id` to the `source_clause_id` of the parent WBS item.
5.  Return a single `BOMItemList` object containing all the generated BOM items for this batch.
"""

            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("user", "Generate the BOM for the provided WBS work packages and budget items."),
            ])
            
            structured_llm = self.llm.with_structured_output(BOMItemList)

            chain = prompt | structured_llm

            wbs_text = "\n".join([f"Code: {item.code}, Name: {item.name}, Description: {item.description}, Clause ID: {item.source_clause_id}" for item in batch])
            budget_text = "\n".join([f"ID: {item.id}, Code: {item.code}, Name: {item.name}, Amount: {item.amount}" for item in state["budget_items"]])

            bom_item_list = chain.invoke({
                "wbs_items": wbs_text,
                "budget_items": budget_text,
            })
            
            all_bom_items.extend(bom_item_list.items)

        return {"bom_items": all_bom_items}


    def run(self, wbs_items: List[WBSItemCreate], budget_items: List[BudgetItem]) -> dict:
        initial_state = {
            "wbs_items": wbs_items,
            "budget_items": budget_items,
            "bom_items": [],
        }
        return self.workflow.invoke(initial_state)

