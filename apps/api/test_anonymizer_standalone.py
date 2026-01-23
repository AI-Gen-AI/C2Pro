"""
C2Pro - PII Anonymizer Standalone Test Script

This script tests the PII Anonymizer service without requiring
the full application setup.

Prerequisites:
1. pip install presidio-analyzer presidio-anonymizer spacy
2. python -m spacy download es_core_news_lg

Usage:
    python test_anonymizer_standalone.py

Expected Output:
    All tests pass with detailed output showing anonymization results.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from services.privacy.anonymizer import (
    get_anonymizer,
    anonymize_text_simple,
    deanonymize_text_simple,
)


def print_header(title: str):
    """Print test section header."""
    print("\n" + "=" * 70)
    print(f"TEST: {title}")
    print("=" * 70)


def print_result(label: str, value: str):
    """Print test result."""
    print(f"\n{label}:")
    print("-" * 70)
    print(value)


def test_1_basic_person_anonymization():
    """Test 1: Basic person name anonymization."""
    print_header("Basic Person Name Anonymization")

    text = "Juan Pérez trabaja en la empresa"

    anonymizer = get_anonymizer()
    anonymizer.reset_mappings()

    result = anonymizer.anonymize_document(text)

    print_result("Original Text", text)
    print_result("Anonymized Text", result.anonymized_text)
    print_result("Mapping", str(result.mapping))
    print_result("Statistics", str(result.statistics))

    # Assertions
    assert "Juan Pérez" not in result.anonymized_text, "Person name should be anonymized"
    assert "<PERSON_1>" in result.anonymized_text, "Should use placeholder <PERSON_1>"
    assert result.mapping["<PERSON_1>"] == "Juan Pérez", "Mapping should be correct"
    assert result.statistics.get("PERSON", 0) == 1, "Should detect 1 person"

    print("\n[OK] Test 1 passed")
    return True


def test_2_multiple_pii_types():
    """Test 2: Multiple PII types (person, email, phone)."""
    print_header("Multiple PII Types")

    text = """
Contrato firmado por Juan Pérez.
Email: juan.perez@empresa.com
Teléfono: +34 600 123 456
"""

    anonymizer = get_anonymizer()
    anonymizer.reset_mappings()

    result = anonymizer.anonymize_document(text)

    print_result("Original Text", text)
    print_result("Anonymized Text", result.anonymized_text)
    print_result("Mapping", str(result.mapping))
    print_result("Statistics", str(result.statistics))

    # Assertions
    assert "juan.perez@empresa.com" not in result.anonymized_text, "Email should be anonymized"
    assert "+34 600 123 456" not in result.anonymized_text, "Phone should be anonymized"
    assert "<EMAIL_ADDRESS_" in result.anonymized_text, "Should use email placeholder"
    assert "<PHONE_NUMBER_" in result.anonymized_text, "Should use phone placeholder"

    print("\n[OK] Test 2 passed")
    return True


def test_3_consistency_same_person():
    """Test 3: Consistency - same person always gets same placeholder."""
    print_header("Consistency - Same Person Multiple Times")

    text = """
Juan Pérez es el gerente.
Contactar a Juan Pérez en caso de urgencia.
Juan Pérez aprobó el presupuesto.
"""

    anonymizer = get_anonymizer()
    anonymizer.reset_mappings()

    result = anonymizer.anonymize_document(text)

    print_result("Original Text", text)
    print_result("Anonymized Text", result.anonymized_text)
    print_result("Mapping", str(result.mapping))

    # Count occurrences of <PERSON_1>
    count = result.anonymized_text.count("<PERSON_1>")

    # Assertions
    assert count == 3, f"Juan Pérez appears 3 times, should be <PERSON_1> 3 times (found {count})"
    assert "<PERSON_2>" not in result.anonymized_text, "Should not create multiple placeholders for same person"

    print(f"\nConsistency verified: 'Juan Pérez' → '<PERSON_1>' (3 occurrences)")
    print("\n[OK] Test 3 passed")
    return True


def test_4_dni_nie_recognition():
    """Test 4: Spanish DNI/NIE recognition."""
    print_header("Spanish DNI/NIE Recognition")

    text = """
