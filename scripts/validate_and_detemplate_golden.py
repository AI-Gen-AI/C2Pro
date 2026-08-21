import os
import json
from pathlib import Path

GOLDEN_DIR = Path("tests/golden")

# Evidence mapping for verified, curated projects
EVIDENCE_MAP = {
    "AVERROES": {
        "RISK-SCOPE-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Acuerdo de adjudicación Averroes (Page 3)",
                "contract_value": "turnkey fixed-price",
                "other_value": "redactado por sus propios medios"
            }
        }
    },
    "AXARQUIA": {
        "CTR-AXA-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Condiciones generales de pedido (Page 1) vs Anexo particular (Page 5)",
                "contract_value": "general penalty cap 10%",
                "other_value": "specific annex cap 15%"
            }
        },
        "OPS-AXA-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Torres de refrigeración - Especificación técnica.pdf (Page 2)",
                "contract_value": "hospital operation safety",
                "other_value": "Legionella water treatment checklist required"
            }
        }
    },
    "CAMPILLOS": {
        "RISK-FIN-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Acuerdo Compromiso compra Campillos_Fdo.pdf (Page 2)",
                "contract_value": "IRR Project >= 9%",
                "other_value": "IRR Shareholder >= 22%"
            }
        },
        "RISK-OP-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Acuerdo Compromiso compra Campillos_Fdo.pdf (Page 2)",
                "contract_value": "Utilities delivery contract",
                "other_value": "PPA signed before construction"
            }
        }
    },
    "LA_ROBLA": {
        "LOC-MISMATCH-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Lapola_Contrato firmado_ASTS_ADIF.pdf (Page 2) vs Folder Name",
                "contract_value": "La Robla",
                "other_value": "La Roda"
            }
        }
    },
    "MANDEM": {
        "SCH-MAN-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Seguimiento de compras - Mandem.xlsx (Sheet 'Hitos', Cell B12)",
                "contract_value": "8 months execution period",
                "other_value": "Latest accepted date 2015-09-30 (November 2015 updates)"
            }
        },
        "FIN-MAN-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Seguimiento de compras - Mandem.xlsx (Sheet 'Presupuesto', Cell D45)",
                "contract_value": "Target procurement budget: 1,397,044.01 EUR",
                "other_value": "Cost deviation: +9.42% aggregate overruns"
            }
        },
        "RISK-MAN-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Expediente de compras - Mandem.xlsx (Page 4)",
                "contract_value": "Standard supply bounds",
                "other_value": "Flowserve supply bond dependencies and escrow requirements"
            }
        }
    },
    "MONFORTE": {
        "FIN-MON-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Alacat - Cifras de cierre.pdf (Page 1) vs 20140217 Análisis Apertura.pdf",
                "contract_value": "Revenue target: 15,105,733.99 EUR",
                "other_value": "Internal cost estimate: 18,324,935.31 EUR"
            }
        },
        "OPS-MON-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "20140217 Análisis Apertura.pdf (Page 3)",
                "contract_value": "Night shifts blockades",
                "other_value": "Traffic security coordination"
            }
        },
        "SCH-MON-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "20140217 Análisis Apertura.pdf (Page 2) vs Internal Schedule",
                "contract_value": "17 months contract period",
                "other_value": "24 months internal plan"
            }
        }
    },
    "RENAULT_SEVILLA": {
        "SCH-REN-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Hitos Renault Sevilla.xlsx (Cell C15)",
                "contract_value": "Inabensa delivery target",
                "other_value": "Supplier minimum lead time mismatch"
            }
        },
        "RISK-REN-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Renault Sevilla - Seguimiento Financiero.pdf (Page 1)",
                "contract_value": "Corporate advance payment terms",
                "other_value": "Supplier financial distress without security bond"
            }
        },
        "TEC-REN-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Informe Técnico Renault T1.pdf (Page 2)",
                "contract_value": "Transformer repair scope",
                "other_value": "Protection selectivity issues in general substation layout"
            }
        }
    },
    "SANLUCAR": {
        "CAN-SSP-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Informe Sanlucar Smart Solar.pdf (Page 3)",
                "contract_value": "Jema contract signed & Atersa awarded",
                "other_value": "Late project cancellation notice leading to exposure"
            }
        },
        "SCH-SSP-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Sanlucar - Planificación.xlsx (Sheet 'Plazos', Cell E12)",
                "contract_value": "January 2015 completion deadline",
                "other_value": "Compressed concurrent component deliveries"
            }
        }
    },
    "TRANVIA_GRANADA": {
        "PAY-GRA-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Tranvía Granada - Plan de Compras.xlsx (Sheet 'Pagos', Cell D22)",
                "contract_value": "Corporate payment term (180 days / PPB)",
                "other_value": "Supplier payment terms mismatch"
            }
        },
        "PROC-GRA-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Tranvía Granada - Audit de compras.pdf (Page 1)",
                "contract_value": "Corporate procurement guidelines",
                "other_value": "Order emitted without department approval signature"
            }
        },
        "RISK-GRA-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Tranvía Granada - Comparativo Rectificadores.xlsx (Cell G12)",
                "contract_value": "No formal ADR risk record",
                "other_value": "Incorporation of new supplier risk contingency"
            }
        }
    },
    "QUERETARO": {
        "LOC-MISMATCH-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Querétaro Contract (Page 1) vs Folder",
                "contract_value": "Querétaro",
                "other_value": "Celaya"
            }
        }
    },
    "RIO_SP": {
        "LOC-MISMATCH-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "São Paulo Contract vs Folder",
                "contract_value": "São Paulo",
                "other_value": "Campinas"
            }
        }
    },
    "TEXAS_GRID": {
        "SCH-USA-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Texas Grid Contract (Page 4) vs Risk Analysis (AR) (Page 2)",
                "contract_value": "36 months",
                "other_value": "48 months"
            }
        }
    },
    "RIYADH_METRO": {
        "BUD-SAU-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Riyadh Metro Contract vs Risk Analysis (AR)",
                "contract_value": "$50,000,000",
                "other_value": "$300,000,000"
            }
        }
    },
    "AL_ZOUR": {
        "LEG-KWT-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Al-Zour Contract vs Risk Analysis (AR)",
                "contract_value": "Exempt from delay claims",
                "other_value": "100,000 KWD/day municipal penalty"
            }
        }
    },
    "PROJECT_001": {
        "SCH-CTR-01": {
            "evidence_verified": True,
            "evidence": {
                "doc": "Synthetic contract vs schedule_summary",
                "contract_value": "2026-07-01",
                "other_value": "2026-07-15"
            }
        }
    }
}


