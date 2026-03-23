import json

def analyze_openapi():
    with open("apps/web/schema/api.json", "r") as f:
        schema = json.load(f)
    
    paths = schema.get("paths", {})
    
    print(f"Total endpoints found: {len(paths)}")
    print("\nEndpoint List:")
    for path, methods in sorted(paths.items()):
        for method in methods.keys():
            if method.lower() in ['get', 'post', 'put', 'patch', 'delete']:
                print(f"{method.upper()} {path}")

if __name__ == "__main__":
    analyze_openapi()
