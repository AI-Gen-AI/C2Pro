#!/usr/bin/env python3
"""
LangSmith Dataset Manager for C2PRO Evaluation Infrastructure

This module provides utilities for managing evaluation datasets in LangSmith,
including upload, sync, versioning, and metrics tracking.

Usage:
    python langsmith_dataset_manager.py upload --service coherence --version 1.0.0
    python langsmith_dataset_manager.py sync-metrics --dataset c2pro_coherence_eval_v1
    python langsmith_dataset_manager.py list
    python langsmith_dataset_manager.py create-run --dataset c2pro_coherence_eval_v1 --model claude-haiku

Environment Variables:
    LANGSMITH_API_KEY: Required for LangSmith API access
    LANGSMITH_PROJECT: Project name (default: C2Pro)
"""

import argparse
import asyncio
import json
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

try:
    from langsmith import Client
    from langsmith.schemas import Dataset, Example
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    print("Warning: langsmith package not installed. Run: pip install langsmith")


# --- Configuration ---
BASE_DIR = Path(__file__).parent.parent / "evaluation" / "datasets"
DEFAULT_PROJECT = os.getenv("LANGSMITH_PROJECT", "C2Pro")


class ServiceType(str, Enum):
    COHERENCE = "coherence"
    EXTRACTION = "extraction"
    RETRIEVAL = "retrieval"


DATASET_CONFIGS = {
    ServiceType.COHERENCE: {
        "name_prefix": "c2pro_coherence_eval",
        "description": "Coherence Engine v2 evaluation dataset for clause analysis",
        "local_path": "coherence/v1.0.0_coherence_eval.json",
        "baseline_path": "coherence/baseline_metrics.json",
    },
    ServiceType.EXTRACTION: {
        "name_prefix": "c2pro_extraction_eval",
        "description": "Document Extraction (I3) evaluation dataset",
        "local_path": "extraction/v1.0.0_extraction_eval.json",
        "baseline_path": "extraction/baseline_metrics.json",
    },
    ServiceType.RETRIEVAL: {
        "name_prefix": "c2pro_retrieval_eval",
        "description": "Hybrid Retrieval (I4) evaluation dataset with corpus",
        "local_path": "retrieval/v1.0.0_retrieval_eval.json",
        "baseline_path": "retrieval/baseline_metrics.json",
    },
}


