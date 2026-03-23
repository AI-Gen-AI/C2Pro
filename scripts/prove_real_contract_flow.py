#!/usr/bin/env python3
"""
Real contract end-to-end proof for analysis + checkpoint persistence.

Suite: AUDIT-TASK-3.1
Purpose: prove with a real uploaded contract that the full flow executes.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import httpx
import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


API_BASE_URL = "http://localhost:8000"
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/c2pro"

TEST_USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TEST_TENANT_ID = "11111111-1111-1111-1111-111111111111"
TEST_EMAIL = "test@example.com"
JWT_SECRET = "your-jwt-secret-at-least-32-chars-very-important-keep-secret"
ANALYSIS_ROUTE = "/api/v1/analysis/analyze"


def build_checkpoint(stage: str, proof_source: str, status: str, **details: str) -> dict[str, Any]:
    return {
        "stage": stage,
        "proof_source": proof_source,
        "status": status,
        "details": details,
    }


def create_token() -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": TEST_USER_ID,
        "tenant_id": TEST_TENANT_ID,
        "email": TEST_EMAIL,
        "role": "admin",
        "exp": now + timedelta(hours=1),
        "iat": now,
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def extract_text_from_pdf(file_path: Path) -> str:
    doc = fitz.open(file_path)
    try:
        text_parts: list[str] = []
        for page in doc:
            page_text = page.get_text("text")
            text_parts.append(str(page_text))
        text = "\n".join(text_parts).strip()
        if not text:
            raise ValueError("No extractable text found in PDF")
        return text
    finally:
        doc.close()


async def checkpoint_counts(engine) -> dict[str, int]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT
                  (SELECT COUNT(*) FROM checkpoints) AS checkpoints,
                  (SELECT COUNT(*) FROM checkpoint_writes) AS checkpoint_writes,
                  (SELECT COUNT(*) FROM checkpoint_blobs) AS checkpoint_blobs
                """
            )
        )
        row = result.fetchone()
        return {
            "checkpoints": int(row[0]),
            "checkpoint_writes": int(row[1]),
            "checkpoint_blobs": int(row[2]),
        }


