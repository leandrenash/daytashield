# Validators Guide

DataShield provides four built-in validators for comprehensive data quality assurance.

## SchemaValidator

Validates data structure against JSON Schema or Pydantic models.

### JSON Schema Validation

```python
from datashield import SchemaValidator

schema = {
    "type": "object",
    "required": ["id", "email"],
    "properties": {
        "id": {"type": "integer", "minimum": 1},
        "email": {"type": "string", "format": "email"},
        "tags": {"type": "array", "items": {"type": "string"}},
    }
}

validator = SchemaValidator(schema=schema)
```

### Pydantic Model Validation

```python
from pydantic import BaseModel, EmailStr
from datashield import SchemaValidator

class User(BaseModel):
    id: int
    email: EmailStr
    tags: list[str] = []

validator = SchemaValidator(model=User)
```

### Configuration

```python
from datashield.validators.schema import SchemaValidator, SchemaValidatorConfig

validator = SchemaValidator(
    schema=schema,
    config=SchemaValidatorConfig(
        strict=True,        # Fail on extra fields
        coerce_types=False, # Don't attempt type coercion
        allow_none=False,   # Don't allow None for optional fields
    )
)
```

## SemanticValidator

Uses LLMs for content-aware validation that goes beyond schema checks.

### Basic Usage

```python
from datashield import SemanticValidator

validator = SemanticValidator(
    prompt="Check if this document is a valid business invoice",
    criteria=["has_invoice_number", "has_date", "has_line_items", "has_total"],
)
```

### Configuration

```python
from datashield.validators.semantic import SemanticValidator, SemanticValidatorConfig

validator = SemanticValidator(
    prompt="Verify this customer support ticket is appropriate",
    config=SemanticValidatorConfig(
        model="gpt-4o-mini",  # or "claude-3-haiku", "ollama/llama2", etc.
        temperature=0.0,      # Deterministic responses
        cache_results=True,   # Cache repeated validations
        timeout=30,           # Request timeout
    )
)
```

### Supported Models

SemanticValidator uses LiteLLM for provider-agnostic model access:

- OpenAI: `gpt-4o`, `gpt-4o-mini`, `gpt-3.5-turbo`
- Anthropic: `claude-3-opus`, `claude-3-sonnet`, `claude-3-haiku`
- Local: `ollama/llama2`, `ollama/mistral`
- Azure: `azure/gpt-4`

## FreshnessValidator

Ensures data isn't stale by checking timestamps.

### Basic Usage

```python
from datashield import FreshnessValidator

# Data must be less than 7 days old
validator = FreshnessValidator(max_age="7d")

# Check specific field
validator = FreshnessValidator(
    max_age="24h",
    timestamp_field="updated_at"
)
```

### Time Formats

Supported duration formats:
- Seconds: `30s`, `30sec`, `30 seconds`
- Minutes: `5m`, `5min`, `5 minutes`
- Hours: `2h`, `2hr`, `2 hours`
- Days: `7d`, `7 days`
- Weeks: `2w`, `2 weeks`
- Months: `1M`, `1 month` (30 days)
- Years: `1y`, `1 year` (365 days)

### Configuration

```python
from datashield.validators.freshness import FreshnessValidator, FreshnessValidatorConfig

validator = FreshnessValidator(
    max_age="7d",
    config=FreshnessValidatorConfig(
        timestamp_fields=["timestamp", "created_at", "date"],
        warn_threshold_ratio=0.8,  # Warn at 80% of max age
    )
)
```

## ComplianceValidator

Checks for regulatory compliance with pluggable rule packs.

### Using Built-in Rules

```python
from datashield import ComplianceValidator

# Single rule
validator = ComplianceValidator(rules=["hipaa"])

# Multiple rules
validator = ComplianceValidator(rules=["hipaa", "gdpr", "pii"])
```

### Available Rule Packs

#### HIPAA Rules
Detects Protected Health Information (PHI):
- Medical record numbers
- Health plan IDs
- Diagnosis codes
- Prescription numbers
- Provider NPIs
- DEA numbers

```python
from datashield.rules import HIPAARules

rules = HIPAARules(strict=True)  # Also check general PII in healthcare context
```

#### GDPR Rules
Checks EU data protection compliance:
- Consent indicators
- Special category data (Article 9)
- Data minimization
- Cross-border indicators

```python
from datashield.rules import GDPRRules

rules = GDPRRules(
    check_consent=True,
    check_special_categories=True,
    check_data_minimization=True,
)
```

#### PII Detector
Scans for personally identifiable information:
- Social Security Numbers
- Credit card numbers
- Email addresses
- Phone numbers
- IP addresses
- Dates of birth
- Passport numbers
- Driver's license numbers

```python
from datashield.rules import PIIDetector

detector = PIIDetector(
    patterns=["ssn", "credit_card", "email"],  # Specific patterns only
    severity_overrides={"email": "warning"},   # Downgrade email to warning
)
```

### Custom Rules

Create custom compliance rules:

```python
from datashield.rules.base import ComplianceRule, ComplianceViolation

class MyCustomRule(ComplianceRule):
    name = "my_rule"
    description = "Check for custom violations"

    def check(self, data, text_content):
        violations = []
        for field, text in text_content:
            if "forbidden_word" in text.lower():
                violations.append(ComplianceViolation(
                    code="CUSTOM_FORBIDDEN",
                    message="Forbidden word detected",
                    severity="error",
                    category="custom",
                    field=field,
                    recommendation="Remove the forbidden word",
                ))
        return violations

# Use in ComplianceValidator
from datashield import ComplianceValidator
validator = ComplianceValidator(rules=[MyCustomRule()])
```

## Combining Validators

Use `ValidationPipeline` to chain validators:

```python
from datashield import (
    ValidationPipeline,
    SchemaValidator,
    SemanticValidator,
    FreshnessValidator,
    ComplianceValidator,
)

pipeline = ValidationPipeline([
    SchemaValidator(schema=my_schema),      # Structure first
    FreshnessValidator(max_age="7d"),       # Then freshness
    ComplianceValidator(rules=["pii"]),     # Then compliance
    SemanticValidator(prompt="..."),        # Semantic last (most expensive)
])

result = pipeline.validate(data)
```

## Validation Order

Validators run in the order they're added to the pipeline. Consider:

1. **Schema first**: Catches structural issues early
2. **Freshness second**: Cheap to check
3. **Compliance third**: Pattern matching
4. **Semantic last**: Most expensive (LLM calls)

Use `fail_fast=True` to stop on first failure:

```python
pipeline = ValidationPipeline(
    validators=[...],
    config={"fail_fast": True}
)
```
