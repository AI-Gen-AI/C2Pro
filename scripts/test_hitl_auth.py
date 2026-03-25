import requests
import json
import os

url = "http://localhost:8000/api/v1/hitl/route"
token = os.getenv("C2PRO_HITL_TEST_TOKEN", "replace-me-with-a-local-dev-token")

headers = {
    "accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

payload = {
  "item_id": "712abbbf-a9ff-432c-b93a-c90bf9855ef4",
  "item_type": "analysis",
  "confidence": 0.20,
  "impact_level": "CRITICAL",
  "item_data": {
    "project_id": "38a0010f-4b1c-4135-9e46-a1af942c0a65",
    "risks_count": 7,
    "coherence_score": 100,
    "note": "Test HITL from Swagger"
  }
}

try:
    response = requests.post(url, headers=headers, json=payload)
    print(f"Status Code: {response.status_code}")
    print("Response Body:")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")
