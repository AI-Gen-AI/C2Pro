from __future__ import annotations
from typing import List, TypedDict
from uuid import UUID
import structlog
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from src.modules.projects.schemas import WBSItemCreate

logger = structlog.get_logger(__name__)

class Clause(BaseModel):
    """Represents a single clause from a contract."""
    id: UUID
    text: str
    type: str # e.g., "Scope", "Technical Specification"

class WBSItemList(BaseModel):
    """A list of WBS items."""
    items: List[WBSItemCreate]

class WBSAgentState(TypedDict):
    """Represents the state of the WBS generation agent."""
    contract_text: str
    wbs_items: WBSItemList
    attempt_count: int
    validation_errors: List[str]
    requires_approval: bool # To flag for human review

class WBSGeneratorAgent:
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
        self.workflow = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(WBSAgentState)

        graph.add_node("generator_node", self.generator_node)
        graph.add_node("auditor_node", self.auditor_node)

        graph.set_entry_point("generator_node")

        graph.add_conditional_edges(
            "auditor_node",
            self.should_retry,
            {
                "retry": "generator_node",
                "end": END
            }
        )
        graph.add_edge("generator_node", "auditor_node")

        return graph.compile()

    def generator_node(self, state: WBSAgentState) -> dict:
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

3.  **Structured Output:** You MUST format your output as a list of WBSItemCreate objects, conforming to the provided Pydantic schema.

**PREVIOUS ERRORS (if any):**
{validation_errors}

**INSTRUCTIONS:**

1.  Carefully analyze the contract text provided.
2.  If there are previous errors, focus on correcting them.
3.  Identify the key deliverables and work packages required to fulfill the contract.
4.  Organize these into the strict 4-level hierarchy.
5.  For each WBS item, create a unique `code` (e.g., "1.1.1", "1.2.3.4").
6.  Ensure every item has a `source_clause_id`.
7.  Generate a `WBSItemList` object containing a list of `WBSItemCreate` objects.
"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Contract Text:\n{contract_text}\n\nGenerate the WBS based on the contract text and correct any previous errors."),
        ])
        
        structured_llm = self.llm.with_structured_output(WBSItemList)

        chain = prompt | structured_llm

        wbs_item_list = chain.invoke({
            "contract_text": state["contract_text"],
            "validation_errors": "\n".join(state["validation_errors"]),
        })
        
        return {
            "wbs_items": wbs_item_list,
            "attempt_count": state["attempt_count"] + 1,
        }


    def auditor_node(self, state: WBSAgentState) -> dict:
        logger.info("Auditing generated WBS...")
        errors = []
        wbs_items = state["wbs_items"].items
        
        if not wbs_items:
            errors.append("WBS is empty.")
            return {"validation_errors": errors}

        item_codes = {item.code for item in wbs_items}

        # Rule 1: Hierarchy validation
        for item in wbs_items:
            if item.parent_code and item.parent_code not in item_codes:
                errors.append(f"Item '{item.name}' ({item.code}) has an invalid parent_code '{item.parent_code}'.")

        # Rule 2: Traceability validation
        for item in wbs_items:
            if not item.source_clause_id:
                errors.append(f"Item '{item.name}' ({item.code}) is missing a source_clause_id.")

        # Rule 3: Depth validation
        max_level = 0
        for item in wbs_items:
            if item.level > max_level:
                max_level = item.level
        if max_level < 3:
            errors.append(f"The WBS has a maximum depth of {max_level}, but a depth of at least 3 is required.")
        
        logger.info(f"Audit complete. Found {len(errors)} errors.")
        return {"validation_errors": errors}


    def should_retry(self, state: WBSAgentState) -> str:
        logger.info("Checking if retry is needed...")
        if state["validation_errors"] and state["attempt_count"] < 3:
            logger.info("Validation errors found. Retrying...")
            return "retry"
        
        if state["validation_errors"]:
            logger.warning("Max retries reached. Ending with errors.")
            state["requires_approval"] = True

        logger.info("Validation successful or max retries reached. Ending.")
        return "end"

    def run(self, contract_text: str) -> dict:
        initial_state: WBSAgentState = {
            "contract_text": contract_text,
            "wbs_items": WBSItemList(items=[]),
            "attempt_count": 0,
            "validation_errors": [],
            "requires_approval": False,
        }
        final_state = self.workflow.invoke(initial_state)
        return final_state