# tests/accuracy/test_regression.py

import asyncio
import json
import glob
import os
from typing import List, Literal, Optional, Dict, Any

import pytest
from pydantic import BaseModel, Field

# Assuming scorers.py is in tests/utils/
from tests.utils.scorers import (
    score_string_similarity,
    score_object_list,
)

# --- Configuration ---
AI_ACCURACY_THRESHOLD = 0.85
# This assumes the test is run from the root of the project
GOLDEN_DATASET_PATH = "tests/golden/*.json"

# --- Pydantic Schemas for Validation (Copied from generation script) ---
# In a real project, these would be in a shared 'schemas' module.
class ProjectMetadata(BaseModel):
    id: str
    name: str
    type: str
    complexity: str
    language: str

class InputDocuments(BaseModel):
    contract_text: str
    schedule_summary: Optional[Dict[str, Any]] = None
    budget_summary: Optional[Dict[str, Any]] = None

class Clause(BaseModel):
    clause_code: str
    type: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Stakeholder(BaseModel):
    name: str
    role: str
    quadrant: str
    mention: Optional[str] = None

class CoherenceAlert(BaseModel):
    rule_id: str
    severity: str
    description: str
    conflicting_elements: List[Dict[str, str]]

class ExpectedOutput(BaseModel):
    clauses: List[Clause]
    stakeholders: List[Stakeholder]
    coherence_alerts: List[CoherenceAlert]

class GoldenProject(BaseModel):
    project_metadata: ProjectMetadata
    input_documents: InputDocuments
    expected_output: ExpectedOutput

# --- Mock AI Service ---
# This function simulates the real AI pipeline for testing purposes.
# It returns a slightly modified version of the expected output to test the scorers.

async def mock_extraction_pipeline(golden_output: ExpectedOutput) -> dict:
    """
    Simulates the output of a real AI pipeline.
    Introduces slight variations to test fuzzy matching.
    """
    await asyncio.sleep(0.1) # Simulate network latency
    
    actual_output = golden_output.model_dump()

    # Simulate minor string changes in a stakeholder's name
    if actual_output["stakeholders"]:
        actual_output["stakeholders"][0]["name"] = actual_output["stakeholders"][0]["name"].replace("Principal", "Princ.")

    # Simulate missing one clause (False Negative)
    if len(actual_output["clauses"]) > 1:
        actual_output["clauses"].pop(-1)

    # Simulate an extra, hallucinated alert (False Positive)
    actual_output["coherence_alerts"].append({
        "rule_id": "FP-ALERT-01",
        "severity": "warning",
        "description": "This is a hallucinated alert from the mock AI.",
        "conflicting_elements": []
    })
    
    return actual_output

# --- Item-specific Scorers ---
def score_stakeholder_item(expected: Dict, actual: Dict) -> float:
    """Calculates an aggregate score for a single stakeholder item."""
    s_name = score_string_similarity(expected['name'], actual['name'])
    s_role = score_string_similarity(expected['role'], actual['role'])
    s_quadrant = 1.0 if expected['quadrant'] == actual['quadrant'] else 0.0
    # Average score for the item's attributes
    return (s_name + s_role + s_quadrant) / 3.0

def score_clause_item(expected: Dict, actual: Dict) -> float:
    """Calculates an aggregate score for a single clause item."""
    s_text = score_string_similarity(expected['text'], actual['text'])
    s_type = 1.0 if expected['type'] == actual['type'] else 0.0
    return (s_text + s_type) / 2.0

def score_alert_item(expected: Dict, actual: Dict) -> float:
    """Calculates an aggregate score for a single alert item."""
    s_desc = score_string_similarity(expected['description'], actual['description'])
    s_sev = 1.0 if expected['severity'] == actual['severity'] else 0.0
    return (s_desc + s_sev) / 2.0
    
# --- Test Suite ---

def load_golden_files():
    """Loads all golden dataset file paths."""
    return glob.glob(GOLDEN_DATASET_PATH)

# A class to hold results across parametrized tests
class TestResults:
    project_scores = []
    detailed_reports = []

@pytest.mark.ai_accuracy
class TestAIAccuracy:
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("golden_file_path", load_golden_files())
    async def test_project_accuracy(self, golden_file_path):
        """
        Tests a single project from the golden dataset against the mock AI.
        """
        # 1. Load and parse the golden dataset file
        with open(golden_file_path, 'r', encoding='utf-8') as f:
            project_data = json.load(f)
        
        golden_project = GoldenProject.model_validate(project_data)
        expected = golden_project.expected_output

        # 2. Run the mock AI extraction pipeline
        actual_dict = await mock_extraction_pipeline(expected)

        # 3. Score the results for each category
        clauses_result = score_object_list(
            expected.model_dump()['clauses'], actual_dict['clauses'], 'clause_code', score_clause_item
        )
        stakeholders_result = score_object_list(
            expected.model_dump()['stakeholders'], actual_dict['stakeholders'], 'name', score_stakeholder_item
        )
        alerts_result = score_object_list(
            expected.model_dump()['coherence_alerts'], actual_dict['coherence_alerts'], 'rule_id', score_alert_item
        )

        # 4. Calculate an overall score for the project (simple average for now)
        project_score = (clauses_result['final_score'] + stakeholders_result['final_score'] + alerts_result['final_score']) / 3.0
        
        # 5. Store results for the final report
        report = {
            "project_id": golden_project.project_metadata.id,
            "overall_score": project_score,
            "clauses": clauses_result,
            "stakeholders": stakeholders_result,
            "alerts": alerts_result,
        }
        TestResults.project_scores.append(project_score)
        TestResults.detailed_reports.append(report)
        
        # Optional: Fail fast if a single project is exceptionally bad
        assert project_score > 0.5, f"Project {golden_project.project_metadata.id} scored unacceptably low."

    def test_report_and_assert_global_accuracy(self):
        """
        This final test runs after all others, calculates the global average,
        prints a report, and asserts the final quality gate.
        """
        if not TestResults.project_scores:
            pytest.skip("No AI accuracy tests were run.")
            
        global_accuracy = sum(TestResults.project_scores) / len(TestResults.project_scores)

        print("\n--- AI Accuracy Regression Report ---")
        print(f"\nGlobal Average Accuracy: {global_accuracy:.2%}")
        print(f"Quality Gate Threshold: {AI_ACCURACY_THRESHOLD:.2%}")
        
        if global_accuracy < AI_ACCURACY_THRESHOLD:
            print("\nProjects with low scores:")
            for report in TestResults.detailed_reports:
                if report['overall_score'] < AI_ACCURACY_THRESHOLD:
                    print(f"  - Project: {report['project_id']} | Score: {report['overall_score']:.2%}")
                    # In a real scenario, you might print more details from the report object
        
        print("\n--- End of Report ---")

        assert global_accuracy >= AI_ACCURACY_THRESHOLD, f"Global AI accuracy ({global_accuracy:.2%}) is below the threshold of {AI_ACCURACY_THRESHOLD:.2%}"
