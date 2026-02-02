# API Reference

Complete API documentation for DaytaShield.

## Core Module

### ValidationPipeline

```python
class ValidationPipeline:
    """Orchestrates validation across multiple validators."""
    
    def __init__(
        self,
        validators: list[BaseValidator] | None = None,
        processors: dict[str, BaseProcessor] | None = None,
        config: PipelineConfig | dict | None = None,
    ) -> None: ...
    
    def add_validator(self, validator: BaseValidator) -> ValidationPipeline: ...
    def add_processor(self, extension: str, processor: BaseProcessor) -> ValidationPipeline: ...
    def validate(self, data: Any, source: str | Path | None = None) -> ValidationResult: ...
    def validate_file(self, path: str | Path) -> ValidationResult: ...
```

### ValidationResult

```python
class ValidationResult(BaseModel):
    """Complete result of a validation operation."""
    
    id: UUID                          # Unique identifier
    status: ValidationStatus          # PASSED, WARNING, FAILED, ERROR, SKIPPED
    messages: list[ValidationMessage] # All validation messages
    data: Any                         # Validated/transformed data
    original_data: Any               # Original input
    provenance: Provenance | None    # Data source info
    validators_run: list[str]        # Names of validators executed
    started_at: datetime
    completed_at: datetime | None
    duration_ms: float | None
    metadata: dict[str, Any]
    
    @property
    def passed(self) -> bool: ...    # True if PASSED or WARNING
    @property
    def failed(self) -> bool: ...    # True if FAILED or ERROR
    @property
    def errors(self) -> list[ValidationMessage]: ...
    @property
    def warnings(self) -> list[ValidationMessage]: ...
    
    def add_message(...) -> None: ...
    def merge(other: ValidationResult) -> ValidationResult: ...
    def to_dict() -> dict[str, Any]: ...
```

### ValidationStatus

```python
class ValidationStatus(str, Enum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
```

### DataRouter

```python
class DataRouter:
    """Routes data based on validation results."""
    
    def __init__(
        self,
        routes: list[Route] | None = None,
        config: RouterConfig | dict | None = None,
    ) -> None: ...
    
    def add_route(self, route: Route) -> DataRouter: ...
    def route(self, result: ValidationResult) -> RoutingDecision: ...
    def route_batch(self, results: list[ValidationResult]) -> dict[RouteAction, list[RoutingDecision]]: ...
```

### RouteAction

```python
class RouteAction(str, Enum):
    PASS = "pass"           # Send to destination
    REVIEW = "review"       # Send to review queue
    QUARANTINE = "quarantine"  # Isolate failed data
    RETRY = "retry"         # Attempt reprocessing
    DROP = "drop"           # Discard the data
```

### AuditTrail

```python
class AuditTrail:
    """Immutable audit trail using JSON Lines format."""
    
    def __init__(self, config: AuditTrailConfig | dict | Path | str | None = None) -> None: ...
    
    def log(self, result: ValidationResult, metadata: dict | None = None) -> AuditEntry: ...
    def log_batch(self, results: list[ValidationResult]) -> list[AuditEntry]: ...
    def flush(self) -> int: ...
    def query(
        self,
        status: ValidationStatus | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        source_id: str | None = None,
        limit: int | None = None,
    ) -> Iterator[AuditEntry]: ...
    def stats(self) -> dict[str, Any]: ...
```

## Validators

### SchemaValidator

```python
class SchemaValidator(BaseValidator):
    """Validates data against JSON Schema or Pydantic models."""
    
    name = "schema"
    
    def __init__(
        self,
        schema: dict[str, Any] | None = None,
        model: Type[BaseModel] | None = None,
        config: SchemaValidatorConfig | dict | None = None,
    ) -> None: ...
    
    def validate(self, data: Any, result: ValidationResult) -> ValidationResult: ...
```

### SemanticValidator

```python
class SemanticValidator(BaseValidator):
    """Validates data semantically using LLMs."""
    
    name = "semantic"
    
    def __init__(
        self,
        prompt: str,
        criteria: list[str] | None = None,
        config: SemanticValidatorConfig | dict | None = None,
    ) -> None: ...
    
    def validate(self, data: Any, result: ValidationResult) -> ValidationResult: ...
    def clear_cache(self) -> None: ...
```

### FreshnessValidator