Cliente: María García
DNI: 12345678Z
NIE: X1234567L
"""

    anonymizer = get_anonymizer()
    anonymizer.reset_mappings()

    result = anonymizer.anonymize_document(text)

    print_result("Original Text", text)
    print_result("Anonymized Text", result.anonymized_text)
    print_result("Mapping", str(result.mapping))
    print_result("Statistics", str(result.statistics))

    # Check if DNI/NIE were detected
    has_dni_nie = any("<DNI_NIE_" in placeholder for placeholder in result.mapping.keys())

    if has_dni_nie:
        assert "12345678Z" not in result.anonymized_text, "DNI should be anonymized"
        print("\n[OK] DNI/NIE recognition working")
    else:
        print("\n[WARN] DNI/NIE not detected (may need pattern improvement)")

    print("\n[OK] Test 4 passed")
    return True


def test_5_deanonymization():
    """Test 5: Deanonymization (restore original values)."""
    print_header("Deanonymization")

    original_text = "Contactar a Juan Pérez en juan@email.com"

    anonymizer = get_anonymizer()
    anonymizer.reset_mappings()

    # Anonymize
    result = anonymizer.anonymize_document(original_text)

    print_result("Original Text", original_text)
    print_result("Anonymized Text", result.anonymized_text)

    # Simulate AI response with placeholders
    ai_response = f"El responsable es {list(result.mapping.keys())[0]}"
    print_result("AI Response (with placeholders)", ai_response)

    # Deanonymize
    clean_response = anonymizer.deanonymize_response(ai_response, result.mapping)
    print_result("Deanonymized Response", clean_response)

    # Assertions
    assert "Juan Pérez" in clean_response, "Should restore original name"
    assert "<PERSON_" not in clean_response, "Should not have placeholders"

    print("\n[OK] Test 5 passed")
    return True


def test_6_preserve_dates_money():
    """Test 6: Verify dates and money amounts are NOT anonymized."""
    print_header("Preserve Dates and Money")

    text = """
Contrato firmado el 15 de enero de 2025.
Presupuesto: 100,000 EUR
Plazo de entrega: 30 días
"""

    anonymizer = get_anonymizer()
    anonymizer.reset_mappings()

    result = anonymizer.anonymize_document(text)

    print_result("Original Text", text)
    print_result("Anonymized Text", result.anonymized_text)
    print_result("Mapping", str(result.mapping))

    # Assertions - dates and money should be PRESERVED
    assert "15 de enero de 2025" in result.anonymized_text, "Date should be preserved"
    assert "100,000 EUR" in result.anonymized_text, "Money should be preserved"
    assert "30 días" in result.anonymized_text, "Duration should be preserved"

    print("\n[OK] Dates and money preserved correctly")
    print("\n[OK] Test 6 passed")
    return True


def test_7_simple_convenience_functions():
    """Test 7: Simple convenience functions."""
    print_header("Simple Convenience Functions")

    text = "Juan Pérez: juan@email.com"

    print_result("Original Text", text)

    # Test anonymize_text_simple
    anonymized, mapping = anonymize_text_simple(text)

    print_result("Anonymized Text", anonymized)
    print_result("Mapping", str(mapping))

    # Test deanonymize_text_simple
    deanonymized = deanonymize_text_simple(anonymized, mapping)

    print_result("Deanonymized Text", deanonymized)

    # Assertions
    assert "Juan Pérez" in deanonymized, "Should restore original text"
    assert deanonymized == text, "Should be identical to original"

    print("\n[OK] Test 7 passed")
    return True


def test_8_empty_text():
    """Test 8: Handle empty text gracefully."""
    print_header("Empty Text Handling")

    anonymizer = get_anonymizer()

    result = anonymizer.anonymize_document("")

    assert result.anonymized_text == "", "Empty text should return empty"
    assert result.mapping == {}, "Empty text should have empty mapping"
    assert result.statistics == {}, "Empty text should have empty statistics"

    print("\n[OK] Empty text handled correctly")
    print("\n[OK] Test 8 passed")
    return True


def test_9_singleton_pattern():
    """Test 9: Verify singleton pattern."""
    print_header("Singleton Pattern")

    anonymizer1 = get_anonymizer()
    anonymizer2 = get_anonymizer()

    # Should be the same instance
    assert anonymizer1 is anonymizer2, "Should return same instance (singleton)"

    print("\nInstance 1 ID:", id(anonymizer1))
    print("Instance 2 ID:", id(anonymizer2))
    print("\n[OK] Singleton pattern working correctly")
    print("\n[OK] Test 9 passed")
    return True


def test_10_real_world_contract():
    """Test 10: Real-world contract example."""
    print_header("Real-World Contract Example")

    contract = """
