import os
import sys
import json
from typing import Dict, Any, Tuple

# Temporarily add project root to sys.path to resolve imports
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, "..")) # Go up from scripts to c2pro root
sys.path.insert(0, project_root)

# Import necessary components from the coherence module
from apps.api.src.modules.coherence.engine import CoherenceEngine
from apps.api.src.modules.coherence.rules import load_rules
from apps.api.src.modules.coherence.models import ProjectContext, CoherenceResult

def get_expected_score_range(project_id: str) -> Tuple[float, float]:
    """
    Defines the expected score range for calibration projects based on scoring_methodology_v1.md.
    """
    if project_id == "calibration-excellent-001":
        return (95.0, 100.0)
    elif project_id == "calibration-minor-002":
        return (75.0, 85.0)
    elif project_id == "calibration-major-003":
        return (50.0, 65.0)
    else:
        raise ValueError(f"Unknown project_id for calibration: {project_id}")

def run_calibration():
    """
    Runs the automated calibration script for the Coherence Engine.
    """
    print("--- Starting Coherence Engine Calibration ---")

    # 1. Load rules
    rules_file_path = os.path.join(project_root, "apps/api/src/modules/coherence/initial_rules.yaml")
    if not os.path.exists(rules_file_path):
        print(f"Error: Rules file not found at {rules_file_path}")
        sys.exit(1)
    
    loaded_rules = load_rules(rules_file_path)
    engine = CoherenceEngine(rules=loaded_rules)
    print(f"Loaded {len(loaded_rules)} rules.")

    # 2. Load calibration dataset projects
    calibration_dataset_path = os.path.join(project_root, "apps/api/tests/coherence/calibration_dataset")
    if not os.path.isdir(calibration_dataset_path):
        print(f"Error: Calibration dataset directory not found at {calibration_dataset_path}")
        sys.exit(1)

    project_files = [f for f in os.listdir(calibration_dataset_path) if f.endswith(".json")]
    if not project_files:
        print("No calibration project files found.")
        sys.exit(1)

    results = []
    total_pass = 0
    total_fail = 0

    print(f"Evaluating {len(project_files)} calibration projects...")
    for pf in sorted(project_files):
        file_path = os.path.join(calibration_dataset_path, pf)
        with open(file_path, 'r', encoding='utf-8') as f:
            project_data = json.load(f)
        
        project_context = ProjectContext(**project_data)
        expected_min, expected_max = get_expected_score_range(project_context.id)

        try:
            coherence_result = engine.evaluate(project_context)
            actual_score = coherence_result.score
            
            status = "PASS" if expected_min <= actual_score <= expected_max else "FAIL"
            if status == "PASS":
                total_pass += 1
            else:
                total_fail += 1

            results.append({
                "project_id": project_context.id,
                "actual_score": actual_score,
                "expected_range": f"[{expected_min:.1f}-{expected_max:.1f}]",
                "status": status,
                "alerts_count": len(coherence_result.alerts)
            })
        except Exception as e:
            results.append({
                "project_id": project_context.id,
                "actual_score": "ERROR",
                "expected_range": f"[{expected_min:.1f}-{expected_max:.1f}]",
                "status": "ERROR",
                "error_message": str(e)
            })
            total_fail += 1 # Count errors as fails


    print("\n--- Calibration Report ---")
    for res in results:
        status_color = "\033[92m" if res["status"] == "PASS" else "\033[91m" # Green/Red
        reset_color = "\033[0m"
        print(f"Project: {res['project_id']:<30} | Score: {res['actual_score']:.2f} | Expected: {res['expected_range']} | {status_color}{res['status']}{reset_color} | Alerts: {res['alerts_count']}")
        if res["status"] == "ERROR":
            print(f"  Error: {res['error_message']}")

    print(f"\nSummary: {total_pass} PASS, {total_fail} FAIL")

    if total_fail > 0:
        print("\nCalibration FAILED: Adjust weights in apps/api/src/modules/coherence/config.py")
        sys.exit(1)
    else:
        print("\nCalibration PASSED: All projects within expected score ranges.")
        sys.exit(0)

if __name__ == "__main__":
    run_calibration()
