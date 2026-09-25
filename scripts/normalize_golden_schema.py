import os
import json
from pathlib import Path

GOLDEN_DIR = Path("tests/golden")


def get_canonical_budget(budget_summary, filename):
    # Defaults
    contract_total = None
    budget_total = None
    currency = "EUR"
    partner_shares = None

    # Determine currency
    keys_str = "".join(budget_summary.keys()).lower()
    if "usd" in keys_str:
        currency = "USD"
    elif "kwd" in keys_str:
        currency = "KWD"
    elif "mxn" in keys_str:
        currency = "MXN"
    elif "brl" in keys_str:
        currency = "BRL"
    
    # Specific project overrides or heuristics:
    filename_upper = filename.upper()
    if "MONFORTE" in filename_upper:
        contract_total = budget_summary.get("revenue_target")
        budget_total = budget_summary.get("internal_cost_estimate")
    elif "LA_ROBLA" in filename_upper:
        contract_total = budget_summary.get("total_value_eur")
        budget_total = budget_summary.get("inabensa_sub_budget_total_eur")
        partner_shares = {
            "Inabensa": 22194629.66,
            "material_sheet": 30382025.38
        }
    elif "CAMPILLOS" in filename_upper:
        contract_total = budget_summary.get("total_investment_eur")
        budget_total = budget_summary.get("budget_total_eur")
    elif "MANDEM" in filename_upper:
        contract_total = budget_summary.get("awarded_value_eur")
        budget_total = budget_summary.get("target_procurement_budget_eur")
    elif "RIYADH_METRO" in filename_upper:
        contract_total = budget_summary.get("total_value_usd")
        budget_total = contract_total - budget_summary.get("contingency_usd", 0) if contract_total else None
    else:
        # Generic heuristic
        for k, v in budget_summary.items():
            if k in ["total_value_eur", "total_value_usd", "total_value_mxn", "total_value_brl", "total_value_kwd", "total_investment_eur", "total_value"]:
                contract_total = v
            if k in ["budget_total_eur", "budget_total_usd", "budget_total_mxn", "budget_total_brl", "budget_total_kwd", "budget_total", "internal_cost_estimate", "target_procurement_budget_eur", "inabensa_sub_budget_total_eur"]:
                budget_total = v
                
        # Fallbacks: if still None, sum line_items
        if contract_total is None:
            contract_total = budget_summary.get("total_value")
        if budget_total is None:
            budget_total = budget_summary.get("budget_total")
            
        if budget_total is None and "line_items" in budget_summary:
            total_sum = 0
            has_costs = False
            for item in budget_summary["line_items"]:
                cost = item.get("cost")
                if cost is not None and isinstance(cost, (int, float)):
                    if "total" not in item.get("name", "").lower():
                        total_sum += cost
                        has_costs = True
            if has_costs:
                budget_total = total_sum
                
        if contract_total is None and budget_total is not None:
            # Assumed 15% margin
            contract_total = round(budget_total / 0.85, 2)
            
        if budget_total is None and contract_total is not None:
            # Assumed 15% margin
            budget_total = round(contract_total * 0.85, 2)

    return contract_total, budget_total, currency, partner_shares


def get_alert_category(alert):
    rule_id = alert.get("rule_id", "").upper()
    desc = alert.get("description", "").upper()
    
    if "LOC-MISMATCH" in rule_id or "LOCATION" in desc or "GEOGRAPH" in desc or "CELAYA" in desc or "CAMPINAS" in desc:
        return "SCOPE"
    elif rule_id.startswith("BUD") or rule_id.startswith("FIN") or "BUDGET" in desc or "FINAN" in desc or "TIR" in desc or "IRR" in desc or "COST" in desc:
        return "BUDGET"
    elif rule_id.startswith("SCH") or rule_id.startswith("TIM") or "TIME" in desc or "DURATION" in desc or "MONTH" in desc or "DELAY" in desc or "CRONOGRAMA" in desc or "FECHA" in desc:
        return "TIME"
    elif rule_id.startswith("LEG") or "LEGAL" in desc or "LAW" in desc or "PENAL" in desc or "CONTRACT" in desc:
        return "LEGAL"
    elif rule_id.startswith("TEC") or "TECHNICAL" in desc or "TECNIC" in desc:
        return "TECHNICAL"
    elif rule_id.startswith("QLY") or rule_id.startswith("QUAL") or "QUALITY" in desc or "STANDARDS" in desc or "NORMATIVA" in desc or "CALIDAD" in desc:
        return "QUALITY"
    elif rule_id.startswith("SCP") or rule_id.startswith("SCOPE") or "SCOPE" in desc or "DESCRIP" in desc or "CELL" in desc or "LAV" in desc or "PLANTA" in desc:
        return "SCOPE"
    else:
        return "SCOPE"


