"""
Suite ID: TS-COH-DET-GOLDEN-001

Golden calibration cases for deterministic coherence evaluators.

These cases use the calibration-dataset style structure and are intended to
validate deterministic rule coverage before the v3 scoring engine is added.
"""

GOLDEN_CASES = [
    {
        "case_id": "GOLD-DET-001",
        "name": "Healthy project — no findings expected",
        "human_score": 95,
        "clauses": [
            {
                "id": "c1",
                "text": "Budget allocated",
                "data": {
                    "current": 100000,
                    "planned": 110000,
                    "currency": "EUR",
                },
            },
            {
                "id": "c2",
                "text": "Schedule on track",
                "data": {
                    "status": "on-track",
                    "end_date": "2030-12-31",
                },
            },
        ],
        "expected_findings": 0,
        "expected_rules_triggered": set(),
    },
    {
        "case_id": "GOLD-DET-002",
        "name": "Calibration sample 001 — budget items > contract total",
        "human_score": 82,
        "clauses": [
            {
                "id": "c1",
                "text": "Contract total 120k",
                "data": {
                    "contract_total": 120000,
                    "budget_items": [{"amount": 60000}, {"amount": 70000}],
                },
            },
            {
                "id": "c2",
                "text": "Schedule",
                "data": {
                    "schedule_items": [
                        {
                            "id": "task-1",
                            "name": "Foundations",
                            "start_date": "2030-01-01",
                            "end_date": "2030-01-10",
                            "predecessor_id": None,
                        },
                        {
                            "id": "task-2",
                            "name": "Structure",
                            "start_date": "2030-01-05",
                            "end_date": "2030-01-12",
                            "predecessor_id": "task-1",
                        },
                    ],
                },
            },
            {
                "id": "c3",
                "text": "BOM",
                "data": {
                    "bom_items": [
                        {
                            "item_name": "Valve X",
                            "required_on_site_date": "2030-02-01",
                            "lead_time_days": 30,
                            "budget_item_id": "budget-1",
                        }
                    ],
                },
            },
        ],
        # c3's bom_items has item_name/lead_time_days (material content) but no
        # spec_reference/standard/norm field, so DET-TEC-SPEC legitimately fires
        # too (src/coherence/rules_engine/deterministic.py:757-774). The original
        # expected set under-counted this rule since the fixture's introduction.
        "expected_findings": 4,
        "expected_rules_triggered": {
            "DET-BUD-SUM", "DET-CRS-BUDCON", "DET-TIM-PREDECESSOR", "DET-TEC-SPEC",
        },
    },
    {
        "case_id": "GOLD-DET-003",
        "name": "Severe multi-category violations",
        "human_score": 42,
        "clauses": [
            {
                "id": "c1",
                "text": "Budget way over",
                "data": {
                    "current": 250000,
                    "planned": 150000,
                    "currency": "USD",
                },
            },
            {
                "id": "c2",
                "text": "Schedule delayed",
                "data": {
                    "status": "delayed",
                    "end_date": "2025-06-01",
                },
            },
            {
                "id": "c3",
                "text": "No penalty cap",
                "data": {
                    "penalty": True,
                    "has_penalty_cap": False,
                },
            },
            {
                "id": "c4",
                "text": "Materials",
                "data": {
                    "item_name": "Steel beams",
                    "required_on_site_date": "2025-04-01",
                    "lead_time_days": 45,
                    "bom_items": [
                        {
                            "item_name": "Steel beams",
                            "required_on_site_date": "2025-04-01",
                            "lead_time_days": 45,
                        },
                        {
                            "item_name": "Concrete mix",
                            "required_on_site_date": "2025-05-01",
                            "lead_time_days": 15,
                        },
                    ],
                },
            },
            {
                "id": "c5",
                "text": "Quality per industry standards",
                "data": {},
            },
        ],
        "expected_findings": 8,
        "expected_rules_triggered": {
            "DET-BUD-OVERRUN",
            "DET-TIM-STATUS",
            "DET-TIM-OVERDUE",
            "DET-LEG-PENALTY",
            "DET-TEC-LEADTIME",
            "DET-TEC-SPEC",
            "DET-TEC-BOMBUDGET",
            "DET-QUA-STANDARD",
        },
    },
    {
        "case_id": "GOLD-DET-004",
        "name": "Moderate — single dimension problem",
        "human_score": 72,
        "clauses": [
            {
                "id": "c1",
                "text": "Budget on track",
                "data": {
                    "current": 95000,
                    "planned": 100000,
                    "currency": "EUR",
                },
            },
            {
                "id": "c2",
                "text": "Schedule at risk with long gap",
                "data": {
                    "status": "at_risk",
                    "end_date": "2030-10-01",
                    "milestones": [
                        {"date": "2030-03-01"},
                        {"date": "2030-09-15"},
                    ],
                },
            },
            {
                "id": "c3",
                "text": "Contract reviewed recently",
                "data": {
                    "last_review_date": "2026-01-15",
                },
            },
        ],
        "expected_findings": 2,
        "expected_rules_triggered": {"DET-TIM-STATUS", "DET-TIM-GAP"},
    },
]
