"""DaytaShield Quickstart Example.

This example demonstrates the basic usage of DaytaShield for validating
structured data against schema and compliance rules.
"""

from daytashield import (
    ComplianceValidator,
    FreshnessValidator,
    SchemaValidator,
    ValidationPipeline,
)

# Sample invoice data
invoice_data = {
    "invoice_id": "INV-2024-001",
    "customer": {
        "name": "Acme Corp",
        "email": "billing@acme.com",
        "address": "123 Main St, New York, NY 10001",
    },
    "items": [
        {"description": "Widget A", "quantity": 10, "unit_price": 29.99},
        {"description": "Widget B", "quantity": 5, "unit_price": 49.99},
    ],
    "total": 549.85,
    "timestamp": "2024-01-15T10:30:00Z",
}

# Define a JSON Schema for invoices
invoice_schema = {
    "type": "object",
    "required": ["invoice_id", "customer", "items", "total"],
    "properties": {
        "invoice_id": {"type": "string", "pattern": "^INV-\\d{4}-\\d{3}$"},
        "customer": {
            "type": "object",
            "required": ["name", "email"],
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string", "format": "email"},
                "address": {"type": "string"},
            },
        },
        "items": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["description", "quantity", "unit_price"],
                "properties": {
                    "description": {"type": "string"},
                    "quantity": {"type": "integer", "minimum": 1},
                    "unit_price": {"type": "number", "minimum": 0},
                },
            },
        },
        "total": {"type": "number", "minimum": 0},
        "timestamp": {"type": "string"},
    },
}


def main() -> None:
    """Run the quickstart example."""
    print("=" * 60)
    print("DaytaShield Quickstart Example")
    print("=" * 60)

    # Example 1: Basic Schema Validation
    print("\n1. Schema Validation")
    print("-" * 40)

    schema_validator = SchemaValidator(schema=invoice_schema)
    pipeline = ValidationPipeline([schema_validator])

    result = pipeline.validate(invoice_data)
    print(f"Status: {result.status.value}")
    print(f"Passed: {result.passed}")
    print(f"Duration: {result.duration_ms:.2f}ms")

    # Example 2: Freshness Validation
    print("\n2. Freshness Validation")
    print("-" * 40)

    pipeline_with_freshness = ValidationPipeline([
        SchemaValidator(schema=invoice_schema),
        FreshnessValidator(max_age="30d"),  # Data must be less than 30 days old
    ])

    result = pipeline_with_freshness.validate(invoice_data)
    print(f"Status: {result.status.value}")
    if result.messages:
        for msg in result.messages:
            print(f"  {msg}")

    # Example 3: Compliance Checking (PII Detection)
    print("\n3. Compliance Validation (PII Detection)")
    print("-" * 40)

    # Data with potential PII
    data_with_pii = {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "555-123-4567",
        "ssn": "123-45-6789",  # This should trigger a warning
        "notes": "Customer called from IP 192.168.1.100",
    }

    compliance_pipeline = ValidationPipeline([
        ComplianceValidator(rules=["pii"]),
    ])

    result = compliance_pipeline.validate(data_with_pii)
    print(f"Status: {result.status.value}")
    print(f"Violations found: {len(result.messages)}")
    for msg in result.messages:
        print(f"  [{msg.severity.value}] {msg.code}: {msg.message}")

    # Example 4: Combined Validation Pipeline
    print("\n4. Combined Validation Pipeline")
    print("-" * 40)

    full_pipeline = ValidationPipeline([
        SchemaValidator(schema=invoice_schema),
        FreshnessValidator(max_age="90d"),
        ComplianceValidator(rules=["pii"]),
    ])

    result = full_pipeline.validate(invoice_data)
    print(f"Status: {result.status.value}")
    print(f"Validators run: {result.validators_run}")
    print(f"Total messages: {len(result.messages)}")

    # Example 5: Invalid Data
    print("\n5. Invalid Data Handling")
    print("-" * 40)

    invalid_data = {
        "invoice_id": "BAD-ID",  # Doesn't match pattern
        "customer": {"name": "Test"},  # Missing required 'email'
        "items": [],  # Empty array (minItems: 1)
        "total": -100,  # Negative (minimum: 0)
    }

    result = full_pipeline.validate(invalid_data)
    print(f"Status: {result.status.value}")
    print(f"Errors: {len(result.errors)}")
    for error in result.errors[:5]:  # Show first 5 errors
        print(f"  [{error.field or 'root'}] {error.message}")

    print("\n" + "=" * 60)
    print("Quickstart complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
