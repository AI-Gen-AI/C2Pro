# PII Anonymizer Service - Usage Guide

**Version**: 1.0.0
**Date**: 2026-01-13
**Status**: Production-Ready

---

## Overview

The PII Anonymizer Service provides GDPR-compliant anonymization of personally identifiable information (PII) in documents before sending them to AI services like Anthropic Claude.

### Key Features

- **Microsoft Presidio**: Industry-standard PII detection
- **Spanish NLP**: Optimized for Spanish contracts using Spacy
- **Custom Recognizers**: DNI/NIE detection for Spain
- **Consistent Mapping**: Same entity → same placeholder (e.g., "Juan Pérez" always becomes `<PERSON_1>`)
- **Reversible**: Original values can be restored in AI responses
- **Performance**: Singleton pattern loads Spacy model only once (~500MB)

### Security Policy

**ANONYMIZED Entities** (Physical Persons Only):
- ✅ `PERSON` - Individual names
- ✅ `EMAIL_ADDRESS` - Email addresses
- ✅ `PHONE_NUMBER` - Phone numbers
- ✅ `IBAN_CODE` - Bank account numbers
- ✅ `DNI_NIE` - Spanish identity documents (custom)

**PRESERVED Entities** (Needed for AI Analysis):
- ⚠️ `DATE_TIME` - Dates and times (critical for contract deadlines)
- ⚠️ `MONEY` - Monetary amounts (critical for budget coherence)
- ⚠️ `ORGANIZATION` - Company names (usually public, needed for context)
- ⚠️ `LOCATION` - Places (cities, countries - usually public)

**Why Preserve Organizations?**
Legal entities (companies) are usually public information and critical for contract context. Only physical persons (individuals) are anonymized for GDPR compliance.

---

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `presidio-analyzer==2.2.354`
- `presidio-anonymizer==2.2.354`
- `spacy==3.7.2`

### 2. Install Spacy Spanish Model

The Spanish language model is large (~500MB) and requires a separate installation:

**Option A: Automated Script**
```bash
python install_spacy_model.py
```

**Option B: Manual Installation**
```bash
# Large model (better accuracy, ~500MB)
python -m spacy download es_core_news_lg

# OR medium model (fallback, ~100MB)
python -m spacy download es_core_news_md
```

### 3. Verify Installation

```python
from services.privacy.anonymizer import get_anonymizer

anonymizer = get_anonymizer()
print("✓ Anonymizer service initialized successfully")
```

---

## Basic Usage

### Example 1: Simple Text Anonymization

```python
from services.privacy.anonymizer import get_anonymizer

# Get singleton instance
anonymizer = get_anonymizer()

# Original text with PII
text = """
Contrato firmado por Juan Pérez (DNI: 12345678A).
Email de contacto: juan.perez@empresa.com
Teléfono: +34 600 123 456
"""

# Anonymize
result = anonymizer.anonymize_document(text)

print("Anonymized Text:")
print(result.anonymized_text)
# Output:
# Contrato firmado por <PERSON_1> (DNI: <DNI_NIE_1>).
# Email de contacto: <EMAIL_ADDRESS_1>
# Teléfono: <PHONE_NUMBER_1>

print("\nMapping:")
print(result.mapping)
# Output:
# {
#     "<PERSON_1>": "Juan Pérez",
#     "<DNI_NIE_1>": "12345678A",
#     "<EMAIL_ADDRESS_1>": "juan.perez@empresa.com",
#     "<PHONE_NUMBER_1>": "+34 600 123 456"
# }

print("\nStatistics:")
print(result.statistics)
# Output:
# {
#     "PERSON": 1,
#     "DNI_NIE": 1,
#     "EMAIL_ADDRESS": 1,
#     "PHONE_NUMBER": 1
# }
```

### Example 2: Consistent Mapping (Same Person Multiple Times)

```python
text = """
Juan Pérez es el gerente del proyecto.
Contactar a Juan Pérez en caso de emergencia.
Juan Pérez aprobó el presupuesto.
"""

result = anonymizer.anonymize_document(text)

print(result.anonymized_text)
# Output:
# <PERSON_1> es el gerente del proyecto.
# Contactar a <PERSON_1> en caso de emergencia.
# <PERSON_1> aprobó el presupuesto.

# Note: "Juan Pérez" appears 3 times, but always becomes <PERSON_1>
```

### Example 3: Deanonymization (Restore Original Values)

```python
# AI responds with placeholders
ai_response = "El responsable del contrato es <PERSON_1>. Contactar en <EMAIL_ADDRESS_1>."

# Restore original values
original_response = anonymizer.deanonymize_response(ai_response, result.mapping)

print(original_response)
# Output:
# "El responsable del contrato es Juan Pérez. Contactar en juan.perez@empresa.com."
```

---

## Integration with AI Services

### Complete Pipeline Example