class LangSmithDatasetManager:
    """
    Manages evaluation datasets in LangSmith.

    Responsibilities:
    - Upload local JSON datasets to LangSmith
    - Sync baseline metrics
    - Version dataset updates
    - Track dataset lineage
    """

    def __init__(self, api_key: str | None = None):
        if not LANGSMITH_AVAILABLE:
            raise RuntimeError("langsmith package is required. Install with: pip install langsmith")

        self.api_key = api_key or os.getenv("LANGSMITH_API_KEY")
        if not self.api_key:
            raise ValueError("LANGSMITH_API_KEY is required")

        self.client = Client(api_key=self.api_key)
        self.project = DEFAULT_PROJECT

    def list_datasets(self) -> list[dict]:
        """List all C2PRO evaluation datasets in LangSmith."""
        datasets = []
        for ds in self.client.list_datasets():
            if ds.name.startswith("c2pro_"):
                datasets.append({
                    "id": str(ds.id),
                    "name": ds.name,
                    "description": ds.description,
                    "created_at": ds.created_at.isoformat() if ds.created_at else None,
                    "example_count": ds.example_count,
                })
        return datasets

    def get_dataset(self, dataset_name: str) -> Dataset | None:
        """Get a dataset by name."""
        try:
            return self.client.read_dataset(dataset_name=dataset_name)
        except Exception:
            return None

    def upload_dataset(
        self,
        service: ServiceType,
        version: str,
        local_path: Path | None = None,
    ) -> str:
        """
        Upload local evaluation dataset to LangSmith.

        Args:
            service: Service type (coherence, extraction, retrieval)
            version: Dataset version (e.g., "1.0.0")
            local_path: Optional custom path to dataset file

        Returns:
            Dataset ID in LangSmith
        """
        config = DATASET_CONFIGS[service]

        if local_path is None:
            local_path = BASE_DIR / config["local_path"]

        if not local_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {local_path}")

        # Load local dataset
        with open(local_path, "r", encoding="utf-8") as f:
            local_data = json.load(f)

        # Generate versioned dataset name
        dataset_name = f"{config['name_prefix']}_v{version}"

        # Check if dataset already exists
        existing = self.get_dataset(dataset_name)
        if existing:
            print(f"Dataset '{dataset_name}' already exists. Updating examples...")
            dataset_id = str(existing.id)
            # Delete existing examples and re-upload
            for example in self.client.list_examples(dataset_name=dataset_name):
                self.client.delete_example(example.id)
        else:
            # Create new dataset
            dataset = self.client.create_dataset(
                dataset_name=dataset_name,
                description=f"{config['description']} (v{version})",
            )
            dataset_id = str(dataset.id)
            print(f"Created new dataset: {dataset_name}")

        # Upload examples
        examples = local_data.get("examples", [])
        uploaded = 0

        for example in examples:
            try:
                inputs = self._prepare_inputs(service, example)
                outputs = self._prepare_outputs(service, example)
                metadata = self._prepare_metadata(service, example)

                self.client.create_example(
                    dataset_name=dataset_name,
                    inputs=inputs,
                    outputs=outputs,
                    metadata=metadata,
                )
                uploaded += 1
            except Exception as e:
                print(f"  Warning: Failed to upload example {example.get('id', 'unknown')}: {e}")

        print(f"Uploaded {uploaded}/{len(examples)} examples to '{dataset_name}'")

        # Store version metadata
        self._update_version_metadata(dataset_name, version, local_data)

        return dataset_id

    def _prepare_inputs(self, service: ServiceType, example: dict) -> dict:
        """Prepare input fields for LangSmith example."""
        if service == ServiceType.COHERENCE:
            return {
                "clause_text": example.get("input", {}).get("clause_text", ""),
                "clause_type": example.get("input", {}).get("clause_type", ""),
                "additional_clauses": example.get("input", {}).get("additional_clauses", []),
                "project_context": example.get("input", {}).get("project_context", {}),
            }
        elif service == ServiceType.EXTRACTION:
            return {
                "document_text": example.get("input", {}).get("document_text", ""),
                "document_type": example.get("input", {}).get("document_type", "contract"),
                "language": example.get("input", {}).get("language", "es"),
            }
        elif service == ServiceType.RETRIEVAL:
            return {
                "query_text": example.get("query", {}).get("text", ""),
                "expected_intent": example.get("query", {}).get("expected_intent", "hybrid"),
                "language": example.get("query", {}).get("language", "es"),
            }
        return example.get("input", {})

    def _prepare_outputs(self, service: ServiceType, example: dict) -> dict:
        """Prepare expected output fields for LangSmith example."""
        if service == ServiceType.COHERENCE:
            return example.get("expected_output", {})
        elif service == ServiceType.EXTRACTION:
            return example.get("expected_output", {})
        elif service == ServiceType.RETRIEVAL:
            return example.get("expected_results", {})
        return example.get("expected_output", {})

    def _prepare_metadata(self, service: ServiceType, example: dict) -> dict:
        """Prepare metadata for LangSmith example."""
        return {
            "example_id": example.get("id", ""),
            "category": example.get("category", ""),
            "difficulty": example.get("difficulty", "medium"),
            "language": example.get("language", example.get("input", {}).get("language", "es")),
            "human_rationale": example.get("human_rationale", ""),
            "tags": example.get("tags", []),
        }

    def _update_version_metadata(
        self,
        dataset_name: str,
        version: str,
        local_data: dict,
    ) -> None:
        """Store version information in dataset metadata."""
        # LangSmith datasets don't have native metadata storage,
        # so we store a special "_version_info" example
        try:
            version_info = {
                "version": version,
                "uploaded_at": datetime.now().isoformat(),
                "source_dataset_name": local_data.get("dataset_name", ""),
                "source_version": local_data.get("version", ""),
                "example_count": len(local_data.get("examples", [])),
                "baseline_metrics": local_data.get("baseline_metrics", {}),
                "metadata": local_data.get("metadata", {}),
            }

            # Delete existing version info if present
            for example in self.client.list_examples(dataset_name=dataset_name):
                if example.metadata and example.metadata.get("is_version_info"):
                    self.client.delete_example(example.id)
                    break

            self.client.create_example(
                dataset_name=dataset_name,
                inputs={"_type": "version_info"},
                outputs=version_info,
                metadata={"is_version_info": True},
            )
        except Exception as e:
            print(f"  Warning: Failed to store version metadata: {e}")

    def sync_baseline_metrics(
        self,
        dataset_name: str,
        metrics: dict[str, float] | None = None,
    ) -> None:
        """
        Sync baseline metrics for drift detection.

        Args:
            dataset_name: Name of the dataset in LangSmith
            metrics: Optional metrics dict. If None, loads from local baseline file.
        """
        # Find service type from dataset name
        service = None
        for svc, config in DATASET_CONFIGS.items():
            if dataset_name.startswith(config["name_prefix"]):
                service = svc
                break

        if service is None:
            raise ValueError(f"Unknown dataset: {dataset_name}")

        config = DATASET_CONFIGS[service]

        if metrics is None:
            # Load from local baseline file
            baseline_path = BASE_DIR / config["baseline_path"]
            if baseline_path.exists():
                with open(baseline_path, "r", encoding="utf-8") as f:
                    baseline_data = json.load(f)
                metrics = baseline_data.get("metrics", {})
            else:
                raise FileNotFoundError(f"Baseline file not found: {baseline_path}")

        # Update version info with new metrics
        for example in self.client.list_examples(dataset_name=dataset_name):
            if example.metadata and example.metadata.get("is_version_info"):
                outputs = dict(example.outputs) if example.outputs else {}
                outputs["baseline_metrics"] = metrics
                outputs["baseline_updated_at"] = datetime.now().isoformat()

                self.client.update_example(
                    example_id=example.id,
                    outputs=outputs,
                )
                print(f"Updated baseline metrics for '{dataset_name}'")
                return

        print(f"Warning: No version info found for '{dataset_name}'. Upload dataset first.")

    def create_evaluation_run(
        self,
        dataset_name: str,
        model_version: str,
        run_name: str | None = None,
    ) -> str:
        """
        Create a new evaluation run for a dataset.

        This sets up the context for running evaluations against
        the specified dataset with a particular model version.

        Returns:
            Run ID for tracking
        """
        if run_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_name = f"eval_{dataset_name}_{model_version}_{timestamp}"

        # In LangSmith, runs are created as part of tracing
        # This method returns the run name for use with tracing
        print(f"Evaluation run configured: {run_name}")
        print(f"  Dataset: {dataset_name}")
        print(f"  Model: {model_version}")
        print(f"  Use LANGSMITH_RUN_NAME={run_name} when running evaluations")

        return run_name

    def get_dataset_examples(self, dataset_name: str) -> list[dict]:
        """
        Retrieve all examples from a dataset for local evaluation.

        Returns:
            List of examples with inputs, outputs, and metadata
        """
        examples = []
        for example in self.client.list_examples(dataset_name=dataset_name):
            if example.metadata and example.metadata.get("is_version_info"):
                continue  # Skip version info

            examples.append({
                "id": str(example.id),
                "example_id": example.metadata.get("example_id") if example.metadata else None,
                "inputs": dict(example.inputs) if example.inputs else {},
                "outputs": dict(example.outputs) if example.outputs else {},
                "metadata": dict(example.metadata) if example.metadata else {},
            })

        return examples


