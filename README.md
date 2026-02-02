# 🛡️ DaytaShield

[![PyPI version](https://badge.fury.io/py/daytashield.svg)](https://badge.fury.io/py/daytashield)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**The missing validation layer between unstructured data and AI systems.**

DaytaShield validates multimodal data (PDFs, CSVs, JSON, images) before it reaches your RAG pipelines, AI agents, or analytics systems. Stop hallucinations at the source.

## 🚀 Quick Start

```bash
pip install daytashield
```

```python
from daytashield import ValidationPipeline, SchemaValidator, FreshnessValidator

# Create a validation pipeline
pipeline = ValidationPipeline([
    SchemaValidator(schema={"type": "object", "required": ["id", "content"]}),
    FreshnessValidator(max_age="7d"),
])

# Validate your data
result = pipeline.validate({
    "id": 1,
    "content": "Hello world",
    "timestamp": "2024-01-15"
})

print(result.status)  # ValidationStatus.PASSED
```

## ✨ Features

- **📋 Schema Validation** - JSON Schema + Pydantic model validation
- **🧠 Semantic Validation** - LLM-powered content validation
- **⏰ Freshness Checks** - Detect stale data before it causes problems
- **🔒 Compliance Rules** - Built-in HIPAA, GDPR, and PII detection
- **📄 Document Processing** - PDF, CSV, JSON extraction and validation
- **🔗 LangChain Integration** - Validated retrievers for RAG pipelines
- **📊 Audit Trail** - Immutable logging for compliance

## 📖 Usage

### Validate Files

```python
from daytashield import ValidationPipeline, SchemaValidator, PDFProcessor

# Create pipeline with processors
pipeline = ValidationPipeline([
    SchemaValidator(schema=invoice_schema),
])
pipeline.add_processor(".pdf", PDFProcessor())

# Validate a PDF
result = pipeline.validate_file("invoice.pdf")
if result.failed:
    for error in result.errors:
        print(f"Error: {error.message}")
```

### Compliance Checking

```python
from daytashield import ValidationPipeline, ComplianceValidator

# Check for HIPAA and PII violations
pipeline = ValidationPipeline([
    ComplianceValidator(rules=["hipaa", "pii"]),
])

result = pipeline.validate(patient_data)
for message in result.messages:
    print(f"{message.severity}: {message.message}")
```

### LangChain Integration

```python
from langchain_community.vectorstores import FAISS
from daytashield import SchemaValidator, FreshnessValidator
from daytashield.integrations.langchain import ValidatedRetriever

# Wrap your retriever with validation
retriever = ValidatedRetriever(
    base_retriever=vectorstore.as_retriever(),
    validators=[
        SchemaValidator(schema=doc_schema),
        FreshnessValidator(max_age="7d"),
    ],
    on_fail="filter",  # Remove invalid documents
)

# Use like any LangChain retriever
docs = retriever.invoke("What is the refund policy?")
```

### Routing Based on Validation

```python
from daytashield import ValidationPipeline, DataRouter, RouteAction

pipeline = ValidationPipeline([...])
router = DataRouter()

result = pipeline.validate(data)
decision = router.route(result)

if decision.route.action == RouteAction.PASS:
    send_to_destination(result.data)
elif decision.route.action == RouteAction.QUARANTINE:
    quarantine_for_review(result.data, decision.reason)
```

## 🖥️ CLI

```bash
# Validate files
daytashield validate invoice.pdf --schema invoice.json

# Validate with compliance rules
daytashield validate ./data/ --rules hipaa --rules pii

# Watch directory for new files
daytashield watch ./incoming/ --rules hipaa --audit audit.jsonl

# Query audit log
daytashield audit audit.jsonl --status failed --limit 10
```

## 📦 Validators

| Validator | Description |
|-----------|-------------|
| `SchemaValidator` | JSON Schema and Pydantic validation |
| `SemanticValidator` | LLM-based content validation |
| `FreshnessValidator` | Timestamp and staleness checks |
| `ComplianceValidator` | HIPAA, GDPR, PII rule enforcement |

## 📄 Processors

| Processor | Formats | Description |
|-----------|---------|-------------|
| `PDFProcessor` | `.pdf` | Text extraction with pdfplumber |
| `CSVProcessor` | `.csv`, `.tsv` | Tabular data with pandas |
| `JSONProcessor` | `.json`, `.jsonl` | Structured data with orjson |

## 🔒 Compliance Rules

| Rule Pack | Coverage |
|-----------|----------|
| `hipaa` | PHI detection, medical record numbers, health plan IDs |
| `gdpr` | Consent checking, special category data, data minimization |
| `pii` | SSN, credit cards, emails, phone numbers, IP addresses |

## 📊 Audit Trail

DaytaShield maintains an immutable audit log of all validation operations:

```python
from daytashield import AuditTrail, ValidationPipeline

# Enable audit logging
audit = AuditTrail("./audit.jsonl")
pipeline = ValidationPipeline([...])

result = pipeline.validate(data)
audit.log(result)

# Query the audit trail
for entry in audit.query(status=ValidationStatus.FAILED):
    print(f"Failed: {entry.source_id} at {entry.timestamp}")

# Get statistics
stats = audit.stats()
print(f"Pass rate: {stats['by_status']['passed'] / stats['total'] * 100:.1f}%")
```

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Source    │────▶│  Processor  │────▶│  Validators │
│ PDF/CSV/JSON│     │  Extract    │     │  Schema     │
└─────────────┘     └─────────────┘     │  Semantic   │
                                        │  Freshness  │
                                        │  Compliance │
                                        └──────┬──────┘
                                               │
                    ┌─────────────┐     ┌──────▼──────┐
                    │   Audit     │◀────│   Router    │
                    │   Trail     │     │  Pass/Warn  │
                    └─────────────┘     │  /Fail      │
                                        └─────────────┘
```

## 🔧 Configuration

```python
from daytashield import ValidationPipeline, PipelineConfig

pipeline = ValidationPipeline(
    validators=[...],
    config=PipelineConfig(
        fail_fast=True,          # Stop on first failure
        include_original_data=True,  # Keep original data in result
        auto_detect_processor=True,  # Auto-select processor by extension
    ),
)
```

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Clone the repo
git clone https://github.com/daytashield/daytashield.git
cd daytashield

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check src tests
```

## 📄 License

Apache 2.0 - see [LICENSE](LICENSE) for details.

## 🔗 Links

- [Documentation](https://daytashield.dev/docs)
- [PyPI](https://pypi.org/project/daytashield/)
- [GitHub](https://github.com/daytashield/daytashield)
- [Discord](https://discord.gg/daytashield)

---

**Built with ❤️ for the AI community**

*Stop bad data at the source. Validate before you hallucinate.*
