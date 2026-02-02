"""Base processor abstract class."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, BinaryIO

from pydantic import BaseModel, Field

from datashield.core.result import Provenance, ValidationResult, ValidationStatus, create_result


class ProcessorConfig(BaseModel):
    """Base configuration for all processors."""

    enabled: bool = Field(True, description="Whether this processor is enabled")
    extract_metadata: bool = Field(True, description="Extract file/data metadata")
    compute_checksum: bool = Field(True, description="Compute SHA-256 checksum of input")
    max_size_bytes: int | None = Field(None, description="Maximum input size in bytes")

    model_config = {"extra": "allow"}


class ProcessedData(BaseModel):
    """Container for processed data with metadata."""

    content: Any = Field(..., description="The extracted/processed content")
    content_type: str = Field(..., description="Type of content (text, records, structured)")
    source_type: str = Field(..., description="Original source type (pdf, csv, json)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extracted metadata")
    page_count: int | None = Field(None, description="Number of pages (for documents)")
    record_count: int | None = Field(None, description="Number of records (for tabular data)")
    raw_size_bytes: int | None = Field(None, description="Size of raw input")

    model_config = {"arbitrary_types_allowed": True}


class BaseProcessor(ABC):
    """Abstract base class for all DataShield processors.

    Processors are responsible for extracting content and metadata from
    various file formats (PDF, CSV, JSON, etc.) and preparing them for
    validation.

    Example:
        >>> class MyProcessor(BaseProcessor):
        ...     name = "my_processor"
        ...     supported_extensions = [".xyz"]
        ...
        ...     def process(self, source, result):
        ...         content = self._extract(source)
        ...         result.data = ProcessedData(
        ...             content=content,
        ...             content_type="text",
        ...             source_type="xyz",
        ...         )
        ...         return result
    """

    name: str = "base_processor"
    supported_extensions: list[str] = []
    supported_mime_types: list[str] = []

    def __init__(self, config: ProcessorConfig | dict[str, Any] | None = None):
        """Initialize the processor with optional configuration.

        Args:
            config: Processor configuration, either as ProcessorConfig or dict.
        """
        if config is None:
            self.config = ProcessorConfig()
        elif isinstance(config, dict):
            self.config = ProcessorConfig(**config)
        else:
            self.config = config

    @abstractmethod
    def process(
        self, source: str | Path | BinaryIO | bytes, result: ValidationResult | None = None
    ) -> ValidationResult:
        """Process the source and extract content.

        This is the main method that subclasses must implement. It should:
        1. Read/parse the source data
        2. Extract content and metadata
        3. Create a ProcessedData object and set it as result.data
        4. Return the ValidationResult

        Args:
            source: The data source (file path, file object, or bytes)
            result: Optional existing ValidationResult to update

        Returns:
            ValidationResult with ProcessedData in result.data
        """
        pass

    def supports(self, source: str | Path) -> bool:
        """Check if this processor supports the given source.

        Args:
            source: File path to check

        Returns:
            True if this processor can handle the source
        """
        path = Path(source) if isinstance(source, str) else source
        return path.suffix.lower() in self.supported_extensions

    def _create_result(
        self, source: str | Path | BinaryIO | bytes
    ) -> tuple[ValidationResult, Provenance]:
        """Create a new result with provenance information.

        Args:
            source: The data source

        Returns:
            Tuple of (ValidationResult, Provenance)
        """
        source_path: str | None = None
        source_type = "bytes"
        source_id = ""

        if isinstance(source, (str, Path)):
            path = Path(source)
            source_path = str(path.absolute())
            source_type = "file"
            source_id = path.name
        elif hasattr(source, "name"):
            source_path = getattr(source, "name", None)
            source_type = "stream"
            source_id = Path(source_path).name if source_path else "stream"
        else:
            source_id = "bytes"

        provenance = Provenance(
            source_id=source_id,
            source_type=source_type,
            source_path=source_path,
            processor_chain=[self.name],
        )

        result = create_result(
            status=ValidationStatus.PASSED,
            provenance=provenance,
        )

        return result, provenance

    def _compute_checksum(self, data: bytes) -> str:
        """Compute SHA-256 checksum of data.

        Args:
            data: Raw bytes to hash

        Returns:
            Hex-encoded SHA-256 hash
        """
        return hashlib.sha256(data).hexdigest()

    def _read_source(self, source: str | Path | BinaryIO | bytes) -> bytes:
        """Read raw bytes from the source.

        Args:
            source: The data source

        Returns:
            Raw bytes from the source
        """
        if isinstance(source, bytes):
            return source
        elif isinstance(source, (str, Path)):
            return Path(source).read_bytes()
        else:
            # File-like object
            return source.read()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, extensions={self.supported_extensions})"
