#!/usr/bin/env python3
"""
Generate Evaluation Datasets for C2PRO AI Services

This script uses LLM-driven generation to expand evaluation datasets
for Coherence Engine, Document Extraction, and Hybrid Retrieval services.

Usage:
    python generate_eval_datasets.py --service coherence --count 30
    python generate_eval_datasets.py --service extraction --count 20
    python generate_eval_datasets.py --service retrieval --count 15
    python generate_eval_datasets.py --all

Environment Variables:
    ANTHROPIC_API_KEY: Required for Claude-based generation
    OPENAI_API_KEY: Alternative for OpenAI-based generation
"""

import argparse
import asyncio
import json
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

# Try to import Anthropic, fall back to OpenAI
try:
    import anthropic
    USE_ANTHROPIC = True
except ImportError:
    import openai
    USE_ANTHROPIC = False


# --- Configuration ---
BASE_DIR = Path(__file__).parent.parent / "evaluation" / "datasets"
MAX_RETRIES = 3
DEFAULT_MODEL = "claude-3-5-haiku-20241022" if USE_ANTHROPIC else "gpt-4-turbo-preview"


class ServiceType(str, Enum):
    COHERENCE = "coherence"
    EXTRACTION = "extraction"
    RETRIEVAL = "retrieval"


# --- Generation Configurations ---
GENERATION_CONFIG = {
    ServiceType.COHERENCE: {
        "scenarios": [
            {"category": "ambiguity", "count": 15, "language": "es", "difficulty": "medium"},
            {"category": "vague_term", "count": 15, "language": "es", "difficulty": "easy"},
            {"category": "clear_clause", "count": 15, "language": "es", "difficulty": "easy"},
            {"category": "cross_clause", "count": 10, "language": "es", "difficulty": "hard"},
            {"category": "contradiction", "count": 10, "language": "es", "difficulty": "hard"},
            {"category": "risk", "count": 10, "language": "es", "difficulty": "medium"},
            {"category": "payment", "count": 10, "language": "es", "difficulty": "medium"},
            {"category": "responsibility", "count": 10, "language": "es", "difficulty": "medium"},
            {"category": "ambiguity", "count": 5, "language": "en", "difficulty": "medium"},
            {"category": "clear_clause", "count": 5, "language": "en", "difficulty": "easy"},
        ],
        "output_file": "coherence/generated_coherence_eval.json",
    },
    ServiceType.EXTRACTION: {
        "scenarios": [
            {"category": "clause_boundary", "count": 20, "language": "es", "difficulty": "standard"},
            {"category": "entity_extraction", "count": 25, "language": "es", "difficulty": "standard"},
            {"category": "obligation_parsing", "count": 20, "language": "es", "difficulty": "nested"},
            {"category": "mixed", "count": 10, "language": "es", "difficulty": "nested"},
            {"category": "malformed", "count": 5, "language": "es", "difficulty": "malformed"},
            {"category": "entity_extraction", "count": 10, "language": "en", "difficulty": "standard"},
            {"category": "obligation_parsing", "count": 10, "language": "en", "difficulty": "standard"},
        ],
        "output_file": "extraction/generated_extraction_eval.json",
    },
    ServiceType.RETRIEVAL: {
        "scenarios": [
            {"category": "keyword_exact", "count": 15, "language": "es"},
            {"category": "semantic_similar", "count": 20, "language": "es"},
            {"category": "hybrid_required", "count": 15, "language": "es"},
            {"category": "negative", "count": 5, "language": "es"},
            {"category": "semantic_similar", "count": 10, "language": "en"},
            {"category": "cross_project", "count": 5, "language": "mixed"},
        ],
        "output_file": "retrieval/generated_retrieval_eval.json",
    },
}


# --- Pydantic Schemas for Validation ---

class CoherenceExample(BaseModel):
    """Schema for a coherence evaluation example."""
    id: str
    category: str
    tags: list[str] = Field(default_factory=list)
    input: dict[str, Any]
    expected_output: dict[str, Any]
    human_rationale: str
    difficulty: str
    language: str


