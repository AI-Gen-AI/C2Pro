import os
import json
from pathlib import Path

EXTERNAL_DIR = Path("D:/Abengoa/Ofertas y Proyectos")
OUTPUT_FILE = Path("docs/ABENGOA_PROJECTS_DB.json")

# Core keywords to match different file dimensions
KEYWORDS_CONTRACT = ["contrato", "contract", "bases", "pliego", "adjudicacion", "adjudicación", "agreement", "pliego_condiciones"]
KEYWORDS_BUDGET = ["presupuesto", "costes", "coste", "boq", "desglose", "comparativa", "comparativo", "medicion", "medición", "budget", "partidas", "estimate"]
KEYWORDS_SCHEDULE = ["cronograma", "plazo", "duracion", "duración", "schedule", "gantt", "milestones", "planning", "planificación", "planificacion"]
KEYWORDS_RISK = ["formg-121", "formg-061", "riesgo", "risk", "ar_", "ar-", "ar ", "ar.pdf", "ar.doc", "ar.xls", "contingency", "incertidumbres"]


def clean_relative_path(p):
    return str(Path(p).relative_to(EXTERNAL_DIR)) if EXTERNAL_DIR in Path(p).parents or Path(p) == EXTERNAL_DIR else str(p)


def crawl_and_cluster():
    if not EXTERNAL_DIR.exists():
        print(f"Error: {EXTERNAL_DIR} does not exist or is not accessible.")
        return

    print(f"Recursively scanning and clustering projects in {EXTERNAL_DIR}...")
    
    # Map from project_key -> clustered files
    packages = {}
    
    total_files = 0
    
    for root, dirs, files in os.walk(EXTERNAL_DIR):
        root_path = Path(root)
        
        # Determine country and project folder names
        relative = root_path.relative_to(EXTERNAL_DIR)
        parts = relative.parts
        
        if len(parts) == 0:
            continue
            
        country = parts[0]
        project_folder = parts[1] if len(parts) > 1 else "Root / Shared"
        
        for file in files:
            file_lower = file.lower()
            file_path = root_path / file
            
            # Check extension (mainly focus on documents and spreadsheets)
            if not file_lower.endswith(('.pdf', '.xls', '.xlsx', '.doc', '.docx')):
                continue
                
            total_files += 1
            
            # Classify file
            category = None
            if any(kw in file_lower for kw in KEYWORDS_RISK):
                category = "risk"
            elif any(kw in file_lower for kw in KEYWORDS_CONTRACT):
                category = "contract"
            elif any(kw in file_lower for kw in KEYWORDS_BUDGET):
                category = "budget"
            elif any(kw in file_lower for kw in KEYWORDS_SCHEDULE):
                category = "schedule"
                
            if category is None:
                continue
                
            # Initialize project package at the project level
            pkg_key = f"{country}||{project_folder}"
            if pkg_key not in packages:
                project_dir = EXTERNAL_DIR / country / project_folder if len(parts) > 1 else EXTERNAL_DIR / country
                packages[pkg_key] = {
                    "directory": str(project_dir),
                    "relative_directory": str(Path(country) / project_folder) if len(parts) > 1 else country,
                    "country": country,
                    "project_folder": project_folder,
                    "contract_files": [],
                    "budget_files": [],
                    "schedule_files": [],
                    "risk_files": []
                }
                
            try:
                stat = file_path.stat()
                file_info = {
                    "name": file,
                    "full_path": str(file_path),
                    "relative_path": clean_relative_path(file_path),
                    "size_bytes": stat.st_size,
                    "modified": stat.st_mtime
                }
                packages[pkg_key][f"{category}_files"].append(file_info)
            except Exception as e:
                print(f"Warning: Failed to read stats for {file_path}: {e}")

    print(f"Total files scanned: {total_files}")
    print(f"Total unique project folders with target files: {len(packages)}")
    
    # Filter for project directories that have meaningful combinations
    # For example, they have a contract/risk file and a budget/schedule file
    rich_projects = []
    any_projects = []
    
    for pkg in packages.values():
        has_contract_or_risk = len(pkg["contract_files"]) > 0 or len(pkg["risk_files"]) > 0
        has_budget_or_schedule = len(pkg["budget_files"]) > 0 or len(pkg["schedule_files"]) > 0
        
        if has_contract_or_risk and has_budget_or_schedule:
            rich_projects.append(pkg)
        if len(pkg["contract_files"]) > 0 or len(pkg["risk_files"]) > 0 or len(pkg["budget_files"]) > 0 or len(pkg["schedule_files"]) > 0:
            any_projects.append(pkg)

    print(f"Rich projects (Contracts/Risks + Budgets/Schedules): {len(rich_projects)}")
    print(f"Total projects with at least one target document: {len(any_projects)}")
    
    # Write output DB file
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "rich_projects": rich_projects,
            "all_target_projects": any_projects,
            "metadata": {
                "total_directories_mapped": len(packages),
                "total_scanned_files": total_files
            }
        }, f, indent=2, ensure_ascii=False)
        
    print(f"Unified project database successfully written to {OUTPUT_FILE}")


if __name__ == "__main__":
    crawl_and_cluster()
