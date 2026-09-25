import os
import json
from pathlib import Path

GOLDEN_DIR = Path("tests/golden/real")


def recreate():
    print("Recreating missing calibration project files...")
    
    # 1. Mexico / Queretaro
    mexico_dir = GOLDEN_DIR / "mexico"
    mexico_dir.mkdir(parents=True, exist_ok=True)
    with open(mexico_dir / "project_QUERETARO.json", "w", encoding="utf-8") as f:
        json.dump({
            "project_metadata": {
                "id": "P-MX-01",
                "name": "LAV México - Querétaro",
                "type": "Railway System",
                "complexity": "Complex",
                "language": "es"
            },
            "input_documents": {
                "contract_text": "CONTRATO PARA EL DESARROLLO DEL TREN DE ALTA VELOCIDAD MÉXICO - QUERÉTARO. Importe total: 50,820,000,000.00 MXN sin IVA.",
                "risk_analysis_text": "Análisis de riesgos: se reportan discrepancias con el tramo Celaya.",
                "budget_summary": {
                    "total_value_mxn": 50820000000.00,
                    "budget_total_mxn": 42150000000.00
                }
            },
            "expected_output": {
                "coherence_alerts": [
                    {
                        "rule_id": "LOC-MISMATCH-01",
                        "severity": "critical",
                        "description": "Location name discrepancy: Celaya folder name vs Querétaro contract location.",
                        "conflicting_elements": []
                    }
                ]
            }
        }, f, indent=2, ensure_ascii=False)

    # 2. Brasil / Rio SP
    brasil_dir = GOLDEN_DIR / "brasil"
    brasil_dir.mkdir(parents=True, exist_ok=True)
    with open(brasil_dir / "project_RIO_SP.json", "w", encoding="utf-8") as f:
        json.dump({
            "project_metadata": {
                "id": "P-BR-01",
                "name": "TAV Rio - São Paulo",
                "type": "High Speed Rail",
                "complexity": "Complex",
                "language": "pt"
            },
            "input_documents": {
                "contract_text": "CONTRATO DE TREM DE ALTA VELOCIDADE RIO - SÃO PAULO. Valor global: 34,600,000,000.00 BRL sem impostos.",
                "risk_analysis_text": "Análise de riscos para o trecho de Campinas.",
                "budget_summary": {
                    "total_value_brl": 34600000000.00,
                    "budget_total_brl": 31200000000.00
                }
            },
            "expected_output": {
                "coherence_alerts": [
                    {
                        "rule_id": "LOC-MISMATCH-01",
                        "severity": "critical",
                        "description": "Location name discrepancy: Campinas folder vs São Paulo contract.",
                        "conflicting_elements": []
                    }
                ]
            }
        }, f, indent=2, ensure_ascii=False)

    # 3. USA / Texas Grid
    usa_dir = GOLDEN_DIR / "usa"
    usa_dir.mkdir(parents=True, exist_ok=True)
    with open(usa_dir / "project_TEXAS_GRID.json", "w", encoding="utf-8") as f:
        json.dump({
            "project_metadata": {
                "id": "P-US-01",
                "name": "Texas Clean Energy Grid",
                "type": "Power Grid",
                "complexity": "Complex",
                "language": "en"
            },
            "input_documents": {
                "contract_text": "CONTRACT AGREEMENT for Texas Clean Energy Grid. Total price: $245,000,000.00 USD. Execution duration: 36 months.",
                "risk_analysis_text": "Risk Analysis (AR): logistics constraints extend schedule duration to 48 months.",
                "budget_summary": {
                    "total_value_usd": 245000000.00,
                    "budget_total_usd": 220000000.00
                }
            },
            "expected_output": {
                "coherence_alerts": [
                    {
                        "rule_id": "SCH-USA-01",
                        "severity": "critical",
                        "description": "Schedule mismatch: 36 months contract vs 48 months risk assessment.",
                        "conflicting_elements": []
                    }
                ]
            }
        }, f, indent=2, ensure_ascii=False)

    # 4. Saudi / Riyadh Metro
    saudi_dir = GOLDEN_DIR / "saudi"
    saudi_dir.mkdir(parents=True, exist_ok=True)
    with open(saudi_dir / "project_RIYADH_METRO.json", "w", encoding="utf-8") as f:
        json.dump({
            "project_metadata": {
                "id": "P-SA-01",
                "name": "Riyadh Metro Line 3",
                "type": "Metro System",
                "complexity": "Complex",
                "language": "en"
            },
            "input_documents": {
                "contract_text": "CONTRACT AGREEMENT for Riyadh Metro Line 3. Price: $1,250,000,000.00 USD. Contingency fund is $50,000,000.00 USD.",
                "risk_analysis_text": "Risk Analysis (AR) identifies civil tunneling cost overrun of $300,000,000.00, which exceeds the contingency fund.",
                "budget_summary": {
                    "total_value_usd": 1250000000.00,
                    "contingency_usd": 50000000.00
                }
            },
            "expected_output": {
                "coherence_alerts": [
                    {
                        "rule_id": "BUD-SAU-01",
                        "severity": "critical",
                        "description": "Tunneling risk of $300,000,000 exceeds contingency of $50,000,000.",
                        "conflicting_elements": []
                    }
                ]
            }
        }, f, indent=2, ensure_ascii=False)

    # 5. Kuwait / Al Zour
    kuwait_dir = GOLDEN_DIR / "kuwait"
    kuwait_dir.mkdir(parents=True, exist_ok=True)
    with open(kuwait_dir / "project_AL_ZOUR.json", "w", encoding="utf-8") as f:
        json.dump({
            "project_metadata": {
                "id": "P-KW-01",
                "name": "Al-Zour Refinery Expansion",
                "type": "Refinery",
                "complexity": "Complex",
                "language": "en"
            },
            "input_documents": {
                "contract_text": "CONTRACT AGREEMENT for Al-Zour Refinery Expansion. Total: 580,000,000.00 KWD. Contract claims to be exempt from delays.",
                "risk_analysis_text": "Municipal Risk Analysis (AR) indicates delay penalties of 100,000 KWD/day apply legally.",
                "budget_summary": {
                    "total_value_kwd": 580000000.00,
                    "budget_total_kwd": 530000000.00
                }
            },
            "expected_output": {
                "coherence_alerts": [
                    {
                        "rule_id": "LEG-KWT-01",
                        "severity": "critical",
                        "description": "Contract claims to be exempt, but risk is 100,000 KWD/day penalty.",
                        "conflicting_elements": []
                    }
                ]
            }
        }, f, indent=2, ensure_ascii=False)

    print("Successfully recreated all 5 ground truth projects!")


if __name__ == "__main__":
    recreate()