class ExtractionExample(BaseModel):
    """Schema for an extraction evaluation example."""
    id: str
    category: str
    input: dict[str, Any]
    expected_output: dict[str, Any]
    extraction_difficulty: str
    human_rationale: str


class RetrievalExample(BaseModel):
    """Schema for a retrieval evaluation example."""
    id: str
    category: str
    query: dict[str, Any]
    expected_results: dict[str, Any]
    reranker_expectations: dict[str, Any] = Field(default_factory=dict)
    human_rationale: str
    difficulty: str


# --- Prompts ---

COHERENCE_SYSTEM_PROMPT = """You are an expert contract analyst generating evaluation test cases for an AI coherence detection system.
Your task is to create realistic contract clauses with expected coherence analysis results.

Generate contract clauses in {language} that demonstrate the category '{category}' with difficulty level '{difficulty}'.

For each example, provide:
1. A realistic contract clause (20-200 words)
2. Whether it has issues (boolean)
3. Severity level if applicable (low/medium/high/critical)
4. Issue types detected
5. Trigger terms that indicate the issue
6. Expected coherence score range [min, max] from 0-100
7. Human-readable rationale explaining why this is the expected output

Return ONLY valid JSON matching the schema. No markdown fences."""

EXTRACTION_SYSTEM_PROMPT = """You are an expert contract analyst generating evaluation test cases for a document extraction AI system.
Your task is to create realistic contract text with expected extraction results.

Generate contract text in {language} demonstrating '{category}' extraction with difficulty '{difficulty}'.

For each example, provide:
1. Realistic contract text (50-500 words) with {category} elements
2. Expected extracted clauses with:
   - clause_id, text, type, modality (shall/may/must_not/will/should/none)
   - actors mentioned, dates, amounts if applicable
   - ambiguity_flag if the clause is ambiguous
   - confidence_range [min, max] from 0-1
3. Human rationale explaining extraction expectations

Return ONLY valid JSON matching the schema. No markdown fences."""

RETRIEVAL_SYSTEM_PROMPT = """You are an expert in information retrieval generating evaluation test cases for a hybrid retrieval system.
Your task is to create realistic search queries with expected retrieval results.

Generate queries in {language} demonstrating '{category}' retrieval patterns.

For each example, provide:
1. A realistic search query
2. Expected intent (keyword/vector/hybrid)
3. Which documents should be retrieved (must_include_doc_ids)
4. Which should not appear (must_exclude_doc_ids)
5. Expected ranking positions for key documents
6. Whether reranking should improve results
7. Human rationale

The corpus contains contract clauses about: payments, penalties, warranties, insurance, termination,
force majeure, quality standards, confidentiality, arbitration, scope, variations, reporting, safety.

Return ONLY valid JSON matching the schema. No markdown fences."""


# --- Generation Functions ---

async def generate_with_anthropic(
    client: "anthropic.AsyncAnthropic",
    system_prompt: str,
    user_prompt: str,
    schema: dict,
) -> dict | None:
    """Generate example using Anthropic Claude."""
    for attempt in range(MAX_RETRIES):
        try:
            message = await client.messages.create(
                model=DEFAULT_MODEL,
                max_tokens=4096,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
            )
            content = message.content[0].text
            # Clean any markdown fences
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content.strip())
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
            if attempt == MAX_RETRIES - 1:
                return None
        except Exception as e:
            print(f"  Unexpected error on attempt {attempt + 1}: {e}")
            if attempt == MAX_RETRIES - 1:
                return None
    return None


async def generate_with_openai(
    client: "openai.AsyncOpenAI",
    system_prompt: str,
    user_prompt: str,
    schema: dict,
) -> dict | None:
    """Generate example using OpenAI."""
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.8,
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
            if attempt == MAX_RETRIES - 1:
                return None
        except Exception as e:
            print(f"  Unexpected error on attempt {attempt + 1}: {e}")
            if attempt == MAX_RETRIES - 1:
                return None
    return None