```python
from services.privacy.anonymizer import get_anonymizer
from modules.ai.service import AIService

async def process_contract_safely(contract_text: str):
    """
    Process contract with PII anonymization.

    Args:
        contract_text: Original contract with PII

    Returns:
        AI analysis with real names restored
    """
    # Step 1: Anonymize PII
    anonymizer = get_anonymizer()
    anonymized = anonymizer.anonymize_document(contract_text)

    print(f"Found {len(anonymized.entities_found)} PII entities")

    # Step 2: Send anonymized text to AI (safe)
    ai_service = AIService()
    ai_response = await ai_service.analyze_contract(
        text=anonymized.anonymized_text,
        task_type="contract_analysis"
    )

    # Step 3: Restore real names in AI response
    clean_response = anonymizer.deanonymize_response(
        text=ai_response.content,
        mapping=anonymized.mapping
    )

    # Step 4: Reset mappings for next document
    anonymizer.reset_mappings()

    return {
        "analysis": clean_response,
        "pii_detected": anonymized.statistics,
        "entities": anonymized.entities_found
    }
```

### Integration with AnthropicWrapper

```python
from services.privacy.anonymizer import get_anonymizer
from modules.ai.anthropic_wrapper import AnthropicWrapper

class SecureAIService:
    """AI service with automatic PII anonymization."""

    def __init__(self):
        self.anonymizer = get_anonymizer()
        self.anthropic = AnthropicWrapper()

    async def analyze_document(self, text: str, task: str):
        """
        Analyze document with automatic PII protection.

        Args:
            text: Document text (may contain PII)
            task: Analysis task type

        Returns:
            Analysis result with original names restored
        """
        # Anonymize before sending to AI
        anonymized = self.anonymizer.anonymize_document(text)

        # Send to Claude (safe)
        response = await self.anthropic.complete(
            prompt=f"Analyze this document: {anonymized.anonymized_text}",
            task_type=task
        )

        # Restore real names
        clean_response = self.anonymizer.deanonymize_response(
            text=response,
            mapping=anonymized.mapping
        )

        return {
            "analysis": clean_response,
            "privacy_protected": True,
            "pii_anonymized": anonymized.statistics
        }
```

---

## Advanced Features

### Custom Score Threshold

```python
# Only anonymize entities with high confidence (>= 0.8)
result = anonymizer.anonymize_document(
    text=contract_text,
    score_threshold=0.8  # Default: 0.5
)
```

### Multi-Language Support

```python
# English document
result = anonymizer.anonymize_document(
    text=english_contract,
    language="en"
)

# Spanish document (default)
result = anonymizer.anonymize_document(
    text=spanish_contract,
    language="es"
)
```

### Reset Mappings Between Documents

**CRITICAL**: Reset mappings between independent documents to avoid conflicts.

```python
# Process Document 1
result1 = anonymizer.anonymize_document(document1)
# ... process ...

# Reset before Document 2
anonymizer.reset_mappings()

# Process Document 2
result2 = anonymizer.anonymize_document(document2)
```

**Why?** Without reset, "Juan Pérez" in Document 2 would be mapped to the same placeholder as "Juan Pérez" in Document 1, even if they're different people.

### Inspect Entity Metadata

```python
result = anonymizer.anonymize_document(text)

for entity in result.entities_found:
    print(f"Type: {entity['type']}")
    print(f"Original: {entity['original_value']}")
    print(f"Placeholder: {entity['placeholder']}")
    print(f"Confidence: {entity['score']:.2f}")
    print(f"Position: {entity['start']}-{entity['end']}")
    print("---")
```

---

## Custom Recognizers

### Spanish DNI/NIE Recognizer

The service includes a custom recognizer for Spanish identity documents:

**DNI Format**: 8 digits + letter (e.g., `12345678A`)
**NIE Format**: X/Y/Z + 7 digits + letter (e.g., `X1234567A`)

The recognizer validates the checksum using the modulo 23 algorithm.

**Supported Patterns**:
- `12345678A` (standard)
- `12.345.678-A` (with separators)
- `X1234567A` (NIE)

**Context Detection**: Recognizer looks for keywords like "DNI", "NIE", "identificación" to improve accuracy.

### Adding Custom Recognizers

```python
from presidio_analyzer import PatternRecognizer, Pattern

# Example: Spanish Social Security Number (NSS)
nss_recognizer = PatternRecognizer(
    supported_entity="NSS",
    patterns=[
        Pattern(
            name="nss_pattern",
            regex=r"\b\d{2}/\d{10}/\d{2}\b",
            score=0.85
        )
    ],
    context=["seguridad social", "NSS", "afiliación"],
    supported_language="es"
)

# Add to analyzer
anonymizer = get_anonymizer()
anonymizer._analyzer.registry.add_recognizer(nss_recognizer)
```

---

## Performance Optimization

### Singleton Pattern

The service uses a singleton pattern to load the Spacy model **only once**.

**Why?**
- Spacy model: ~500MB
- Loading time: ~5 seconds
- Memory: ~1GB RAM

Loading on every request would:
- ❌ Consume too much memory
- ❌ Slow down API responses
- ❌ Potentially crash the server

