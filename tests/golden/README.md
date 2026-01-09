# Golden Dataset v1.0

This directory contains the golden dataset used for testing and benchmarking the C2Pro platform, specifically for `CE-S2-015`. This dataset consists of 10 synthetic projects, each with annotated data representing various aspects of project intelligence (documents, clauses, stakeholders, WBS, BOM, etc.).

## Purpose

The primary purposes of this golden dataset are:
-   **Regression Testing**: To ensure that new features or changes do not negatively impact the accuracy and consistency of existing functionalities.
-   **Accuracy Benchmarking**: To measure the performance of AI models in extracting and analyzing information against a known ground truth.
-   **System Integration Testing**: To validate the end-to-end data flow and processing within the C2Pro platform.

## Structure

Each `project_XX.json` file represents a synthetic project and contains a structured JSON object. The content of these files simulates various data points that would typically be processed by the C2Pro system.

### Example `project_XX.json` Structure (Conceptual)

```json
{
  "project_id": "uuid-of-project",
  "name": "Synthetic Project Name",
  "description": "A brief description of this synthetic project.",
  "documents": [
    {
      "document_id": "uuid-of-document",
      "type": "CONTRACT",
      "content_summary": "Summary of contract clauses...",
      "clauses": [
        {
          "clause_id": "uuid-of-clause",
          "text": "Full text of clause 1...",
          "annotations": {
            "stakeholders": ["John Doe", "Acme Corp"],
            "wbs_items_funded": ["WBS-001"],
            "bom_items_defined": ["BOM-ITEM-001"]
          }
        },
        {
          "clause_id": "uuid-of-clause-2",
          "text": "Full text of clause 2...",
          "annotations": {
            "stakeholders": [],
            "wbs_items_funded": [],
            "bom_items_defined": []
          }
        }
      ]
    }
  ],
  "stakeholders": [
    {
      "stakeholder_id": "uuid-of-stakeholder",
      "name": "John Doe",
      "role": "Project Manager",
      "power_level": "HIGH",
      "interest_level": "HIGH",
      "source_clause_id": "uuid-of-clause"
    }
  ],
  "wbs_items": [
    {
      "wbs_item_id": "uuid-of-wbs",
      "code": "1.1.1",
      "name": "Project Planning",
      "budget_allocated": 10000.00,
      "funded_by_clause_id": "uuid-of-clause"
    }
  ],
  "bom_items": [
    {
      "bom_item_id": "uuid-of-bom",
      "name": "Steel Beams",
      "quantity": 50.0,
      "unit_price": 200.00,
      "contract_clause_id": "uuid-of-clause"
    }
  ]
}
```

## How to Use

-   **Accessing Data**: Test scripts can read these JSON files to load predefined project scenarios.
-   **Verification**: The annotated data within each project serves as the expected output for various extraction and analysis processes.

## Contributing

-   When adding new synthetic projects, ensure they are thoroughly annotated and reflect realistic scenarios.
-   Update this `README.md` with any significant changes to the dataset structure or new conventions.
