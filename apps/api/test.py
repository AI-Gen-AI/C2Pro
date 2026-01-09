import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


def run_tests():
    """
    Loads .env.test and runs pytest.
    """
    print("Loading .env.test for test environment...")
    dotenv_path = Path(__file__).parent / ".env.test"
    if not dotenv_path.is_file():
        print(f"Error: .env.test file not found at {dotenv_path}")
        sys.exit(1)

    load_dotenv(dotenv_path)

    print("Running pytest...")
    # Ensure pytest is installed
    try:
        import pytest
    except ImportError:
        print("pytest is not installed. Installing now...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pytest", "pytest-asyncio", "python-dotenv"]
        )

    # Construct pytest command
    pytest_args = sys.argv[1:]  # Pass any additional arguments to pytest
    command = [sys.executable, "-m", "pytest"] + pytest_args

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Pytest exited with error: {e}")
        sys.exit(e.returncode)


if __name__ == "__main__":
    run_tests()
