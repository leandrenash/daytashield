# Changelog

All notable changes to DaytaShield will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2024-01-21

### Added
- Initial release of DaytaShield
- Core validation pipeline with chained validators
- **Validators**:
  - `SchemaValidator` - JSON Schema and Pydantic model validation
  - `SemanticValidator` - LLM-based content validation via LiteLLM
  - `FreshnessValidator` - Timestamp and staleness checks
  - `ComplianceValidator` - Regulatory compliance checking
- **Processors**:
  - `PDFProcessor` - PDF text extraction with pdfplumber
  - `CSVProcessor` - CSV/TSV parsing with pandas
  - `JSONProcessor` - JSON/JSONL parsing with orjson
- **Compliance Rules**:
  - `PIIDetector` - PII pattern detection (SSN, credit cards, email, phone, IP)
  - `HIPAARules` - HIPAA PHI detection (MRN, diagnosis codes, NPI)
  - `GDPRRules` - GDPR compliance (consent, special categories, data minimization)
- **Integrations**:
  - `ValidatedRetriever` - LangChain retriever with validation
  - `ValidatedDocumentLoader` - LangChain loader with validation
- **Core Features**:
  - `DataRouter` - Route data based on validation results (pass/review/quarantine)
  - `AuditTrail` - Immutable JSON Lines audit logging
  - `ValidationResult` - Comprehensive result with messages, provenance, metadata
- **CLI**:
  - `daytashield validate` - Validate files against schema and rules
  - `daytashield watch` - Watch directory for new files
  - `daytashield audit` - Query audit trail
  - `daytashield info` - Show configuration and status
- Docker support with multi-stage build
- GitHub Actions CI/CD pipeline
- Comprehensive documentation and examples

[Unreleased]: https://github.com/daytashield/daytashield/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/daytashield/daytashield/releases/tag/v0.1.0