def print_datasets(datasets: list[dict]) -> None:
    """Pretty print dataset list."""
    if not datasets:
        print("No C2PRO datasets found in LangSmith.")
        return

    print(f"\n{'='*70}")
    print("C2PRO Evaluation Datasets in LangSmith")
    print(f"{'='*70}")

    for ds in datasets:
        print(f"\n  {ds['name']}")
        print(f"    ID: {ds['id']}")
        print(f"    Description: {ds.get('description', 'N/A')}")
        print(f"    Examples: {ds.get('example_count', 'N/A')}")
        print(f"    Created: {ds.get('created_at', 'N/A')}")


async def main():
    parser = argparse.ArgumentParser(
        description="Manage C2PRO evaluation datasets in LangSmith"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # List command
    subparsers.add_parser("list", help="List all C2PRO datasets in LangSmith")

    # Upload command
    upload_parser = subparsers.add_parser("upload", help="Upload dataset to LangSmith")
    upload_parser.add_argument(
        "--service",
        type=str,
        choices=["coherence", "extraction", "retrieval"],
        required=True,
        help="Service type",
    )
    upload_parser.add_argument(
        "--version",
        type=str,
        default="1.0.0",
        help="Dataset version",
    )
    upload_parser.add_argument(
        "--path",
        type=Path,
        help="Custom path to dataset file",
    )

    # Sync metrics command
    sync_parser = subparsers.add_parser("sync-metrics", help="Sync baseline metrics")
    sync_parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Dataset name in LangSmith",
    )

    # Create run command
    run_parser = subparsers.add_parser("create-run", help="Create evaluation run")
    run_parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Dataset name",
    )
    run_parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Model version being evaluated",
    )
    run_parser.add_argument(
        "--name",
        type=str,
        help="Custom run name",
    )

    # Download command
    download_parser = subparsers.add_parser("download", help="Download dataset examples")
    download_parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Dataset name",
    )
    download_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output file path",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        manager = LangSmithDatasetManager()

        if args.command == "list":
            datasets = manager.list_datasets()
            print_datasets(datasets)

        elif args.command == "upload":
            service = ServiceType(args.service)
            dataset_id = manager.upload_dataset(
                service=service,
                version=args.version,
                local_path=args.path,
            )
            print(f"\nDataset ID: {dataset_id}")

        elif args.command == "sync-metrics":
            manager.sync_baseline_metrics(args.dataset)

        elif args.command == "create-run":
            run_id = manager.create_evaluation_run(
                dataset_name=args.dataset,
                model_version=args.model,
                run_name=args.name,
            )
            print(f"Run ID: {run_id}")

        elif args.command == "download":
            examples = manager.get_dataset_examples(args.dataset)
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(examples, f, indent=2, ensure_ascii=False)
            print(f"Downloaded {len(examples)} examples to {args.output}")

    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
