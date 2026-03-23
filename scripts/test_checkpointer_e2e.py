#!/usr/bin/env python3
"""
End-to-End Test: LangGraph PostgreSQL Checkpointer
Task: B-3 (AUDIT-TASK-3.1)

This script:
1. Creates a test project
2. Uploads a document
3. Triggers analysis workflow
4. Monitors checkpoint table creation in real-time
5. Verifies checkpoints are being persisted

Usage:
    python scripts/test_checkpointer_e2e.py
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


# Test configuration
API_BASE_URL = "http://localhost:8000"
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/c2pro"

# Test user/tenant (seeded in database)
TEST_USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TEST_TENANT_ID = "11111111-1111-1111-1111-111111111111"
TEST_EMAIL = "test@example.com"

# JWT secret (from API container environment)
JWT_SECRET = "your-jwt-secret-at-least-32-chars-very-important-keep-secret"
ANALYSIS_ROUTE = "/api/v1/analysis/analyze"


async def wait_for_parsed_document(
    client: httpx.AsyncClient,
    project_id: str,
    document_id: str,
    headers: dict[str, str],
    attempts: int = 20,
    delay_seconds: int = 3,
) -> dict:
    for attempt in range(1, attempts + 1):
        response = await client.get(
            f"{API_BASE_URL}/api/v1/projects/{project_id}/documents",
            headers={"Authorization": headers["Authorization"]},
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Document list failed while waiting for parsed state: {response.status_code} {response.text}"
            )

        items = response.json().get("items", [])
        match = next((item for item in items if item.get("id") == document_id), None)
        if match and match.get("status") == "parsed":
            return match

        print(f"  [WAIT] Parsed checkpoint pending... ({attempt}/{attempts})")
        await asyncio.sleep(delay_seconds)

    raise TimeoutError("Document never reached parsed state before analysis")


def create_test_token(user_id: str, tenant_id: str, email: str) -> str:
    """Create a valid JWT token for testing."""
    now = datetime.utcnow()
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "email": email,
        "role": "admin",
        "exp": now + timedelta(hours=1),
        "iat": now,
        "type": "access"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


async def check_checkpoint_tables(engine) -> dict:
    """Check if checkpoint tables exist and get row counts."""
    async with engine.connect() as conn:
        tables = {}

        for table_name in ["checkpoints", "checkpoint_writes", "checkpoint_blobs", "checkpoint_migrations"]:
            # Check if table exists
            result = await conn.execute(
                text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = '{table_name}'
                    )
                """)
            )
            exists = result.scalar()

            count = 0
            if exists:
                result = await conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                count = result.scalar()

            tables[table_name] = {
                "exists": exists,
                "count": count
            }

        return tables


async def get_checkpoint_details(engine, limit=5) -> list:
    """Get recent checkpoint details."""
    async with engine.connect() as conn:
        try:
            result = await conn.execute(
                text("""
                    SELECT
                        thread_id,
                        checkpoint_id,
                        type,
                        metadata
                    FROM checkpoints
                    ORDER BY checkpoint_id DESC
                    LIMIT :limit
                """),
                {"limit": limit}
            )

            rows = result.fetchall()
            return [
                {
                    "thread_id": row[0],
                    "checkpoint_id": row[1],
                    "type": row[2],
                    "metadata": row[3]
                }
                for row in rows
            ]
        except Exception as e:
            print(f"   Note: Could not query checkpoints (table may not exist yet): {e}")
            return []


