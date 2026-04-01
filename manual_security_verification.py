
import os
import json
from pathlib import Path
from golden.loader import GoldenDatasetLoader, PathTraversalError, FileSizeError, MAX_FILE_SIZE_BYTES
from golden.schemas import GoldenCase, DifficultyLevel, CoherenceDimension, InputDocuments, TrajectoryConstraint
from pydantic import ValidationError

def test_manual_security_verification():
    # Setup temporary directory
    test_dir = Path("./temp_security_test")
    test_dir.mkdir(exist_ok=True)
    cases_dir = test_dir / "cases"
    cases_dir.mkdir(exist_ok=True)
    
    loader = GoldenDatasetLoader(test_dir)
    
    print("--- Manual Security Verification ---")
    
    # 1. Path Traversal Test (Unix-style)
    print("1. Testing Unix-style path traversal (../../../etc/passwd)...")
    try:
        result = loader.load_case("../../../etc/passwd")
        if result is None:
            print("✅ SUCCESS: Path traversal blocked (returned None).")
        else:
            print("❌ FAILED: Path traversal should have been blocked.")
    except Exception as e:
        print(f"✅ SUCCESS: Blocked with error: {type(e).__name__}")

    # 2. Path Traversal Test (Windows-style)
    print("2. Testing Windows-style path traversal (..\\..\\Windows)...")
    try:
        result = loader.load_case("..\\..\\Windows")
        if result is None:
            print("✅ SUCCESS: Path traversal blocked (returned None).")
        else:
            print("❌ FAILED: Path traversal should have been blocked.")
    except Exception as e:
        print(f"✅ SUCCESS: Blocked with error: {type(e).__name__}")

    # 3. File Size Limit Test
    print(f"3. Testing file size limit (>{MAX_FILE_SIZE_BYTES} bytes)...")
    large_file = cases_dir / "LARGE-001.json"
    with open(large_file, "wb") as f:
        f.seek(MAX_FILE_SIZE_BYTES + 1024)
        f.write(b" ")
    
    # Clear discovery cache
    loader.clear_cache()
    
    try:
        loader.load_case("LARGE-001")
        print("❌ FAILED: Large file should have been rejected.")
    except FileSizeError:
        print("✅ SUCCESS: Large file rejected (as expected).")
    except Exception as e:
        print(f"❌ FAILED: Unexpected error: {type(e).__name__}: {e}")
    finally:
        large_file.unlink()

    # 4. Metadata Depth Test
    print("4. Testing metadata depth limit (>5 levels)...")
    deep_metadata = {"a": {"b": {"c": {"d": {"e": {"f": "too deep"}}}}}}
    try:
        case = GoldenCase(
            case_id="SCHED-001",
            name="Deep Metadata Case",
            dimensions=[CoherenceDimension.Schedule],
            difficulty=DifficultyLevel.Easy,
            input_documents=InputDocuments(contract_path="c.pdf", schedule_path="s.mpp"),
            trajectory=TrajectoryConstraint(required_nodes=["node1"]),
            metadata=deep_metadata
        )
        print("❌ FAILED: Deep metadata should have been rejected.")
    except ValidationError as e:
        print("✅ SUCCESS: Deep metadata rejected (as expected).")
        # print(f"   Validation Error: {e}")

    # Cleanup
    import shutil
    shutil.rmtree(test_dir)
    print("--- Verification Complete ---")

if __name__ == "__main__":
    # Add apps/api/src to path for imports
    import sys
    sys.path.append(os.path.abspath("./apps/api/src"))
    test_manual_security_verification()
