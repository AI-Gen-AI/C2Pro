"""
Stress Test for C2Pro AI Ingestion and Analysis Pipeline

This script is designed to test the performance and stability of the AI pipeline
under heavy loads, including large document uploads and concurrent user activity.

It answers questions like:
- How does the system handle an 800-page PDF?
- Can the task queue (Celery) manage 10 simultaneous uploads?
- What is the end-to-end latency from upload to final analysis?

Requirements:
- fpdf2: `pip install fpdf2`
- httpx: `pip install httpx`
- tabulate: `pip install tabulate`

To Run:
1. Make sure the C2Pro backend API is running locally.
2. Set the environment variables below (e.g., in a `.env` file and run with `python -m dotenv run -- python tests/performance/stress_test_ai.py`).
3. Run the script: `python tests/performance/stress_test_ai.py`
"""

import asyncio
import os
import random
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Coroutine, Dict, List, Any, Tuple
import httpx
from dotenv import load_dotenv

# --- Dependency Check ---
try:
    from fpdf import FPDF
    from tabulate import tabulate
except ImportError:
    print("One or more required packages (fpdf2, tabulate) are not found.")
    print("Attempting to install them now...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "fpdf2", "tabulate"])
        from fpdf import FPDF
        from tabulate import tabulate
        print("Packages installed successfully.")
    except Exception as e:
        print(f"Failed to install packages: {e}")
        print("Please install them manually: pip install fpdf2 tabulate")
        sys.exit(1)


# --- Configuration ---
load_dotenv()
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
# IMPORTANT: This should be a valid JWT for an existing user/tenant
# You can get this from your frontend's local storage after logging in.
AUTH_TOKEN = os.getenv("C2PRO_AUTH_TOKEN")
# IMPORTANT: This should be a valid UUID of a project belonging to the user's tenant
PROJECT_ID = os.getenv("C2PRO_PROJECT_ID")

if not AUTH_TOKEN or not PROJECT_ID:
    print("Error: C2PRO_AUTH_TOKEN and C2PRO_PROJECT_ID must be set in your environment.")
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {AUTH_TOKEN}"}
TEMP_DIR = Path(__file__).parent / "temp_stress_test_docs"
TEMP_DIR.mkdir(exist_ok=True)

# --- Test Scenarios ---
SCENARIOS = [
    # desc, page_count, concurrency, doc_type
    ("Small Doc, Single User", 10, 1, "CONTRACT"),
    ("Medium Doc, Single User", 100, 1, "SCHEDULE"),
    ("Large Doc, Single User", 500, 1, "CONTRACT"),
    ("Medium Docs, 5 Concurrent Users", 50, 5, "BUDGET"),
    ("Large Docs, 3 Concurrent Users", 200, 3, "CONTRACT"),
]

# --- Cost Estimation ---
# Based on Claude 3.5 Sonnet pricing (July 2024): $3/million input, $15/million output
# Assuming a 5x expansion factor for output (analysis is larger than input)
# Average tokens per word is ~1.3
TOKEN_PER_WORD_RATIO = 1.3
COST_PER_INPUT_TOKEN = 3 / 1_000_000
COST_PER_OUTPUT_TOKEN = 15 / 1_000_000
COST_ESTIMATION_THRESHOLD_USD = 0.50  # Warn if a single doc processing costs > $0.50

# --- Legal Text for PDF Generation ---
LEGAL_TEXT = """
This Agreement is made and entered into as of this [Date], by and between [Party A], a [State of Incorporation] corporation with its principal place of business at [Address] ("Client"), and [Party B], a [State of Incorporation] corporation with its principal place of business at [Address] ("Contractor").
WHEREAS, Client desires to engage Contractor to perform certain services as set forth in this Agreement; and
WHEREAS, Contractor has the skills, qualifications, and expertise to perform such services;
NOW, THEREFORE, in consideration of the mutual covenants and promises contained herein, the parties agree as follows:
1. Scope of Work. Contractor shall perform the services described in Exhibit A attached hereto (the "Services"). Contractor shall perform the Services in a professional and workmanlike manner, in accordance with all applicable laws and industry standards. Client may request changes to the Scope of Work in writing, and any such changes shall be subject to mutual agreement of the parties, including adjustments to the compensation and schedule.
2. Term. The term of this Agreement shall commence on the date hereof and shall continue until the Services are completed, or until earlier terminated as provided herein.
3. Compensation. In consideration for the Services, Client shall pay Contractor the fees set forth in Exhibit B. Payment shall be made within thirty (30) days of receipt of Contractor's invoice. Late payments shall accrue interest at a rate of 1.5% per month.
4. Confidentiality. Each party agrees to maintain in confidence all proprietary and confidential information of the other party. This obligation shall survive the termination of this Agreement.
5. Intellectual Property. All intellectual property developed or created by Contractor in the course of performing the Services shall be the sole and exclusive property of the Client.
6. Warranties. Contractor warrants that the Services will be performed in a professional manner and will conform to the specifications set forth in Exhibit A.
7. Limitation of Liability. IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES ARISING OUT OF THIS AGREEMENT.
8. Governing Law. This Agreement shall be governed by and construed in accordance with the laws of the State of [State].
9. Entire Agreement. This Agreement constitutes the entire agreement between the parties and supersedes all prior oral or written agreements or understandings.
"

def generate_large_pdf(page_count: int, output_path: Path) -> int:
    """Generates a PDF with a specified number of pages."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    word_count = 0
    for i in range(page_count):
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        
        # Add a title for each page to make them slightly different
        pdf.cell(200, 10, txt=f"Page {i + 1} of {page_count} - Stress Test Document", ln=True, align='C')
        
        # Add the legal text multiple times to fill the page
        full_page_text = LEGAL_TEXT * 3 # Repeat text to fill page
        pdf.multi_cell(0, 5, txt=full_page_text)
        word_count += len(full_page_text.split())

    pdf.output(output_path)
    return word_count


async def poll_document_status(client: httpx.AsyncClient, document_id: str) -> Dict[str, Any]:
    """Polls the document list endpoint to get the status of a specific document."""
    url = f"{API_BASE_URL}/projects/{PROJECT_ID}/documents"
    while True:
        try:
            response = await client.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            data = response.json()
            # The response is a list, find our document
            for doc in data.get("items", []):
                if doc["id"] == document_id:
                    if doc["status"] in ["PARSED", "ERROR"]:
                        return doc
            # If not found or status not final, wait and retry
            await asyncio.sleep(5)
        except httpx.ReadTimeout:
            print(f"Polling timeout for doc {document_id}, retrying...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"An error occurred while polling for doc {document_id}: {e}")
            return {"status": "ERROR", "error_message": str(e)}


def upload_and_monitor(file_path: Path, doc_type: str, total_words: int) -> Dict[str, Any]:
    """Uploads a single document and monitors its processing time."""
    start_time = time.time()
    results = {
        "filename": file_path.name,
        "status": "FAIL",
        "total_time": 0,
        "upload_to_queued_time": 0,
        "queued_to_parsed_time": 0,
        "cost_warning": "N/A"
    }

    try:
        async with httpx.AsyncClient() as client:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "application/pdf")}
                data = {"document_type": doc_type}
                
                print(f"Uploading {file_path.name}...")
                upload_start_time = time.time()
                response = await client.post(
                    f"{API_BASE_URL}/projects/{PROJECT_ID}/documents",
                    files=files,
                    data=data,
                    headers=HEADERS,
                    timeout=120, # Generous timeout for large files
                )
                response.raise_for_status()
                
            upload_time = time.time() - upload_start_time
            results["upload_to_queued_time"] = upload_time
            
            resp_data = response.json()
            document_id = resp_data["id"]
            print(f"Upload successful for {file_path.name} (Doc ID: {document_id}). Took {upload_time:.2f}s. Now polling for 'PARSED' status...")

            # Cost estimation
            input_tokens = total_words * TOKEN_PER_WORD_RATIO
            output_tokens = input_tokens * 5  # Estimated 5x expansion
            estimated_cost = (input_tokens * COST_PER_INPUT_TOKEN) + (output_tokens * COST_PER_OUTPUT_TOKEN)
            if estimated_cost > COST_ESTIMATION_THRESHOLD_USD:
                results["cost_warning"] = f"Estimated cost ${estimated_cost:.4f} exceeds threshold of ${COST_ESTIMATION_THRESHOLD_USD:.2f}"
                print(f"WARNING: {results['cost_warning']}")

            # Polling
            polling_start_time = time.time()
            final_status_data = await poll_document_status(client, document_id)
            polling_time = time.time() - polling_start_time
            results["queued_to_parsed_time"] = polling_time

            if final_status_data["status"] == "PARSED":
                results["status"] = "PASS"
            else:
                results["status"] = "FAIL"
                print(f"Processing failed for {document_id}: {final_status_data.get('error_message')}")

    except httpx.HTTPStatusError as e:
        print(f"HTTP error for {file_path.name}: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"An unexpected error occurred for {file_path.name}: {e}")

    results["total_time"] = time.time() - start_time
    return results


async def run_test_scenario(
    desc: str, page_count: int, concurrency: int, doc_type: str
) -> List[Dict[str, Any]]:
    """Runs a single scenario, either single or concurrent uploads."""
    print("\n" + "="*50)
    print(f"Running Scenario: {desc}")
    print(f"Pages: {page_count}, Concurrent Users: {concurrency}, Doc Type: {doc_type}")
    print("="*50)

    # Generate a base document for this scenario
    doc_path = TEMP_DIR / f"doc_{page_count}p.pdf"
    print(f"Generating a {page_count}-page PDF...")
    total_words = generate_large_pdf(page_count, doc_path)
    print(f"PDF generated at {doc_path} ({doc_path.stat().st_size / 1_000_000:.2f} MB)")

    tasks: List[Coroutine] = []
    for i in range(concurrency):
        # In a real concurrent test, we might generate unique files
        # but for this purpose, uploading the same file is sufficient
        # to test the server's handling of concurrent requests.
        task = upload_and_monitor(doc_path, doc_type, total_words)
        tasks.append(task)
    
    scenario_results = await asyncio.gather(*tasks)
    return scenario_results


def main():
    """Main function to run all stress test scenarios."""
    all_results_for_report: List[Tuple[str, int, int, str, str]] = []
    start_time = time.time()

    for desc, page_count, concurrency, doc_type in SCENARIOS:
        loop = asyncio.get_event_loop()
        scenario_results = loop.run_until_complete(
            run_test_scenario(desc, page_count, concurrency, doc_type)
        )

        # For reporting, we'll aggregate the results of a concurrent run
        total_time = max(r["total_time"] for r in scenario_results)
        num_passed = sum(1 for r in scenario_results if r["status"] == "PASS")
        status = f"{num_passed}/{concurrency} PASS"

        # Get size of the generated doc
        doc_path = TEMP_DIR / f"doc_{page_count}p.pdf"
        size_mb = f"{doc_path.stat().st_size / 1_000_000:.2f}MB"

        # Check for warnings
        warnings = [r.get("cost_warning", "N/A") for r in scenario_results]
        has_warning = any(w != "N/A" for w in warnings)
        
        report_status = status
        if has_warning:
            report_status += " (Cost Warning)"
        if "FAIL" in status:
            report_status = "FAIL"


        all_results_for_report.append(
            (size_mb, page_count, concurrency, f"{total_time:.2f}s", report_status)
        )

    print("\n" + "="*80)
    print("Stress Test Summary")
    print("="*80)

    headers = ["Doc Size", "Pages", "Concurrent Users", "Total Time", "Status"]
    print(tabulate(all_results_for_report, headers=headers, tablefmt="grid"))
    
    total_duration = time.time() - start_time
    print(f"\nTotal stress test duration: {total_duration:.2f} seconds.")

    # Clean up generated files
    for p in TEMP_DIR.glob("*.pdf"):
        p.unlink()
    TEMP_DIR.rmdir()
    print("Temporary files cleaned up.")


if __name__ == "__main__":
    main()