async def wait_for_parsed_document(
    client: httpx.AsyncClient,
    project_id: str,
    document_id: str,
    headers: dict[str, str],
    attempts: int = 20,
    delay_seconds: int = 3,
) -> dict[str, Any]:
    for attempt in range(1, attempts + 1):
        response = await client.get(f"{API_BASE_URL}/api/v1/projects/{project_id}/documents", headers=headers)
        if response.status_code != 200:
            raise RuntimeError(f"Document list failed while waiting for parsed state: {response.status_code} {response.text}")

        items = response.json().get("items", [])
        match = next((item for item in items if item.get("id") == document_id), None)
        if match and match.get("status") == "parsed":
            return match

        print(f"[WAIT] Parsed checkpoint pending ({attempt}/{attempts})")
        await asyncio.sleep(delay_seconds)

    raise TimeoutError("Document never reached parsed state")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--contract",
        default="docs/assets/samples/contracts/3 East Coast PSU Phase 1 Project Integrated Risk Register.pdf",
        help="Path to a real contract PDF",
    )
    parser.add_argument(
        "--require-dashboard",
        action="store_true",
        help="Fail if coherence dashboard endpoint is not 200",
    )
    args = parser.parse_args()

    contract_path = Path(args.contract)
    if not contract_path.exists():
        print(f"[FAIL] Contract not found: {contract_path}")
        return 1

    print("=" * 80)
    print(" Real Contract Flow Proof")
    print("=" * 80)
    print(f"Contract: {contract_path}")
    verification_checkpoints: list[dict[str, Any]] = []

    token = create_token()
    headers = {"Authorization": f"Bearer {token}"}
    json_headers = {**headers, "Content-Type": "application/json"}

    engine = create_async_engine(DATABASE_URL, echo=False)
    before = await checkpoint_counts(engine)
    print(f"[DB BEFORE] {before}")

    extracted_text = extract_text_from_pdf(contract_path)
    print(f"[TEXT] Extracted {len(extracted_text)} chars from PDF")

    async with httpx.AsyncClient(timeout=120.0) as client:
        project_payload = {
            "name": f"Real Contract Proof {datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "description": "Manual proof run with real contract upload",
            "start_date": datetime.now().isoformat(),
            "end_date": (datetime.now() + timedelta(days=30)).isoformat(),
        }
        project_res = await client.post(f"{API_BASE_URL}/api/v1/projects", headers=json_headers, json=project_payload)
        if project_res.status_code != 201:
            print(f"[FAIL] Project create failed: {project_res.status_code} {project_res.text}")
            await engine.dispose()
            return 1
        project_id = project_res.json()["id"]
        print(f"[OK] Project created: {project_id}")

        with contract_path.open("rb") as f:
            upload_res = await client.post(
                f"{API_BASE_URL}/api/v1/projects/{project_id}/documents",
                headers=headers,
                files={"file": (contract_path.name, f, "application/pdf")},
                data={"document_type": "contract"},
            )
        if upload_res.status_code not in (201, 202):
            print(f"[FAIL] Upload failed: {upload_res.status_code} {upload_res.text}")
            await engine.dispose()
            return 1

        document_id = upload_res.json()["id"]
        print(f"[OK] Uploaded real contract: {document_id}")
        verification_checkpoints.append(
            build_checkpoint(
                "uploaded",
                "POST /api/v1/projects/{project_id}/documents",
                upload_res.json().get("processing_status", "queued"),
                document_id=document_id,
                task_id=upload_res.json().get("task_id", "unknown"),
            )
        )

        parsed_item = await wait_for_parsed_document(client, project_id, document_id, headers)
        print(f"[OK] Parsed checkpoint reached: {parsed_item['status']}")
        verification_checkpoints.append(
            build_checkpoint(
                "parsed",
                "GET /api/v1/projects/{project_id}/documents",
                parsed_item["status"],
                document_id=document_id,
                status_detail=parsed_item.get("status_detail", ""),
            )
        )

        analysis_payload = {
            "document_text": extracted_text,
            "project_id": project_id,
            "document_id": document_id,
        }
        analysis_res = await client.post(f"{API_BASE_URL}{ANALYSIS_ROUTE}", headers=json_headers, json=analysis_payload)
        if analysis_res.status_code != 200:
            print(f"[FAIL] Analysis failed: {analysis_res.status_code}")
            print(analysis_res.text)
            await engine.dispose()
            return 1

        body = analysis_res.json()
        print(f"[OK] Analysis status: {analysis_res.status_code}")
        print(f"[OK] Analysis ID: {body.get('analysis_id')}")
        print(f"[OK] WBS items: {len(body.get('wbs', []))}")
        print(f"[OK] Risks: {len(body.get('risks', []))}")
        verification_checkpoints.append(
            build_checkpoint(
                "analyzed",
                f"POST {ANALYSIS_ROUTE}",
                "completed",
                analysis_id=str(body.get("analysis_id") or ""),
                risks=str(len(body.get("risks", []))),
                wbs_items=str(len(body.get("wbs", []))),
            )
        )

        dashboard_res = await client.get(f"{API_BASE_URL}/api/coherence/dashboard/{project_id}", headers=headers)
        print(f"[INFO] Dashboard status: {dashboard_res.status_code}")
        if args.require_dashboard and dashboard_res.status_code != 200:
            print("[FAIL] Dashboard check required and endpoint did not return 200")
            await engine.dispose()
            return 1

    after = await checkpoint_counts(engine)
    await engine.dispose()
    print(f"[DB AFTER] {after}")

    growth = {k: after[k] - before[k] for k in before}
    print(f"[DB DELTA] {growth}")
    print(f"[CHECKPOINTS] {verification_checkpoints}")

    if growth["checkpoints"] <= 0 or growth["checkpoint_writes"] <= 0:
        print("[FAIL] No checkpoint growth detected")
        return 1

    print("[SUCCESS] Real contract upload + analysis flow proven")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