def get_example_id(service: ServiceType, index: int) -> str:
    """Generate a unique example ID."""
    prefix_map = {
        ServiceType.COHERENCE: "CE-EVAL",
        ServiceType.EXTRACTION: "EX-EVAL",
        ServiceType.RETRIEVAL: "RT-EVAL",
    }
    return f"{prefix_map[service]}-{index:04d}"


async def generate_coherence_examples(
    client: Any,
    scenario: dict,
    start_index: int,
    generate_fn: callable,
) -> list[dict]:
    """Generate coherence evaluation examples for a scenario."""
    examples = []
    schema = CoherenceExample.model_json_schema()

    system_prompt = COHERENCE_SYSTEM_PROMPT.format(
        language=scenario["language"],
        category=scenario["category"],
        difficulty=scenario["difficulty"],
    )

    for i in range(scenario["count"]):
        example_id = get_example_id(ServiceType.COHERENCE, start_index + i)
        user_prompt = f"""Generate evaluation example #{i+1} with ID '{example_id}' for category '{scenario['category']}'.

Schema:
{json.dumps(schema, indent=2)}

Requirements:
- Category: {scenario['category']}
- Language: {scenario['language']}
- Difficulty: {scenario['difficulty']}
- Make the clause realistic and domain-specific to construction/infrastructure contracts
- Include appropriate trigger_terms for detectable issues
- Provide coherence_score_range as [min, max] integers 0-100"""

        print(f"  Generating {example_id} ({scenario['category']})...")
        result = await generate_fn(client, system_prompt, user_prompt, schema)

        if result:
            result["id"] = example_id
            result["language"] = scenario["language"]
            result["difficulty"] = scenario["difficulty"]
            examples.append(result)
            print(f"  ✓ Generated {example_id}")
        else:
            print(f"  ✗ Failed to generate {example_id}")

    return examples


async def generate_extraction_examples(
    client: Any,
    scenario: dict,
    start_index: int,
    generate_fn: callable,
) -> list[dict]:
    """Generate extraction evaluation examples for a scenario."""
    examples = []
    schema = ExtractionExample.model_json_schema()

    system_prompt = EXTRACTION_SYSTEM_PROMPT.format(
        language=scenario["language"],
        category=scenario["category"],
        difficulty=scenario["difficulty"],
    )

    for i in range(scenario["count"]):
        example_id = get_example_id(ServiceType.EXTRACTION, start_index + i)
        user_prompt = f"""Generate evaluation example #{i+1} with ID '{example_id}' for category '{scenario['category']}'.

Schema:
{json.dumps(schema, indent=2)}

Requirements:
- Category: {scenario['category']}
- Language: {scenario['language']}
- Difficulty: {scenario['difficulty']}
- Document should contain extractable elements (clauses, actors, dates, amounts)
- Provide realistic confidence ranges based on extraction difficulty"""

        print(f"  Generating {example_id} ({scenario['category']})...")
        result = await generate_fn(client, system_prompt, user_prompt, schema)

        if result:
            result["id"] = example_id
            result["extraction_difficulty"] = scenario["difficulty"]
            examples.append(result)
            print(f"  ✓ Generated {example_id}")
        else:
            print(f"  ✗ Failed to generate {example_id}")

    return examples


