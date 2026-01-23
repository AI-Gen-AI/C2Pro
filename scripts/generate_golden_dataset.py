# scripts/generate_golden_dataset.py
import asyncio
import json
import os
import re
from typing import List, Literal, Optional, Dict, Any

import openai
from pydantic import BaseModel, Field, ValidationError

# --- Configuration ---
# It's recommended to use a powerful model for structured JSON generation.
# Ensure the OPENAI_API_KEY environment variable is set.
LLM_MODEL = "gpt-4-turbo-preview"
OUTPUT_DIR = "tests/golden"
MAX_RETRIES = 3

# --- Pydantic Schemas for Validation ---
# These models ensure the LLM output conforms to our desired structure.

class ProjectMetadata(BaseModel):
    id: str = Field(..., description="Unique project identifier, e.g., 'project_002'")
    name: str = Field(..., description="Fictional but realistic project name.")
    type: Literal["Obra Civil", "Industrial", "Edificación"]
    complexity: Literal["Simple", "Medium", "Complex"]
    language: Literal["es", "en"]

class DocumentSummary(BaseModel):
    project_end_date: Optional[str] = Field(None, description="e.g., '2026-10-31'")
    total_value_eur: Optional[float] = None
    risk_contingency_pct: Optional[float] = None
    # Allow other flexible fields
    class Config:
        extra = "allow"

class InputDocuments(BaseModel):
    contract_text: str = Field(..., description="~3-4 paragraphs of contract text containing key entities.")
    schedule_summary: Optional[Dict[str, Any]] = Field(None, description="Simulated summary of project schedule.")
    budget_summary: Optional[Dict[str, Any]] = Field(None, description="Simulated summary of project budget.")

class Clause(BaseModel):
    clause_code: str = Field(..., description="e.g., 'CL-DEADLINE-01'")
    type: Literal["deadline", "penalty", "quality", "scope"]
    text: str = Field(..., description="Exact text extracted from the contract.")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Stakeholder(BaseModel):
    name: str
    role: str
    quadrant: Literal["Responsible", "Accountable", "Consulted", "Informed"]
    mention: Optional[str] = None

class CoherenceAlert(BaseModel):
    rule_id: str = Field(..., description="e.g., 'SCH-CTR-01' for Schedule-Contract conflict.")
    severity: Literal["warning", "critical"]
    description: str = Field(..., description="Explanation of the incoherence.")
    conflicting_elements: List[Dict[str, str]]

class ExpectedOutput(BaseModel):
    clauses: List[Clause]
    stakeholders: List[Stakeholder]
    coherence_alerts: List[CoherenceAlert]

class GoldenProject(BaseModel):
    project_metadata: ProjectMetadata
    input_documents: InputDocuments
    expected_output: ExpectedOutput

# --- Generation Scenarios ---

TEST_SCENARIOS = [
    {"id": "002", "type": "Obra Civil", "complexity": "Simple", "language": "es", "incoherence_type": "DateMismatch"},
    {"id": "003", "type": "Edificación", "complexity": "Medium", "language": "es", "incoherence_type": "BudgetOverrun"},
    {"id": "004", "type": "Industrial", "complexity": "Complex", "language": "en", "incoherence_type": "MissingStakeholder"},
    {"id": "005", "type": "Obra Civil", "complexity": "Medium", "language": "es", "incoherence_type": "None"},
    {"id": "006", "type": "Edificación", "complexity": "Complex", "language": "es", "incoherence_type": "DateMismatch"},
    {"id": "007", "type": "Industrial", "complexity": "Simple", "language": "en", "incoherence_type": "None"},
    {"id": "008", "type": "Obra Civil", "complexity": "Complex", "language": "es", "incoherence_type": "BudgetOverrun"},
    {"id": "009", "type": "Edificación", "complexity": "Simple", "language": "es", "incoherence_type": "MissingStakeholder"},
    {"id": "010", "type": "Industrial", "complexity": "Medium", "language": "es", "incoherence_type": "DateMismatch"},
]

# --- Core Logic ---

def slugify(value: str) -> str:
    """Simple slugify function."""
    return re.sub(r'[\s_]+', '-', value.lower())

async def generate_project_async(
    scenario: dict, client: openai.AsyncClient, schema: str
) -> Optional[GoldenProject]:
    """
    Generates and validates a single synthetic project using an LLM.
    Includes a retry mechanism for robustness.
    """
    system_prompt = (
        "You are a world-class Project Director specializing in creating test cases for construction auditing software. "
        "Your task is to generate realistic but fictional project data. Your response MUST be ONLY the valid JSON object, "
        "without any introductory text, explanations, or markdown fences like ```json ... ```."
    )
    
    user_prompt = (
        f"Generate a complete project JSON object following the provided schema. Ensure the project is of type '{scenario['type']}', "
        f"has a complexity of '{scenario['complexity']}', is in language '{scenario['language']}', "
        f"and has project id '{scenario['id']}'. CRITICAL: You must introduce a subtle incoherence of type '{scenario['incoherence_type']}'.\n\n"
        f"JSON Schema to follow:\n{schema}"
    )

    print(f"[{scenario['id']}] Generating project: {scenario['type']} ({scenario['complexity']}) with {scenario['incoherence_type']} issue...")

    for attempt in range(MAX_RETRIES):
        try:
            response = await client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.8,
            )
            
            content = response.choices[0].message.content
            # Validate the generated content against the Pydantic model
            project = GoldenProject.model_validate_json(content)
            
            # Additional check to ensure the generated ID matches the scenario
            if project.project_metadata.id != scenario['id']:
                print(f"[{scenario['id']}] Mismatch Warning: LLM generated id '{project.project_metadata.id}', expected '{scenario['id']}'. Overwriting.")
                project.project_metadata.id = scenario['id']

            print(f"[{scenario['id']}] Generation and validation successful on attempt {attempt + 1}.")
            return project

        except (ValidationError, json.JSONDecodeError) as e:
            print(f"[{scenario['id']}] Validation failed on attempt {attempt + 1}: {e}")
            if attempt == MAX_RETRIES - 1:
                print(f"[{scenario['id']}] Failed after {MAX_RETRIES} attempts. Skipping.")
                return None
        except Exception as e:
            print(f"[{scenario['id']}] An unexpected error occurred on attempt {attempt + 1}: {e}")
            if attempt == MAX_RETRIES - 1:
                print(f"[{scenario['id']}] Failed due to unexpected error. Skipping.")
                return None
    return None

async def main():
    """Main function to orchestrate the dataset generation."""
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    client = openai.AsyncClient()
    schema_json = json.dumps(GoldenProject.model_json_schema(), indent=2)

    tasks = [
        generate_project_async(scenario, client, schema_json)
        for scenario in TEST_SCENARIOS
    ]
    
    results = await asyncio.gather(*tasks)

    for i, project in enumerate(results):
        if project:
            scenario = TEST_SCENARIOS[i]
            file_name = f"project_{scenario['id']}_{slugify(scenario['type'])}.json"
            file_path = os.path.join(OUTPUT_DIR, file_name)
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(project.model_dump(), f, indent=2, ensure_ascii=False)
            
            print(f"Successfully saved '{file_path}'")

if __name__ == "__main__":
    print("Starting Golden Dataset Generation...")
    asyncio.run(main())
    print("Dataset generation complete.")