**Solution**: Singleton loads the model once at application startup.

```python
# GOOD: Singleton (loads once)
anonymizer = get_anonymizer()

# BAD: Don't do this (would load model multiple times)
anonymizer = PiiAnonymizerService()  # Don't instantiate directly
```

### Batch Processing

For multiple documents:

```python
documents = [doc1, doc2, doc3, ...]

for doc in documents:
    result = anonymizer.anonymize_document(doc)
    # ... process ...
    anonymizer.reset_mappings()  # Reset between documents
```

---

## Error Handling

### Missing Spacy Model

**Error**:
```
RuntimeError: Failed to load Spacy model for Spanish.
Install with: python -m spacy download es_core_news_lg
```

**Solution**:
```bash
python install_spacy_model.py
```

### Empty Text

```python
result = anonymizer.anonymize_document("")

# Returns empty result (no error)
assert result.anonymized_text == ""
assert result.mapping == {}
```

### No Entities Found

```python
text = "El proyecto inicia el 1 de enero de 2025."  # No PII

result = anonymizer.anonymize_document(text)

assert result.anonymized_text == text  # Unchanged
assert len(result.mapping) == 0  # No mappings
assert result.statistics == {}  # No entities
```

---

## Testing

### Unit Test Example

```python
import pytest
from services.privacy.anonymizer import get_anonymizer

def test_person_anonymization():
    anonymizer = get_anonymizer()
    anonymizer.reset_mappings()

    text = "Juan Pérez trabaja aquí"
    result = anonymizer.anonymize_document(text)

    # Check anonymization
    assert "Juan Pérez" not in result.anonymized_text
    assert "<PERSON_1>" in result.anonymized_text

    # Check mapping
    assert result.mapping["<PERSON_1>"] == "Juan Pérez"

    # Check statistics
    assert result.statistics["PERSON"] == 1

def test_consistency():
    anonymizer = get_anonymizer()
    anonymizer.reset_mappings()

    text = "Juan Pérez y Juan Pérez"
    result = anonymizer.anonymize_document(text)

    # Same person -> same placeholder
    assert result.anonymized_text == "<PERSON_1> y <PERSON_1>"

def test_deanonymization():
    anonymizer = get_anonymizer()

    mapping = {"<PERSON_1>": "Juan Pérez"}
    text = "Contactar a <PERSON_1>"

    result = anonymizer.deanonymize_response(text, mapping)

    assert result == "Contactar a Juan Pérez"
```

---

## Security Best Practices

### 1. Always Anonymize Before External API Calls

```python
# GOOD: Anonymize before sending to external API
anonymized = anonymizer.anonymize_document(text)
response = await external_api.call(anonymized.anonymized_text)

# BAD: Sending raw PII to external API
response = await external_api.call(text)  # ❌ GDPR violation
```

### 2. Store Mappings Securely

```python
# If storing mappings in database, encrypt them
encrypted_mapping = encrypt(json.dumps(result.mapping))
await db.store(encrypted_mapping)
```

### 3. Reset Mappings Regularly

```python
# After each independent document
anonymizer.reset_mappings()

# Or at API request boundaries
@app.post("/analyze")
async def analyze_endpoint(request: Request):
    anonymizer = get_anonymizer()
    anonymizer.reset_mappings()  # Start fresh
    # ... process ...
```

### 4. Log Anonymization Statistics (Not Values)

```python
# GOOD: Log statistics
logger.info(f"Anonymized {result.statistics}")

# BAD: Log actual PII values
logger.info(f"Found person: {original_name}")  # ❌ Don't log PII
```

---

## Troubleshooting

### Issue: Model Loading Slow

**Problem**: First request takes 5+ seconds.

**Solution**: Initialize anonymizer at application startup:

```python
# In main.py or app startup
from services.privacy.anonymizer import get_anonymizer

@app.on_event("startup")
async def startup_event():
    logger.info("Initializing PII Anonymizer...")
    anonymizer = get_anonymizer()  # Load model once
    logger.info("✓ Anonymizer ready")
```

### Issue: High Memory Usage

**Problem**: Server uses 2GB+ RAM.

**Solution**: This is normal. Spacy model requires ~1GB RAM. Consider:
- Using smaller model (`es_core_news_md` instead of `lg`)
- Increasing server RAM
- Using a separate microservice for anonymization

### Issue: Organizations Being Anonymized

**Problem**: Company names are being anonymized as `PERSON`.

**Solution**: Spacy may misclassify organizations. Update entity filter:

```python
# In analyzer configuration
ENTITIES_TO_PRESERVE = [
    "ORGANIZATION",  # Keep organizations
    ...
]
```

---

## References

- **Presidio Docs**: https://microsoft.github.io/presidio/
- **Spacy Spanish Models**: https://spacy.io/models/es
- **GDPR Guidelines**: https://gdpr.eu/

---

**Author**: C2Pro Development Team
**Sprint**: S1.5
**Story Points**: 5 SP
**Version**: 1.0.0
**Last Updated**: 2026-01-13
