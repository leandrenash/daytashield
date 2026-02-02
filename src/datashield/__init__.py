"""DataShield: The missing validation layer between unstructured data and AI systems.

DataShield validates multimodal data before it reaches RAG/agents/analytics:
- Validates: Schema, semantic (LLM-based), freshness, compliance (HIPAA, GDPR)
- Cleans: Fixes OCR errors, missing fields, stale data automatically
- Routes: Pass → Destination | Warning → Review | Fail → Quarantine
- Tracks: Immutable audit trail (provenance tracking)
- Integrates: LangChain, RAGFlow, Unstructured.io, Anthropic MCP

Example:
    >>> from datashield import ValidationPipeline, SchemaValidator, FreshnessValidator
    >>> pipeline = ValidationPipeline([
    ...     SchemaValidator(schema={"type": "object", "required": ["id", "content"]}),
    ...     FreshnessValidator(max_age="7d"),
    ... ])
    >>> result = pipeline.validate({"id": 1, "content": "Hello", "timestamp": "2024-01-01"})
    >>> print(result.status)
    ValidationStatus.PASSED
"""

from datashield.core.audit import AuditTrail
from datashield.core.pipeline import ValidationPipeline
from datashield.core.result import ValidationResult, ValidationStatus
from datashield.core.router import DataRouter, RouteAction
from datashield.processors.base import BaseProcessor
from datashield.processors.csv import CSVProcessor
from datashield.processors.json import JSONProcessor
from datashield.processors.pdf import PDFProcessor
from datashield.validators.base import BaseValidator
from datashield.validators.compliance import ComplianceValidator
from datashield.validators.freshness import FreshnessValidator
from datashield.validators.schema import SchemaValidator
from datashield.validators.semantic import SemanticValidator

__version__ = "0.1.0"
__all__ = [
    # Core
    "ValidationPipeline",
    "ValidationResult",
    "ValidationStatus",
    "DataRouter",
    "RouteAction",
    "AuditTrail",
    # Validators
    "BaseValidator",
    "SchemaValidator",
    "SemanticValidator",
    "FreshnessValidator",
    "ComplianceValidator",
    # Processors
    "BaseProcessor",
    "PDFProcessor",
    "CSVProcessor",
    "JSONProcessor",
]