async def generate_retrieval_examples(
    client: Any,
    scenario: dict,
    start_index: int,
    generate_fn: callable,
) -> list[dict]:
    """Generate retrieval evaluation examples for a scenario."""
    examples = []
    schema = RetrievalExample.model_json_schema()

    system_prompt = RETRIEVAL_SYSTEM_PROMPT.format(
        language=scenario["language"],
        category=scenario["category"],
    )

    for i in range(scenario["count"]):
        example_id = get_example_id(ServiceType.RETRIEVAL, start_index + i)
        user_prompt = f"""Generate evaluation example #{i+1} with ID '{example_id}' for category '{scenario['category']}'.

Schema:
{json.dumps(schema, indent=2)}

Requirements:
- Category: {scenario['category']}
- Language: {scenario['language']}
- Query should target specific contract clause types
- Use DOC-001 through DOC-015 as document IDs (they exist in the corpus)
- For {scenario['category']} queries, specify appropriate expected_intent"""

        print(f"  Generating {example_id} ({scenario['category']})...")
        result = await generate_fn(client, system_prompt, user_prompt, schema)

        if result:
            result["id"] = example_id
            result["difficulty"] = "medium"  # Default, can be overridden
            examples.append(result)
            print(f"  ✓ Generated {example_id}")
        else:
            print(f"  ✗ Failed to generate {example_id}")

    return examples


async def generate_service_dataset(
    service: ServiceType,
    max_count: int | None = None,
) -> dict:
    """Generate evaluation dataset for a specific service."""
    config = GENERATION_CONFIG[service]

    # Initialize client
    if USE_ANTHROPIC:
        client = anthropic.AsyncAnthropic()
        generate_fn = generate_with_anthropic
    else:
        client = openai.AsyncOpenAI()
        generate_fn = generate_with_openai

    print(f"\n{'='*60}")
    print(f"Generating {service.value} evaluation dataset")
    print(f"{'='*60}")

    all_examples = []
    current_index = 1000  # Start after seed dataset IDs

    # Map service to generator function
    generator_map = {
        ServiceType.COHERENCE: generate_coherence_examples,
        ServiceType.EXTRACTION: generate_extraction_examples,
        ServiceType.RETRIEVAL: generate_retrieval_examples,
    }

    generator = generator_map[service]

    for scenario in config["scenarios"]:
        if max_count and len(all_examples) >= max_count:
            break

        # Adjust count if max_count is specified
        scenario_count = scenario["count"]
        if max_count:
            remaining = max_count - len(all_examples)
            scenario_count = min(scenario_count, remaining)
            scenario = {**scenario, "count": scenario_count}

        print(f"\nScenario: {scenario['category']} ({scenario.get('language', 'mixed')})")
        examples = await generator(client, scenario, current_index, generate_fn)
        all_examples.extend(examples)
        current_index += len(examples)

    # Build dataset structure
    dataset = {
        "dataset_name": f"c2pro_{service.value}_eval_generated",
        "version": "1.1.0",
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "service": f"{service.value}_generated",
        "generation_metadata": {
            "model": DEFAULT_MODEL,
            "total_generated": len(all_examples),
            "generation_date": datetime.now().isoformat(),
        },
        "examples": all_examples,
    }

    return dataset


async def save_dataset(dataset: dict, output_path: Path) -> None:
    """Save dataset to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Saved dataset to {output_path}")
    print(f"  Total examples: {len(dataset['examples'])}")


async def main():
    parser = argparse.ArgumentParser(description="Generate evaluation datasets for C2PRO AI services")
    parser.add_argument(
        "--service",
        type=str,
        choices=["coherence", "extraction", "retrieval"],
        help="Service type to generate dataset for",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Maximum number of examples to generate",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate datasets for all services",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=BASE_DIR,
        help="Output directory for generated datasets",
    )

    args = parser.parse_args()

    if not args.service and not args.all:
        parser.error("Either --service or --all must be specified")

    # Check for API keys
    if USE_ANTHROPIC and not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        return
    elif not USE_ANTHROPIC and not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        return

    services_to_generate = []
    if args.all:
        services_to_generate = list(ServiceType)
    else:
        services_to_generate = [ServiceType(args.service)]

    for service in services_to_generate:
        dataset = await generate_service_dataset(service, args.count)
        output_path = args.output_dir / GENERATION_CONFIG[service]["output_file"]
        await save_dataset(dataset, output_path)

    print("\n" + "="*60)
    print("Dataset generation complete!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
