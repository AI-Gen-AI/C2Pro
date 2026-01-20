"""
C2Pro - Spacy Model Installer

This script installs the Spanish language model for Spacy.

The model is large (~500MB) so it's installed separately from requirements.txt.

Models:
- es_core_news_lg (large, ~500MB, better accuracy)
- es_core_news_md (medium, ~100MB, fallback)

Usage:
    python install_spacy_model.py

Or manually:
    python -m spacy download es_core_news_lg
"""

import subprocess
import sys


def install_model(model_name: str) -> bool:
    """
    Install a Spacy model.

    Args:
        model_name: Name of the model to install

    Returns:
        True if successful, False otherwise
    """
    print(f"Installing Spacy model: {model_name}...")
    print("This may take a few minutes (model is ~500MB)...")

    try:
        subprocess.check_call([
            sys.executable,
            "-m",
            "spacy",
            "download",
            model_name
        ])
        print(f"✓ Model {model_name} installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install {model_name}: {e}")
        return False


def main():
    """Install required Spacy models for Spanish."""
    print("=" * 60)
    print("C2PRO - Spacy Model Installation")
    print("=" * 60)
    print()

    # Try to install large model first (best accuracy)
    success = install_model("es_core_news_lg")

    if not success:
        print()
        print("Large model installation failed.")
        print("Trying medium model as fallback...")
        print()
        success = install_model("es_core_news_md")

    print()
    print("=" * 60)

    if success:
        print("✓ Installation complete!")
        print()
        print("The PII Anonymizer service is now ready to use.")
    else:
        print("✗ Installation failed!")
        print()
        print("Please install manually with:")
        print("  python -m spacy download es_core_news_lg")
        sys.exit(1)


if __name__ == "__main__":
    main()
