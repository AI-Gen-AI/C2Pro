import json
import os
import sys

# Add apps/api to path
sys.path.append(os.path.join(os.getcwd(), "apps", "api"))

# Mock environment variables required by Settings
os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/db"
os.environ["SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "anon-key"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "service-role-key"
os.environ["JWT_SECRET_KEY"] = "secret-key"

from src.main import create_application

def export_openapi():
    app = create_application()
    openapi_schema = app.openapi()
    
    # Ensure the directory exists
    os.makedirs("apps/web/schema", exist_ok=True)
    
    with open("apps/web/schema/api.json", "w") as f:
        json.dump(openapi_schema, f, indent=2)
    
    print("Successfully exported OpenAPI schema to apps/web/schema/api.json")

if __name__ == "__main__":
    export_openapi()
