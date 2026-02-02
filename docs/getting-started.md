# Getting Started with DataShield

DataShield is the missing validation layer between unstructured data and AI systems. This guide will help you get up and running quickly.

## Installation

```bash
pip install datashield
```

For optional features:

```bash
# OCR support for PDFs
pip install datashield[ocr]

# Development tools
pip install datashield[dev]

# Documentation tools
pip install datashield[docs]

# Everything
pip install datashield[all]
```

## Basic Concepts

### Validators

Validators check specific aspects of your data:

- **SchemaValidator**: Validates data structure against JSON Schema or Pydantic models
- **SemanticValidator**: Uses LLMs for content-aware validation
- **FreshnessValidator**: Ensures data isn't stale
- **ComplianceValidator**: Checks for regulatory compliance (HIPAA, GDPR, PII)

### Processors

Processors extract content from files:

- **PDFProcessor**: Extracts text and metadata from PDFs
- **CSVProcessor**: Parses CSV/TSV files into records
- **JSONProcessor**: Handles JSON and JSON Lines files

### Pipeline

The `ValidationPipeline` chains validators together:

```python
from datashield import ValidationPipeline, SchemaValidator, FreshnessValidator

pipeline = ValidationPipeline([
    SchemaValidator(schema=my_schema),
    FreshnessValidator(max_age="7d"),
])

result = pipeline.validate(my_data)
```

### Results

Every validation returns a `ValidationResult`:

```python
result = pipeline.validate(data)

print(result.status)      # ValidationStatus.PASSED/WARNING/FAILED/ERROR
print(result.passed)      # True if passed or warning
print(result.failed)      # True if failed or error
print(result.messages)    # List of validation messages
print(result.errors)      # Only error messages
print(result.warnings)    # Only warning messages
print(result.duration_ms) # Time taken
```

## Quick Examples

### 1. Schema Validation

```python
from datashield import ValidationPipeline, SchemaValidator

schema = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "integer"},
        "name": {"type": "string"},
    }
}

pipeline = ValidationPipeline([SchemaValidator(schema=schema)])

# Valid data
result = pipeline.validate({"id": 1, "name": "Test"})
print(result.passed)  # True

# Invalid data
result = pipeline.validate({"id": "not-an-int"})
print(result.passed)  # False
for error in result.errors:
    print(error.message)
```

### 2. File Validation

```python
from datashield import ValidationPipeline, SchemaValidator, PDFProcessor

pipeline = ValidationPipeline([SchemaValidator(schema=doc_schema)])
pipeline.add_processor(".pdf", PDFProcessor())

result = pipeline.validate_file("document.pdf")
```

### 3. Compliance Checking

```python
from datashield import ValidationPipeline, ComplianceValidator

pipeline = ValidationPipeline([
    ComplianceValidator(rules=["hipaa", "pii"]),
])

result = pipeline.validate(patient_data)
for msg in result.messages:
    print(f"[{msg.severity}] {msg.message}")
```

### 4. Data Routing

```python
from datashield import ValidationPipeline, DataRouter, RouteAction

pipeline = ValidationPipeline([...])
router = DataRouter()

result = pipeline.validate(data)
decision = router.route(result)

if decision.route.action == RouteAction.PASS:
    process_data(result.data)
elif decision.route.action == RouteAction.QUARANTINE:
    review_data(result.data)
```

## CLI Usage

DataShield includes a command-line interface:

```bash
# Validate a file
datashield validate invoice.pdf --schema invoice.json

# Validate with compliance rules
datashield validate ./data/ --rules hipaa --rules pii

# Watch for new files
datashield watch ./incoming/ --rules hipaa

# View audit log
datashield audit ./audit.jsonl --stats
```

## Next Steps

- [Validators Guide](validators.md) - Deep dive into each validator
- [Processors Guide](processors.md) - Working with different file formats
- [API Reference](api-reference.md) - Complete API documentation
- [Examples](https://github.com/datashield/datashield/tree/main/examples) - More example code
