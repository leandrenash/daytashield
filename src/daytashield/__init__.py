"""DaytaShield: The missing validation layer between unstructured data and AI systems.

DaytaShield validates multimodal data before it reaches RAG/agents/analytics:
- Validates: Schema, semantic (LLM-based), freshness, compliance (HIPAA, GDPR)
- Cleans: Fixes OCR errors, missing fields, stale data automatically
- Routes: Pass → Destination | Warning → Review | Fail → Quarantine
- Tracks: Immutable audit trail (provenance tracking)
- Integrates: LangChain, RAGFlow, Unstructured.io, Anthropic MCP

Example:
    >>> from daytashield import ValidationPipeline, SchemaValidator, FreshnessValidator
    >>> pipeline = ValidationPipeline([
    ...     SchemaValidator(schema={"type": "object", "required": ["id", "content"]}),
    ...     FreshnessValidator(max_age="7d"),
    ... ])
    >>> result = pipeline.validate({"id": 1, "content": "Hello", "timestamp": "2024-01-01"})
    >>> print(result.status)
    ValidationStatus.PASSED
"""

from daytashield.core.audit import AuditTrail
from daytashield.core.pipeline import ValidationPipeline
from daytashield.core.result import ValidationResult, ValidationStatus
from daytashield.core.router import DataRouter, RouteAction
from daytashield.processors.base import BaseProcessor
from daytashield.processors.csv import CSVProcessor
from daytashield.processors.json import JSONProcessor
from daytashield.processors.pdf import PDFProcessor
from daytashield.validators.base import BaseValidator
from daytashield.validators.compliance import ComplianceValidator
from daytashield.validators.freshness import FreshnessValidator
from daytashield.validators.schema import SchemaValidator
from daytashield.validators.semantic import SemanticValidator

__version__ = "0.1.1"
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
