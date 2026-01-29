# apps/api/src/coherence/router.py
import os

from fastapi import APIRouter, Depends

from .engine import CoherenceEngine
from .models import CoherenceResult, ProjectContext
from .rules import load_rules

# Create a new APIRouter instance
router = APIRouter(
    prefix="/v0/coherence",
    tags=["Coherence Engine"],
    responses={404: {"description": "Not found"}},
)


# ---- Dependency for the Coherence Engine ----
def get_coherence_engine():
    """
    Dependency to create and provide a CoherenceEngine instance.
    This loads the rules from the YAML file. In a real application, this
    would be cached or loaded once at startup.
    """
    # Construct the absolute path to the rules file
    rules_file_path = os.path.join(os.path.dirname(__file__), "initial_rules.yaml")

    if not os.path.exists(rules_file_path):
        # In a real app, this should probably raise a 500 Internal Server Error
        # or be handled more gracefully at startup.
        raise RuntimeError(f"Coherence rules file not found at {rules_file_path}")

    loaded_rules = load_rules(rules_file_path)
    return CoherenceEngine(rules=loaded_rules)


# ---- API Endpoint ----
@router.post(
    "/evaluate",
    response_model=CoherenceResult,
    summary="Evaluate Project Coherence",
    description="""
    Accepts a project's context and evaluates it against a predefined set of coherence rules.
    Returns a list of alerts and a calculated coherence score.
    """,
)
async def evaluate_project_coherence(
    project_context: ProjectContext, engine: CoherenceEngine = Depends(get_coherence_engine)
) -> CoherenceResult:
    """
    Evaluates the coherence of a project based on its context.

    - **project_context**: The project data to be evaluated.
    - **engine**: The coherence engine dependency that performs the evaluation.

    Returns the evaluation result, including alerts and a score.
    """
    result = engine.evaluate(project_context)
    return result