def calculate_expert_scores(coherence_alerts, classification, filename_upper):
    categories = ["SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"]
    scores = {cat: 100.0 for cat in categories}
    
    if classification == "incoherence":
        scores["BUDGET"] -= 30.0
        
    if "LA_ROBLA" in filename_upper:
        scores["SCOPE"] = 60.0
        scores["BUDGET"] = 100.0
        scores["TIME"] = 100.0
    elif "CAMPILLOS" in filename_upper:
        scores["BUDGET"] = 60.0
        scores["SCOPE"] = 85.0
    elif "MONFORTE" in filename_upper:
        scores["BUDGET"] = 40.0
        scores["TIME"] = 60.0
    elif "MANDEM" in filename_upper:
        scores["TIME"] = 50.0
        scores["BUDGET"] = 80.0
    elif "RIYADH_METRO" in filename_upper:
        scores["BUDGET"] = 50.0
    elif "QUERETARO" in filename_upper or "RIO_SP" in filename_upper:
        scores["SCOPE"] = 60.0
    elif "TEXAS_GRID" in filename_upper:
        scores["TIME"] = 50.0
    elif "AL_ZOUR" in filename_upper:
        scores["LEGAL"] = 50.0
        
    for alert in coherence_alerts:
        cat = alert.get("category")
        if cat in scores:
            sev = alert.get("severity", "").lower()
            if sev == "critical":
                scores[cat] = min(scores[cat], 50.0)
            elif sev == "high":
                scores[cat] = min(scores[cat], 70.0)
            else:
                scores[cat] = min(scores[cat], 85.0)
                
    overall = int(sum(scores.values()) / len(scores))
    per_cat = {cat: int(scores[cat]) for cat in categories}
    
    return overall, per_cat


def normalize_all():
    print("Normalizing all golden schema files...")
    normalized_count = 0
    
    # Recurse through GOLDEN_DIR
    for json_path in GOLDEN_DIR.glob("**/*.json"):
        # Read the file
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                project = json.load(f)
        except Exception as e:
            print(f"Skipping {json_path.name} due to read error: {e}")
            continue
            
        # Check if it is a golden project definition (must have input_documents and expected_output)
        if "input_documents" not in project or "expected_output" not in project:
            continue
            
        filename = json_path.name
        filename_upper = filename.upper()
        
        # 1. & 2. Get and inject canonical budget keys and gap classification
        input_docs = project["input_documents"]
        budget_summary = input_docs.get("budget_summary", {})
        
        contract_total, budget_total, currency, partner_shares = get_canonical_budget(budget_summary, filename)
        
        # Determine classification
        classification = "normal_margin"
        gap_reason = "Normal execution margin."
        
        if "MANDEM" in filename_upper:
            classification = "incoherence"
            gap_reason = "Unexplained deviation of 9.42% over procurement target and heavy cost overruns."
        elif "MONFORTE" in filename_upper:
            classification = "incoherence"
            gap_reason = "Negative margin where internal cost estimate exceeds contract revenue."
        elif "RIYADH_METRO" in filename_upper:
            classification = "incoherence"
            gap_reason = "Tunneling cost overruns exceed contract contingency fund."
        elif "LA_ROBLA" in filename_upper:
            classification = "normal_margin"
            gap_reason = "JV partition of Inabensa sub-budget and material sheets under ADIF-AV total contract."
        elif "CAMPILLOS" in filename_upper:
            classification = "normal_margin"
            gap_reason = "Viability IRR constraints with normal investment-budget spread."
        else:
            has_budget_alert = False
            for alert in project.get("expected_output", {}).get("coherence_alerts", []):
                alert_cat = get_alert_category(alert)
                if alert_cat == "BUDGET":
                    has_budget_alert = True
                    gap_reason = alert.get("description", "Budget discrepancy identified.")
                    break
                    
            if has_budget_alert:
                classification = "incoherence"
            else:
                classification = "normal_margin"
                if "001" in filename_upper:
                    gap_reason = "Contract total and budget are fully reconciled."
                else:
                    gap_reason = "Normal 15% execution margin."
                    
        # Inject canonical keys to budget_summary
        budget_summary["contract_total"] = contract_total
        budget_summary["budget_total"] = budget_total
        budget_summary["currency"] = currency
        if partner_shares:
            budget_summary["partner_shares"] = partner_shares
            
        budget_summary["budget_gap_classification"] = classification
        budget_summary["budget_gap_reason"] = gap_reason
        
        # 3. Every alert gets an explicit category
        expected_output = project["expected_output"]
        alerts = expected_output.get("coherence_alerts", [])
        for alert in alerts:
            alert["category"] = get_alert_category(alert)
            
        # 4. Calculate and inject expert_score and per_category_scores
        overall, per_cat = calculate_expert_scores(alerts, classification, filename_upper)
        expected_output["expert_score"] = overall
        expected_output["per_category_scores"] = per_cat
        
        # Save back the file
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(project, f, indent=2, ensure_ascii=False)
            
        normalized_count += 1

    print(f"Successfully normalized {normalized_count} projects in the golden dataset.")


if __name__ == "__main__":
    normalize_all()