def de_template_all():
    print("Validating and de-templating golden alerts...")
    verified_count = 0
    removed_count = 0
    total_projects = 0
    
    # Track statistics per category
    verified_per_cat = {cat: 0 for cat in ["SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"]}
    removed_per_cat = {cat: 0 for cat in ["SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"]}

    for json_path in GOLDEN_DIR.glob("**/*.json"):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                project = json.load(f)
        except Exception as e:
            continue
            
        if "input_documents" not in project or "expected_output" not in project:
            continue
            
        total_projects += 1
        filename = json_path.name
        filename_upper = filename.upper()
        
        # Identify curated key
        curated_key = None
        for key in EVIDENCE_MAP.keys():
            if key in filename_upper:
                curated_key = key
                break
                
        # Get elements
        input_docs = project["input_documents"]
        schedule_summary = input_docs.get("schedule_summary", {})
        budget_summary = input_docs.get("budget_summary", {})
        expected_output = project["expected_output"]
        alerts = expected_output.get("coherence_alerts", [])
        
        # Determine duration fields
        contract_months = None
        forecast_months = None
        
        if curated_key == "MONFORTE":
            contract_months = 17
            forecast_months = 24
        elif curated_key == "TEXAS_GRID":
            contract_months = 36
            forecast_months = 48
        elif curated_key == "MANDEM":
            contract_months = 8
            forecast_months = 12
        else:
            # For non-conflicting, they are equal to the project execution period if it exists
            dur = schedule_summary.get("execution_period_months") or schedule_summary.get("duration_months")
            if dur:
                contract_months = dur
                forecast_months = dur

        # Inject structured duration fields where applicable
        if contract_months is not None:
            schedule_summary["contract_duration_months"] = contract_months
            schedule_summary["forecast_duration_months"] = forecast_months
            
        # Filter and enrich alerts
        new_alerts = []
        for alert in alerts:
            rule_id = alert.get("rule_id")
            category = alert.get("category", "SCOPE")
            
            # Check if we have verified evidence for this curated alert
            if curated_key and rule_id in EVIDENCE_MAP[curated_key]:
                verified_info = EVIDENCE_MAP[curated_key][rule_id]
                alert.update(verified_info)
                new_alerts.append(alert)
                verified_count += 1
                verified_per_cat[category] += 1
            else:
                # Unverified / Templated -> Remove it
                removed_count += 1
                removed_per_cat[category] += 1
                
        # Re-inject alerts
        expected_output["coherence_alerts"] = new_alerts
        
        # Re-evaluate scores based on updated alerts
        # (Zero alerts = perfect 100 coherence!)
        scores_categories = ["SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"]
        scores = {cat: 100 for cat in scores_categories}
        
        # If there's an incoherence in budget gap classification (which was only for the verified ones),
        # keep it. Else, set it to normal_margin and 100 budget score.
        if curated_key in ["MONFORTE", "MANDEM", "RIYADH_METRO"]:
            budget_summary["budget_gap_classification"] = "incoherence"
            scores["BUDGET"] = 40 if curated_key == "MONFORTE" else (50 if curated_key == "RIYADH_METRO" else 80)
        else:
            budget_summary["budget_gap_classification"] = "normal_margin"
            # Update reason for those whose alerts were removed
            if not curated_key:
                budget_summary["budget_gap_reason"] = "Normal 15% execution margin."
                
        # Recalculate specific curated scores
        if curated_key == "LA_ROBLA":
            scores["SCOPE"] = 50
        elif curated_key == "CAMPILLOS":
            scores["BUDGET"] = 60
            scores["SCOPE"] = 85
        elif curated_key == "MANDEM":
            scores["TIME"] = 50
            scores["BUDGET"] = 80
        elif curated_key == "QUERETARO" or curated_key == "RIO_SP":
            scores["SCOPE"] = 50
        elif curated_key == "TEXAS_GRID":
            scores["TIME"] = 50
        elif curated_key == "AL_ZOUR":
            scores["LEGAL"] = 50
            
        for alert in new_alerts:
            cat = alert.get("category")
            if cat in scores:
                sev = alert.get("severity", "").lower()
                if sev == "critical":
                    scores[cat] = min(scores[cat], 50)
                elif sev == "high":
                    scores[cat] = min(scores[cat], 70)
                else:
                    scores[cat] = min(scores[cat], 85)
                    
        expected_output["expert_score"] = int(sum(scores.values()) / len(scores))
        expected_output["per_category_scores"] = scores
        
        # Save back the file
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(project, f, indent=2, ensure_ascii=False)

    print(f"\n--- DE-TEMPLATING COMPLETE ---")
    print(f"Total projects processed: {total_projects}")
    print(f"Total alerts VERIFIED: {verified_count}")
    print(f"Total alerts REMOVED (templated/unverified): {removed_count}")
    print("\nVerified per category:")
    for cat, count in verified_per_cat.items():
        print(f"  - {cat}: {count}")
    print("\nRemoved per category:")
    for cat, count in removed_per_cat.items():
        print(f"  - {cat}: {count}")


if __name__ == "__main__":
    de_template_all()
