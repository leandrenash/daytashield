"""JSON file processor."""

from __future__ import annotations

from pathlib import Path
from typing import Any, BinaryIO

from pydantic import Field

from datashield.core.result import ValidationResult, ValidationStatus
from datashield.processors.base import BaseProcessor, ProcessedData, ProcessorConfig


class JSONProcessorConfig(ProcessorConfig):
    """Configuration for JSON processing."""

    encoding: str = Field("utf-8", description="File encoding")
    allow_comments: bool = Field(False, description="Allow JSON5-style comments")
    max_depth: int = Field(100, description="Maximum nesting depth")
    flatten: bool = Field(False, description="Flatten nested structures")
    flatten_separator: str = Field(".", description="Separator for flattened keys")


class JSONProcessor(BaseProcessor):
    """Processes JSON files to extract structured data.

    Uses orjson for fast JSON parsing with:
    - Streaming support for large files
    - Schema extraction
    - Nested structure analysis
    - Optional flattening

    Example:
        >>> processor = JSONProcessor()
        >>> result = processor.process("data.json")
        >>> data = result.data.content  # Parsed JSON
        >>> schema = result.data.metadata["schema"]  # Inferred structure
    """

    name = "json"
    supported_extensions = [".json", ".jsonl", ".ndjson"]
    supported_mime_types = ["application/json", "application/x-ndjson"]

    def __init__(self, config: JSONProcessorConfig | dict[str, Any] | None = None):
        """Initialize the JSON processor.

        Args:
            config: Processor configuration
        """
        if config is None:
            super().__init__(JSONProcessorConfig())
        elif isinstance(config, dict):
            super().__init__(JSONProcessorConfig(**config))
        else:
            super().__init__(config)

    def process(
        self, source: str | Path | BinaryIO | bytes, result: ValidationResult | None = None
    ) -> ValidationResult:
        """Process a JSON file and extract content.

        Args:
            source: JSON file path, file object, or bytes
            result: Optional existing ValidationResult

        Returns:
            ValidationResult with ProcessedData containing parsed JSON
        """
        # Create result if not provided
        if result is None:
            result, provenance = self._create_result(source)
        else:
            provenance = result.provenance

        config = self.config
        if not isinstance(config, JSONProcessorConfig):
            config = JSONProcessorConfig()

        try:
            import orjson
        except ImportError:
            # Fall back to standard json
            import json as orjson  # type: ignore[no-redef]

        try:
            # Read raw bytes
            raw_bytes = self._read_source(source)

            # Compute checksum if configured
            if self.config.compute_checksum and provenance:
                provenance.checksum = self._compute_checksum(raw_bytes)

            # Determine if JSONL format
            is_jsonl = False
            if isinstance(source, (str, Path)):
                ext = Path(source).suffix.lower()
                is_jsonl = ext in (".jsonl", ".ndjson")

            # Parse JSON
            if is_jsonl:
                content = self._parse_jsonl(raw_bytes, config.encoding)
                content_type = "records"
                record_count = len(content)
            else:
                content = orjson.loads(raw_bytes)
                content_type = "array" if isinstance(content, list) else "object"
                record_count = len(content) if isinstance(content, list) else None

            # Analyze structure
            structure_info = self._analyze_structure(content, config.max_depth)

            # Optionally flatten
            if config.flatten and isinstance(content, dict):
                content = self._flatten(content, config.flatten_separator)

            # Create processed data
            processed = ProcessedData(
                content=content,
                content_type=content_type,
                source_type="json",
                metadata={
                    "structure": structure_info,
                    "is_jsonl": is_jsonl,
                },
                record_count=record_count,
                raw_size_bytes=len(raw_bytes),
            )

            result.data = processed

            # Add warnings for potential issues
            if structure_info["max_depth"] > 10:
                result.add_message(
                    code="JSON_DEEP_NESTING",
                    message=f"Deep nesting detected: {structure_info['max_depth']} levels",
                    severity=ValidationStatus.WARNING,
                    validator=self.name,
                )
                if result.status == ValidationStatus.PASSED:
                    result.status = ValidationStatus.WARNING

        except orjson.JSONDecodeError as e:  # type: ignore[union-attr]
            result.add_message(
                code="JSON_PARSE_ERROR",
                message=f"Invalid JSON: {e}",
                severity=ValidationStatus.ERROR,
                validator=self.name,
            )
            result.status = ValidationStatus.ERROR

        except Exception as e:
            result.add_message(
                code="JSON_PROCESSING_ERROR",
                message=f"Failed to process JSON: {e}",
                severity=ValidationStatus.ERROR,
                validator=self.name,
                details={"error": str(e)},
            )
            result.status = ValidationStatus.ERROR

        return result

    def _parse_jsonl(self, raw_bytes: bytes, encoding: str) -> list[Any]:
        """Parse JSON Lines format.

        Args:
            raw_bytes: Raw file bytes
            encoding: Text encoding

        Returns:
            List of parsed JSON objects
        """
        try:
            import orjson

            records = []
            for line in raw_bytes.decode(encoding).splitlines():
                line = line.strip()
                if line:  # Skip empty lines
                    records.append(orjson.loads(line))
            return records
        except ImportError:
            import json

            records = []
            for line in raw_bytes.decode(encoding).splitlines():
                line = line.strip()
                if line:
                    records.append(json.loads(line))
            return records

    def _analyze_structure(self, data: Any, max_depth: int) -> dict[str, Any]:
        """Analyze JSON structure.

        Args:
            data: Parsed JSON data
            max_depth: Maximum depth to analyze

        Returns:
            Structure analysis dict
        """
        info: dict[str, Any] = {
            "type": type(data).__name__,
            "max_depth": 0,
            "total_keys": 0,
            "array_lengths": [],
        }

        def analyze(obj: Any, depth: int) -> None:
            if depth > max_depth:
                return

            info["max_depth"] = max(info["max_depth"], depth)

            if isinstance(obj, dict):
                info["total_keys"] += len(obj)
                for value in obj.values():
                    analyze(value, depth + 1)
            elif isinstance(obj, list):
                info["array_lengths"].append(len(obj))
                for item in obj:
                    analyze(item, depth + 1)

        analyze(data, 0)

        # Summarize array lengths
        if info["array_lengths"]:
            info["min_array_length"] = min(info["array_lengths"])
            info["max_array_length"] = max(info["array_lengths"])
            info["array_count"] = len(info["array_lengths"])
        del info["array_lengths"]

        return info

    def _flatten(self, data: dict[str, Any], separator: str) -> dict[str, Any]:
        """Flatten a nested dictionary.

        Args:
            data: Nested dictionary
            separator: Key separator

        Returns:
            Flattened dictionary
        """
        result: dict[str, Any] = {}

        def flatten_recursive(obj: Any, prefix: str) -> None:
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_key = f"{prefix}{separator}{key}" if prefix else key
                    flatten_recursive(value, new_key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    new_key = f"{prefix}[{i}]"
                    flatten_recursive(item, new_key)
            else:
                result[prefix] = obj

        flatten_recursive(data, "")
        return result
