from datetime import timezone
import asyncio
from uuid import uuid4
import jwt
from datetime import datetime, timedelta
import httpx
import asyncpg
from src.config import settings

async def run_flow():
    tenant_id = str(uuid4())
    user_id = str(uuid4())
    print(f"User: {user_id}, Tenant: {tenant_id}")
    
    conn = await asyncpg.connect("postgresql://postgres:postgres@postgres:5432/c2pro")
    
    await conn.execute("""
        INSERT INTO tenants (id, name, slug, is_active, subscription_plan, subscription_status, created_at, updated_at) 
        VALUES ($1, $2, $3, true, $4, $5, now(), now())
    """, tenant_id, "Test Tenant", f"test-{tenant_id}", "free", "active")
    
    await conn.execute("""
        INSERT INTO users (id, tenant_id, email, role, is_active, created_at, updated_at) 
        VALUES ($1, $2, $3, $4, true, now(), now())
    """, user_id, tenant_id, f"test-{user_id}@e2e.com", "admin")
    
    await conn.close()
    
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "email": f"test-{user_id}@e2e.com",
        "role": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(days=1),
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=120.0) as client:
        resp = await client.post("/api/v1/projects", json={
            "name": "E2E Real AI Test",
            "description": "Project for real AI flow",
            "owner": f"test-{user_id}@e2e.com",
            "category": "services",
            "budget": 100000,
            "currency": "EUR"
        }, headers=headers)
        if resp.status_code != 201:
            print(f"Failed to create project: {resp.status_code} {resp.text}")
            return
        project_id = resp.json()["id"]
        print(f"Project created: {project_id}")
        
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n5 0 obj\n<< /Length 44 >>\nstream\nBT\n/F1 12 Tf\n72 712 Td\n(Real Contract Test) Tj\nET\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000219 00000 n \n0000000306 00000 n \ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n399\n%%EOF"
        
        files = {"file": ("contract.pdf", pdf_content, "application/pdf")}
        data = {"document_type": "contract", "description": "Real contract for analysis", "metadata": "{}"}
        
        up_resp = await client.post(f"/api/v1/projects/{project_id}/documents", data=data, files=files, headers=headers)
        if up_resp.status_code not in (201, 202):
            print(f"Failed to upload document: {up_resp.status_code} {up_resp.text}")
            return
        doc_id = up_resp.json()["id"]
        print(f"Document uploaded: {doc_id}")
        
        print("Waiting for parsing (5 seconds)...")
        await asyncio.sleep(5)
        
        print("Running Analysis...")
        an_resp = await client.post("/api/v1/decision-intelligence/execute", json={
            "project_id": project_id,
            "document_id": doc_id,
            "analysis_type": "standard",
            "llm_provider": "anthropic"
        }, headers=headers)
        
        if an_resp.status_code != 200:
            print(f"Failed to run analysis: {an_resp.status_code} {an_resp.text}")
        else:
            print(f"Analysis started/completed: {an_resp.json()}")
            
        print("Running Coherence Evaluation...")
        coh_resp = await client.post("/api/v1/coherence/evaluate", json={
            "project_id": project_id,
            "document_id": doc_id
        }, headers=headers)
        if coh_resp.status_code != 200:
            print(f"Failed coherence: {coh_resp.status_code} {coh_resp.text}")
        else:
            print(f"Coherence Evaluation result: {coh_resp.json()}")

if __name__ == "__main__":
    asyncio.run(run_flow())
