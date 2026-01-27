from __future__ import annotations
from typing import List, TypedDict
from uuid import UUID
import structlog
from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

# Import from the new domain models file
from src.procurement.domain.models import WBSItem, WBSItemList

logger = structlog.get_logger(__name__)

# This is an input DTO for this use case, not a core domain entity.
class ClauseDTO(BaseModel):
    """Represents a single clause from a contract, used as input for WBS generation."""
    id: UUID
    text: str
    type: str

# This is the state for the LangGraph orchestrator, belongs in the application layer.
class WBSGenerationState(TypedDict):
    """Represents the state of the WBS generation process."""
    contract_text: str
    wbs_items: WBSItemList
    attempt_count: int
    validation_errors: List[str]
    requires_approval: bool

class WBSGenerationService:
    """
    Application service to generate a Work Breakdown Structure using a self-correcting AI graph.
    """
    def __init__(self, llm: ChatAnthropic):
        # The LLM adapter is injected, following Clean Architecture.
        self.llm = llm
        self.workflow = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(WBSGenerationState)
        graph.add_node("generator_node", self.generator_node)
        graph.add_node("auditor_node", self.auditor_node)
        graph.set_entry_point("generator_node")
        graph.add_conditional_edges(
            "auditor_node",
            self.should_retry,
            {"retry": "generator_node", "end": END}
        )
        graph.add_edge("generator_node", "auditor_node")
        return graph.compile()

    def generator_node(self, state: WBSGenerationState) -> dict:
        logger.info(f"Generating WBS (Attempt: {state['attempt_count'] + 1})")
        system_prompt = """
You are an expert in project management and civil engineering, specialized in creating Work Breakdown Structures (WBS) for large-scale EPC (Engineering, Procurement, and Construction) projects. Your task is to analyze the provided contract text to generate a detailed, hierarchical WBS.

**CRITICAL REQUIREMENTS:**

1.  **Strict 4-Level Hierarchy:** You MUST follow this structure:
    *   **Level 1: Project Root:** A single top-level item representing the entire project.
    *   **Level 2: Phases:** High-level project phases (e.g., Engineering, Procurement, Construction, Commissioning).
    *   **Level 3: Major Deliverables:** Tangible and verifiable outcomes within each phase (e.g., "Site Preparation", "Foundation Works").
    *   **Level 4: Work Packages:** The lowest level of detail, representing a group of related tasks that can be assigned and executed (e.g., "Excavation and Earthworks", "Concrete Pouring").

2.  **Legal Traceability:** This is non-negotiable. Every single WBS item you generate, at every level, MUST be justified by a specific contract clause. You must include the `source_clause_id` for each item, linking it back to a clause in the contract.

3.  **Structured Output:** You MUST format your output as a JSON object conforming to the `WBSItemList` Pydantic schema, which contains a list of `WBSItem` objects.
"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Contract Text:\n{contract_text}\n\nGenerate the WBS based on the contract text and correct any previous validation errors listed below:\n{validation_errors}"),
        ])
        structured_llm = self.llm.with_structured_output(WBSItemList)
        chain = prompt | structured_llm
        wbs_item_list = chain.invoke({
            "contract_text": state["contract_text"],
            "validation_errors": "\n".join(state["validation_errors"]),
        })
        return {"wbs_items": wbs_item_list, "attempt_count": state["attempt_count"] + 1}

    def auditor_node(self, state: WBSGenerationState) -> dict:
        logger.info("Auditing generated WBS...")
        errors = []
        if not state["wbs_items"] or not state["wbs_items"].items:
            errors.append("WBS is empty. The LLM failed to generate any items.")
            return {"validation_errors": errors}
        
        wbs_items = state["wbs_items"].items
        item_codes = {item.code for item in wbs_items}

        for item in wbs_items:
            if item.parent_code and item.parent_code not in item_codes:
                errors.append(f"Item '{item.name}' ({item.code}) has an invalid parent_code '{item.parent_code}'.")
            if not item.source_clause_id:
                errors.append(f"Item '{item.name}' ({item.code}) is missing a 'source_clause_id'.")
        
        max_level = max((item.level for item in wbs_items), default=0)
        if max_level < 3:
            errors.append(f"The WBS has a maximum depth of {max_level}, but a depth of at least 3 is required.")
        
        logger.info(f"Audit complete. Found {len(errors)} errors.")
        return {"validation_errors": errors}

    def should_retry(self, state: WBSGenerationState) -> str:
        if state["validation_errors"] and state["attempt_count"] < 3:
            logger.info("Validation errors found. Retrying generation.", errors=state["validation_errors"])
            return "retry"
        if state["validation_errors"]:
            logger.warning("Max retries reached. Ending generation with errors.", errors=state["validation_errors"])
            state["requires_approval"] = True
        logger.info("Validation successful or max retries reached. Ending generation.")
        return "end"

    def run(self, contract_text: str) -> dict:
        """Entry point to run the WBS generation graph."""
        initial_state: WBSGenerationState = {
            "contract_text": contract_text,
            "wbs_items": WBSItemList(items=[]),
            "attempt_count": 0,
            "validation_errors": [],
            "requires_approval": False,
        }
        final_state = self.workflow.invoke(initial_state)
        return final_state