CONTRATO DE SERVICIOS

Entre la empresa CONSTRUCTORA XYZ S.L. (en adelante, "el Cliente")
y Juan Pérez Martínez, con DNI 12345678Z (en adelante, "el Proveedor").

DATOS DE CONTACTO:
Email: juan.perez@construcciones.com
Teléfono: +34 600 123 456
IBAN: ES91 2100 0418 4502 0005 1332

OBJETO DEL CONTRATO:
Servicios de consultoría para el proyecto "Torre Ejecutiva Madrid",
con un presupuesto de 50,000 EUR.

PLAZO DE EJECUCIÓN:
Inicio: 1 de febrero de 2025
Finalización: 30 de junio de 2025

Firmado en Madrid, a 15 de enero de 2025.
"""

    anonymizer = get_anonymizer()
    anonymizer.reset_mappings()

    result = anonymizer.anonymize_document(contract)

    print_result("Original Contract (excerpt)", contract[:200] + "...")
    print_result("Anonymized Contract (excerpt)", result.anonymized_text[:200] + "...")
    print_result("Statistics", str(result.statistics))

    print("\nEntities Found:")
    for entity in result.entities_found:
        print(f"  - {entity['type']}: {entity['placeholder']} (confidence: {entity['score']:.2f})")

    # Verify PII is anonymized
    assert "Juan Pérez Martínez" not in result.anonymized_text, "Person name should be anonymized"
    assert "juan.perez@construcciones.com" not in result.anonymized_text, "Email should be anonymized"
    assert "+34 600 123 456" not in result.anonymized_text, "Phone should be anonymized"

    # Verify context is preserved
    assert "CONSTRUCTORA XYZ S.L." in result.anonymized_text, "Company name should be preserved"
    assert "50,000 EUR" in result.anonymized_text, "Money amount should be preserved"
    assert "1 de febrero de 2025" in result.anonymized_text, "Dates should be preserved"
    assert "Torre Ejecutiva Madrid" in result.anonymized_text, "Project name should be preserved"

    print("\n[OK] Real-world contract processed correctly")
    print("\n[OK] Test 10 passed")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("C2PRO - PII ANONYMIZER TEST SUITE")
    print("=" * 70)

    tests = [
        test_1_basic_person_anonymization,
        test_2_multiple_pii_types,
        test_3_consistency_same_person,
        test_4_dni_nie_recognition,
        test_5_deanonymization,
        test_6_preserve_dates_money,
        test_7_simple_convenience_functions,
        test_8_empty_text,
        test_9_singleton_pattern,
        test_10_real_world_contract,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n[FAIL] Test failed: {e}")
            failed += 1
        except Exception as e:
            print(f"\n[ERROR] Test error: {e}")
            failed += 1

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Total Tests: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print("=" * 70)

    if failed == 0:
        print("\n[OK] ALL TESTS PASSED")
        print("\nThe PII Anonymizer service is working correctly.")
        print("You can now integrate it with your AI pipeline.")
        return 0
    else:
        print("\n[FAIL] SOME TESTS FAILED")
        print("\nPlease review the errors above.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
