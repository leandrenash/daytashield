"""DaytaShield Compliance Checking Example.

This example demonstrates how to use DaytaShield for compliance validation,
including HIPAA, GDPR, and PII detection.
"""

from daytashield import ComplianceValidator, DataRouter, RouteAction, ValidationPipeline
from daytashield.core.audit import AuditTrail
from daytashield.rules import GDPRRules, HIPAARules, PIIDetector


def main() -> None:
    """Run the compliance checking example."""
    print("=" * 60)
    print("DaytaShield Compliance Checking Example")
    print("=" * 60)

    # Example 1: PII Detection
    print("\n1. PII Detection")
    print("-" * 40)

    pii_detector = PIIDetector()

    # Sample data with various PII
    user_data = {
        "name": "John Smith",
        "email": "john.smith@example.com",
        "phone": "(555) 123-4567",
        "ssn": "123-45-6789",
        "credit_card": "4532015112830366",
        "notes": "Customer IP: 192.168.1.100",
    }

    text_content = [
        (key, str(value))
        for key, value in user_data.items()
        if isinstance(value, str)
    ]

    violations = pii_detector.check(user_data, text_content)
    print(f"Found {len(violations)} PII violations:")
    for v in violations:
        print(f"  [{v.severity}] {v.code}")
        print(f"    Field: {v.field}")
        print(f"    Message: {v.message}")
        print(f"    Recommendation: {v.recommendation}")
        print()

    # Example 2: HIPAA Compliance
    print("\n2. HIPAA Compliance")
    print("-" * 40)

    hipaa_rules = HIPAARules(strict=True)

    # Sample healthcare data
    patient_record = {
        "patient_name": "Jane Doe",
        "mrn": "MRN: 12345678",
        "diagnosis": "ICD-10: J06.9 - Acute upper respiratory infection",
        "provider_npi": "NPI: 1234567890",
        "notes": "Patient prescribed medication. Rx: 12345678901",
        "dob": "01/15/1985",
        "ssn": "987-65-4321",
    }

    text_content = [
        (key, str(value))
        for key, value in patient_record.items()
    ]

    violations = hipaa_rules.check(patient_record, text_content)
    print(f"Found {len(violations)} HIPAA violations:")
    for v in violations:
        print(f"  [{v.severity}] {v.code}: {v.message}")

    # Example 3: GDPR Compliance
    print("\n3. GDPR Compliance")
    print("-" * 40)

    gdpr_rules = GDPRRules(
        check_consent=True,
        check_special_categories=True,
        check_data_minimization=True,
    )

    # Sample EU user data
    eu_user_data = {
        "name": "Hans Mueller",
        "email": "hans@example.de",
        "iban": "DE89370400440532013000",
        "political_opinion": "Supports environmental policies",  # Special category
        "health_data": "Diabetic",  # Special category
        # Missing consent field
    }

    text_content = [
        (key, str(value))
        for key, value in eu_user_data.items()
    ]

    violations = gdpr_rules.check(eu_user_data, text_content)
    print(f"Found {len(violations)} GDPR violations:")
    for v in violations:
        print(f"  [{v.severity}] {v.code}")
        print(f"    {v.message}")
        if v.recommendation:
            print(f"    Recommendation: {v.recommendation}")
        print()

    # Example 4: Combined Compliance Pipeline
    print("\n4. Combined Compliance Pipeline")
    print("-" * 40)

    pipeline = ValidationPipeline([
        ComplianceValidator(rules=["hipaa", "gdpr", "pii"]),
    ])

    result = pipeline.validate(patient_record)
    print(f"Status: {result.status.value}")
    print(f"Total violations: {len(result.messages)}")

    # Group by rule
    by_rule: dict[str, list] = {}
    for msg in result.messages:
        rule = msg.details.get("rule", "unknown")
        by_rule.setdefault(rule, []).append(msg)

    for rule, messages in by_rule.items():
        print(f"\n{rule}: {len(messages)} violations")
        for msg in messages[:3]:
            print(f"  - {msg.message}")

    # Example 5: Routing Based on Compliance
    print("\n5. Routing Based on Compliance")
    print("-" * 40)

    router = DataRouter()

    # Test with compliant data
    compliant_data = {
        "product_id": "PROD-001",
        "name": "Widget",
        "price": 29.99,
    }

    result = pipeline.validate(compliant_data)
    decision = router.route(result)
    print(f"Compliant data: {result.status.value} → {decision.route.action.value}")

    # Test with non-compliant data
    result = pipeline.validate(patient_record)
    decision = router.route(result)
    print(f"Non-compliant data: {result.status.value} → {decision.route.action.value}")
    print(f"Reason: {decision.reason}")

    # Example 6: Audit Trail
    print("\n6. Audit Trail")
    print("-" * 40)

    # Create audit trail (in-memory for this example)
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        audit_path = f.name

    try:
        audit = AuditTrail(audit_path)

        # Log some validations
        for i, data in enumerate([compliant_data, patient_record, eu_user_data]):
            result = pipeline.validate(data)
            audit.log(result, metadata={"batch": "example", "index": i})

        audit.flush()

        # Get statistics
        stats = audit.stats()
        print(f"Audit Statistics:")
        print(f"  Total validations: {stats['total']}")
        print(f"  Passed: {stats['by_status']['passed']}")
        print(f"  Failed: {stats['by_status']['failed']}")
        print(f"  Warnings: {stats['by_status']['warning']}")
        print(f"  Avg duration: {stats['avg_duration_ms']:.2f}ms")
    finally:
        os.unlink(audit_path)

    print("\n" + "=" * 60)
    print("Compliance checking example complete!")
    print("=" * 60)
    print("\nKey takeaways:")
    print("- Use PIIDetector for general PII scanning")
    print("- Use HIPAARules for healthcare data")
    print("- Use GDPRRules for EU data protection")
    print("- Combine rules in ComplianceValidator for comprehensive checks")
    print("- Use DataRouter to automate handling of non-compliant data")
    print("- Use AuditTrail for compliance reporting")


if __name__ == "__main__":
    main()