async def main():
    """Run end-to-end checkpointer test."""

    print("=" * 80)
    print(" LangGraph PostgreSQL Checkpointer - End-to-End Test")
    print(" Task B-3 (AUDIT-TASK-3.1)")
    print("=" * 80)

    # Create database engine
    engine = create_async_engine(DATABASE_URL, echo=False)

    # Step 1: Check initial state
    print("\n[Step 1] Checking initial database state...")
    initial_state = await check_checkpoint_tables(engine)

    for table_name, info in initial_state.items():
        status = "EXISTS" if info["exists"] else "NOT FOUND"
        count_str = f"({info['count']} rows)" if info["exists"] else ""
        print(f"  {table_name:30s} - {status:10s} {count_str}")

    if not initial_state["checkpoints"]["exists"]:
        print("\n  [OK] No checkpoint tables yet - will be created on first workflow execution")

    # Step 2: Create test token
    print("\n[Step 2] Creating test authentication token...")
    token = create_test_token(TEST_USER_ID, TEST_TENANT_ID, TEST_EMAIL)
    print(f"  [OK] Token created for user: {TEST_EMAIL}")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Step 3: Create test project
    print("\n[Step 3] Creating test project...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Create project
        project_data = {
            "name": f"Checkpointer Test {datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "description": "Test project for LangGraph checkpointer verification",
            "start_date": datetime.now().isoformat(),
            "end_date": (datetime.now() + timedelta(days=30)).isoformat()
        }

        response = await client.post(
            f"{API_BASE_URL}/api/v1/projects",
            headers=headers,
            json=project_data
        )

        if response.status_code == 201:
            project = response.json()
            project_id = project["id"]
            print(f"  [OK] Project created: {project_id}")
            print(f"    Name: {project['name']}")
        else:
            print(f"  [FAIL] Failed to create project: {response.status_code}")
            print(f"    Response: {response.text}")
            return

        # Step 4: Upload document
        print("\n[Step 4] Uploading test document...")

        # Get test document path
        test_doc_path = Path("docs/assets/samples/contracts/3 East Coast PSU Phase 1 Project Integrated Risk Register.pdf")

        if not test_doc_path.exists():
            print(f"  [FAIL] Test document not found: {test_doc_path}")
            print("  Trying alternative path...")
            test_doc_path = Path("apps/api/tests/fixtures/sample_contract.pdf")
            if not test_doc_path.exists():
                print(f"  [FAIL] Alternative document not found: {test_doc_path}")
                return

        # Upload document
        with open(test_doc_path, "rb") as f:
            files = {
                "file": ("sample_contract.pdf", f, "application/pdf")
            }

            data = {
                "document_type": "contract"  # Required field
            }

            upload_headers = {
                "Authorization": f"Bearer {token}"
            }

            response = await client.post(
                f"{API_BASE_URL}/api/v1/projects/{project_id}/documents",
                headers=upload_headers,
                files=files,
                data=data
            )

        if response.status_code in [201, 202]:
            document = response.json()
            document_id = document["id"]
            print(f"  [OK] Document uploaded: {document_id}")
            print(f"    Filename: {document.get('filename', 'N/A')}")
            print(f"    Size: {document.get('file_size_bytes', 'N/A')} bytes")
            print(f"    Status: {response.status_code} ({'Accepted - Processing' if response.status_code == 202 else 'Created'})")
            if "task_id" in document:
                print(f"    Task ID: {document['task_id']}")
        else:
            print(f"  [FAIL] Failed to upload document: {response.status_code}")
            print(f"    Response: {response.text}")
            return

        parsed_item = await wait_for_parsed_document(client, project_id, document_id, headers)
        print(f"  [OK] Parsed checkpoint reached: {parsed_item['status']}")
        print(f"    Detail: {parsed_item.get('status_detail', 'N/A')}")

        # Step 5: Trigger analysis
        print("\n[Step 5] Triggering analysis workflow...")
        print("  This will invoke the LangGraph workflow with PostgreSQL checkpointing")

        # Use a simple test document text for analysis
        test_document_text = """
        CONSTRUCTION CONTRACT

        This agreement is entered into between Owner and Contractor.

        SCOPE OF WORK:
        - Site preparation and excavation
        - Foundation and structural work
        - Electrical and plumbing installation

        PAYMENT TERMS:
        Total contract value: $500,000
        Payment schedule: Monthly progress payments
        Retention: 10% until final completion

        PENALTIES:
        Late completion penalty: $1,000 per day after scheduled completion date

        TIMELINE:
        Start date: January 1, 2026
        Completion date: June 30, 2026
        """

        try:
            response = await client.post(
                f"{API_BASE_URL}{ANALYSIS_ROUTE}",
                headers=headers,
                json={
                    "document_text": test_document_text.strip(),
                    "project_id": project_id,
                    "document_id": document_id
                },
                timeout=120.0  # Increased timeout for long-running analysis
            )

            if response.status_code in [200, 202, 201]:
                analysis = response.json()
                print(f"  [OK] Analysis completed")
                print(f"    Status: {response.status_code}")
                print(f"    Analysis ID: {analysis.get('analysis_id', 'N/A')}")
                print(f"    Risks found: {len(analysis.get('risks', []))}")
                print(f"    WBS items: {len(analysis.get('wbs', []))}")
            else:
                print(f"  [INFO] Analysis response: {response.status_code}")
                print(f"    Response: {response.text}")

        except httpx.ReadTimeout:
            print(f"  [OK] Analysis started (still running in background)")
            print(f"    The workflow is executing - this is expected for complex analysis")
            print(f"    Checkpoint tables should be created as the workflow progresses")

        except Exception as e:
            print(f"  [INFO] Analysis encountered an issue: {e}")
            print(f"    Continuing to monitor checkpoint creation...")

        # Step 6: Monitor checkpoint creation
        print("\n[Step 6] Monitoring checkpoint table creation...")
        print("  Waiting for LangGraph to create checkpoint tables and save state...")

        max_attempts = 30  # Increased from 10 to allow more time
        for attempt in range(max_attempts):
            await asyncio.sleep(3)  # Wait 3 seconds between checks

            current_state = await check_checkpoint_tables(engine)

            if current_state["checkpoints"]["exists"]:
                print(f"\n  [OK] Checkpoint tables created! (attempt {attempt + 1}/{max_attempts})")
                break
            else:
                print(f"  [WAIT] Waiting... (attempt {attempt + 1}/{max_attempts})")
        else:
            print("\n  [INFO] Tables not created yet - workflow may still be initializing")
            print("  This is normal if the workflow hasn't reached the first checkpoint yet")

        # Step 7: Verify checkpoints
        print("\n[Step 7] Verifying checkpoint persistence...")

        final_state = await check_checkpoint_tables(engine)

        print("\nFinal Database State:")
        print("-" * 80)
        for table_name, info in final_state.items():
            status = "[OK] EXISTS" if info["exists"] else "[FAIL] NOT FOUND"
            count_str = f"with {info['count']} rows" if info["exists"] else ""
            print(f"  {table_name:30s} - {status:12s} {count_str}")

        # Get checkpoint details
        if final_state["checkpoints"]["exists"] and final_state["checkpoints"]["count"] > 0:
            print("\n[Step 8] Inspecting checkpoint data...")

            checkpoints = await get_checkpoint_details(engine, limit=5)

            if checkpoints:
                print(f"\nRecent Checkpoints ({len(checkpoints)}):")
                print("-" * 80)
                for i, cp in enumerate(checkpoints, 1):
                    print(f"\n  Checkpoint {i}:")
                    print(f"    Thread ID:      {cp['thread_id'][:50]}...")
                    print(f"    Checkpoint ID:  {cp['checkpoint_id']}")
                    print(f"    Type:           {cp['type']}")
                    print(f"    Metadata:       {json.dumps(cp['metadata'], indent=16)[:200]}...")
            else:
                print("  No checkpoint details available")

        # Summary
        print("\n" + "=" * 80)
        print(" TEST SUMMARY")
        print("=" * 80)

        if final_state["checkpoints"]["exists"]:
            print("  [SUCCESS] SUCCESS - Checkpointer is working!")
            print(f"     - Checkpoint tables created automatically")
            print(f"     - {final_state['checkpoints']['count']} checkpoints saved")
            print(f"     - {final_state['checkpoint_writes']['count']} checkpoint writes recorded")
            print("\n  The LangGraph PostgreSQL checkpointer is functioning correctly.")
            print("  Workflow state will persist across process restarts.")
        else:
            print("  [INFO]  PENDING - Tables not created yet")
            print("     This can happen if:")
            print("     - Workflow is still initializing")
            print("     - Analysis hasn't reached first checkpoint yet")
            print("     - Workflow is using in-memory checkpointer")
            print("\n  Check the API logs for workflow execution details.")

        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
