import os
import re
import sys
import codecs

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())

legacy_files_with_tasks = [
    r"docs\archive\plans\ux-implementation\QUICK_REFERENCE.md",
    r"docs\archive\tasks\CE-P0-06_TASK_TRACKER.md",
    r"docs\archive\plans\Clerk\CLERK_IMPLEMENTATION_CHECKLIST_2026-02-17.md",
    r"docs\archive\roadmaps\ROADMAP_v2.2.0.md",
    r"docs\archive\tasks\CE-P0-06_STAGING_MIGRATIONS_PLAN.md",
    r"docs\archive\plans\Clerk\IMPLEMENTATION_GUIDE.md",
    r"docs\archive\roadmaps\ROADMAP_v2.3.0.md",
    r"docs\archive\plans\Clerk\README.md",
    r"docs\archive\sprints\SPRINT_1_COMPLETED.md",
    r"docs\archive\plans\tdd-testing\TDD_WEEK2_TESTS.md",
    r"docs\archive\tasks\CE-P0-06_QUICK_START.md",
    r"docs\archive\migrations\MIGRATION_COMPLETED.md",
    r"docs\archive\tasks\CTO_GATES_VERIFICATION_PLAN.md",
    r"docs\archive\plans\Clerk\01_FRONTEND_ENV_SETUP.md",
    r"docs\archive\plans\ux-implementation\README.md",
    r"docs\archive\plans\tdd-testing\TDD_QUICK_REFERENCE.md",
    r"docs\archive\plans\tdd-testing\TDD_WEEK1_TESTS.md",
    r"docs\archive\planning\2026-02\PLAN_LANGGRAPH_TDD_TESTPLAN_I13_2026-02-15.md",
    r"docs\archive\plans\tdd-testing\I7_RISK_SCORING_IMPLEMENTATION_CHECKLIST_2026-02-16.md",
    r"docs\archive\tasks\CE-P0-05_TASK_SUMMARY.md",
    r"docs\archive\tasks\CE-P0-06_IMPLEMENTATION_COMPLETE.md",
    r"docs\wireframes\05-stakeholders.md",
    r"docs\archive\plans\Clerk\00_CLERK_SETUP_GUIDE.md",
    r"docs\archive\tasks\CTO_GATES_QUICKSTART.md",
    r"docs\archive\duplicates\START_HERE (1).md",
    r"docs\archive\plans\Clerk\START_HERE.md",
    r"docs\archive\tasks\TEST_RESULTS_2026-01-06.md",
    r"docs\archive\plans\tdd-testing\I12_OBSERVABILITY_EVAL_100_COVERAGE_PLAN_2026-02-18.md",
    r"docs\archive\plans\ux-implementation\MASTER_PLAN_v1.0.md",
    r"docs\archive\reports\2026-03\SPRINT_S2_PROGRESS_SUMMARY.md",
    r"docs\archive\reports\2026-03\TS-E2E-SEC-TNT-001_IMPLEMENTATION_SUMMARY.md",
    r"docs\archive\tasks\FRONTEND_TYPE_SAFETY_CE-S2-011.md",
    r"docs\archive\implementation\supabase\S0.3_TEST_IMPLEMENTATION_SUMMARY.md",
    r"docs\archive\planning\2026-02\TACTICAL_BOARD_S4_S6_2026-02-14.md",
    r"docs\archive\changelogs\CHANGELOG_2026-01-06.md",
    r"docs\archive\reports\2026-03\TS-E2E-SEC-TNT-001_GREEN_PHASE_STATUS.md"
]

def extract_tasks_from_legacy():
    all_tasks = []
    task_id_counter = 1
    
    for file_path in legacy_files_with_tasks:
        if not os.path.exists(file_path):
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                for line in lines:
                    line = line.strip()
                    # Match [ ] or TODO
                    is_task = False
                    description = ""
                    
                    if line.startswith("- [ ]"):
                        is_task = True
                        description = line[5:].strip()
                    elif "TODO:" in line.upper():
                        is_task = True
                        description = line.split("TODO:", 1)[1].strip()
                        
                    if is_task and description:
                        all_tasks.append({
                            "ID": f"LEG-{task_id_counter:03d}",
                            "File": file_path,
                            "Description": description
                        })
                        task_id_counter += 1
        except Exception:
            pass
            
    return all_tasks

if __name__ == "__main__":
    tasks = extract_tasks_from_legacy()
    print("# Consolidated Legacy Pending Tasks")
    print(f"**Total Tasks Found:** {len(tasks)}\n")
    print("| Task ID | File | Description |")
    print("| :--- | :--- | :--- |")
    for t in tasks:
        # Clean description of markdown table characters
        clean_desc = t['Description'].replace("|", "\\|")
        print(f"| {t['ID']} | `{t['File']}` | {clean_desc} |")
