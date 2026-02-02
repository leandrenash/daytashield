# DaytaShield

**The missing validation layer between unstructured data and AI systems.**

DaytaShield validates multimodal data (PDFs, CSVs, JSON, images) before it reaches your RAG pipelines, AI agents, or analytics systems. Stop hallucinations at the source.

## Features

- **Schema Validation** - JSON Schema + Pydantic model validation
- **Semantic Validation** - LLM-powered content validation
- **Freshness Checks** - Detect stale data before it causes problems
- **Compliance Rules** - Built-in HIPAA, GDPR, and PII detection
- **Document Processing** - PDF, CSV, JSON extraction and validation
- **LangChain Integration** - Validated retrievers for RAG pipelines
- **Audit Trail** - Immutable logging for compliance

## Quick Start

```bash
pip install daytashield
```

```python
from daytashield import ValidationPipeline, SchemaValidator, FreshnessValidator

pipeline = ValidationPipeline([
    SchemaValidator(schema={"type": "object", "required": ["id", "content"]}),
    FreshnessValidator(max_age="7d"),
])

result = pipeline.validate({
    "id": 1,
    "content": "Hello world",
    "timestamp": "2024-01-15"
})

print(result.status)  # ValidationStatus.PASSED
```

## Why DaytaShield?

- **80% of enterprise data is unstructured** (PDFs, images, videos, logs, emails)
- **Data quality is the #1 blocker to AI adoption** (30% of AI projects fail due to bad data)
- **Current solutions extract and index, but don't validate**
- **Result**: Hallucinations, compliance violations, wasted compute, customer distrust

DaytaShield is the missing piece: validate **before** your data reaches AI systems.

## Installation

```bash
# Basic installation
pip install daytashield

# With OCR support
pip install daytashield[ocr]

# With all extras
pip install daytashield[all]
```

## Next Steps

- [Getting Started](getting-started.md) - Tutorial and basic usage
- [Validators](validators.md) - Deep dive into validation
- [Processors](processors.md) - Working with different file formats
- [API Reference](api-reference.md) - Complete API documentation