```python
class FreshnessValidator(BaseValidator):
    """Validates data freshness based on timestamps."""
    
    name = "freshness"
    
    def __init__(
        self,
        max_age: str | timedelta,
        timestamp_field: str | None = None,
        config: FreshnessValidatorConfig | dict | None = None,
    ) -> None: ...
    
    def validate(self, data: Any, result: ValidationResult) -> ValidationResult: ...
```

### ComplianceValidator

```python
class ComplianceValidator(BaseValidator):
    """Validates data against compliance rules."""
    
    name = "compliance"
    
    def __init__(
        self,
        rules: list[ComplianceRule] | list[str] | None = None,
        config: ComplianceValidatorConfig | dict | None = None,
    ) -> None: ...
    
    def add_rule(self, rule: ComplianceRule | str) -> ComplianceValidator: ...
    def validate(self, data: Any, result: ValidationResult) -> ValidationResult: ...
```

## Processors

### PDFProcessor

```python
class PDFProcessor(BaseProcessor):
    """Processes PDF documents."""
    
    name = "pdf"
    supported_extensions = [".pdf"]
    
    def __init__(self, config: PDFProcessorConfig | dict | None = None) -> None: ...
    def process(self, source: str | Path | BinaryIO | bytes, result: ValidationResult | None = None) -> ValidationResult: ...
```

### CSVProcessor

```python
class CSVProcessor(BaseProcessor):
    """Processes CSV files."""
    
    name = "csv"
    supported_extensions = [".csv", ".tsv", ".txt"]
    
    def __init__(self, config: CSVProcessorConfig | dict | None = None) -> None: ...
    def process(self, source: str | Path | BinaryIO | bytes, result: ValidationResult | None = None) -> ValidationResult: ...
```

### JSONProcessor

```python
class JSONProcessor(BaseProcessor):
    """Processes JSON files."""
    
    name = "json"
    supported_extensions = [".json", ".jsonl", ".ndjson"]
    
    def __init__(self, config: JSONProcessorConfig | dict | None = None) -> None: ...
    def process(self, source: str | Path | BinaryIO | bytes, result: ValidationResult | None = None) -> ValidationResult: ...
```

## Rules

### PIIDetector

```python
class PIIDetector(ComplianceRule):
    """Detects personally identifiable information."""
    
    name = "pii"
    
    def __init__(
        self,
        patterns: list[str] | None = None,
        severity_overrides: dict[str, str] | None = None,
    ) -> None: ...
    
    def check(self, data: Any, text_content: list[tuple[str, str]]) -> list[ComplianceViolation]: ...
```

### HIPAARules

```python
class HIPAARules(ComplianceRule):
    """HIPAA compliance rules for PHI."""
    
    name = "hipaa"
    
    def __init__(self, strict: bool = True) -> None: ...
    def check(self, data: Any, text_content: list[tuple[str, str]]) -> list[ComplianceViolation]: ...
```

### GDPRRules

```python
class GDPRRules(ComplianceRule):
    """GDPR compliance rules."""
    
    name = "gdpr"
    
    def __init__(
        self,
        check_consent: bool = True,
        check_special_categories: bool = True,
        check_data_minimization: bool = True,
    ) -> None: ...
    
    def check(self, data: Any, text_content: list[tuple[str, str]]) -> list[ComplianceViolation]: ...
```

## Integrations

### ValidatedRetriever

```python
class ValidatedRetriever:
    """LangChain retriever with validation."""
    
    def __init__(
        self,
        base_retriever: BaseRetriever,
        validators: list[BaseValidator] | None = None,
        pipeline: ValidationPipeline | None = None,
        on_fail: Literal["filter", "raise", "warn", "tag"] = "filter",
        validate_metadata: bool = True,
        validate_content: bool = True,
        min_confidence: float = 0.0,
    ) -> None: ...
    
    def invoke(self, input: str, config: dict | None = None) -> list[Document]: ...
    async def ainvoke(self, input: str, config: dict | None = None) -> list[Document]: ...
    
    @property
    def stats(self) -> dict[str, int]: ...
    def reset_stats(self) -> None: ...
```

### ValidatedDocumentLoader

```python
class ValidatedDocumentLoader:
    """LangChain document loader with validation."""
    
    def __init__(
        self,
        base_loader: Any,
        validators: list[BaseValidator] | None = None,
        pipeline: ValidationPipeline | None = None,
        on_fail: Literal["filter", "raise", "warn", "tag"] = "filter",
    ) -> None: ...
    
    def load(self) -> list[Document]: ...
    def lazy_load(self) -> Iterator[Document]: ...
```
