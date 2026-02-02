"""PDF document processor."""

from __future__ import annotations

from pathlib import Path
from typing import Any, BinaryIO

from pydantic import Field

from daytashield.core.result import ValidationResult, ValidationStatus
from daytashield.processors.base import BaseProcessor, ProcessedData, ProcessorConfig


class PDFProcessorConfig(ProcessorConfig):
    """Configuration for PDF processing."""

    extract_images: bool = Field(False, description="Extract embedded images")
    extract_tables: bool = Field(True, description="Extract tables from PDF")
    ocr_fallback: bool = Field(False, description="Use OCR if text extraction fails")
    max_pages: int | None = Field(None, description="Maximum pages to process")
    password: str | None = Field(None, description="PDF password if encrypted")


class PDFProcessor(BaseProcessor):
    """Processes PDF documents to extract text and metadata.

    Uses pdfplumber for reliable text extraction with layout preservation.
    Supports:
    - Text extraction with layout
    - Metadata extraction (author, title, dates)
    - Table extraction
    - Page-by-page processing
    - Optional OCR fallback

    Example:
        >>> processor = PDFProcessor()
        >>> result = processor.process("invoice.pdf")
        >>> print(result.data.content)  # Extracted text
        >>> print(result.data.metadata)  # PDF metadata
    """

    name = "pdf"
    supported_extensions = [".pdf"]
    supported_mime_types = ["application/pdf"]

    def __init__(self, config: PDFProcessorConfig | dict[str, Any] | None = None):
        """Initialize the PDF processor.

        Args:
            config: Processor configuration
        """
        if config is None:
            super().__init__(PDFProcessorConfig())
        elif isinstance(config, dict):
            super().__init__(PDFProcessorConfig(**config))
        else:
            super().__init__(config)

    def process(
        self, source: str | Path | BinaryIO | bytes, result: ValidationResult | None = None
    ) -> ValidationResult:
        """Process a PDF file and extract content.

        Args:
            source: PDF file path, file object, or bytes
            result: Optional existing ValidationResult

        Returns:
            ValidationResult with ProcessedData containing extracted text
        """
        # Create result if not provided
        if result is None:
            result, provenance = self._create_result(source)
        else:
            provenance = result.provenance

        config = self.config
        if not isinstance(config, PDFProcessorConfig):
            config = PDFProcessorConfig()

        try:
            import pdfplumber
        except ImportError:
            result.add_message(
                code="PDF_NO_PDFPLUMBER",
                message="pdfplumber package not installed. Install with: pip install pdfplumber",
                severity=ValidationStatus.ERROR,
                validator=self.name,
            )
            result.status = ValidationStatus.ERROR
            return result

        try:
            # Read the source
            raw_bytes = self._read_source(source)

            # Compute checksum if configured
            if self.config.compute_checksum and provenance:
                provenance.checksum = self._compute_checksum(raw_bytes)

            # Open PDF
            pdf_file: Any
            if isinstance(source, (str, Path)):
                pdf_file = pdfplumber.open(source, password=config.password)
            else:
                import io
                pdf_file = pdfplumber.open(io.BytesIO(raw_bytes), password=config.password)

            with pdf_file as pdf:
                # Extract metadata
                metadata = self._extract_metadata(pdf)

                # Extract text from pages
                pages_text: list[str] = []
                tables: list[list[list[str]]] = []
                page_count = len(pdf.pages)

                max_pages = config.max_pages or page_count
                for i, page in enumerate(pdf.pages[:max_pages]):
                    # Extract text
                    page_text = page.extract_text() or ""
                    pages_text.append(page_text)

                    # Extract tables if configured
                    if config.extract_tables:
                        page_tables = page.extract_tables() or []
                        tables.extend(page_tables)

                # Combine all text
                full_text = "\n\n".join(pages_text)

                # Check if text extraction worked
                if not full_text.strip() and config.ocr_fallback:
                    full_text = self._ocr_fallback(raw_bytes)
                    metadata["ocr_used"] = True

                # Create processed data
                processed = ProcessedData(
                    content=full_text,
                    content_type="text",
                    source_type="pdf",
                    metadata=metadata,
                    page_count=page_count,
                    raw_size_bytes=len(raw_bytes),
                )

                # Add tables to metadata if extracted
                if tables:
                    processed.metadata["tables"] = tables
                    processed.metadata["table_count"] = len(tables)

                result.data = processed

                # Add info message about extraction
                result.metadata["pdf_pages"] = page_count
                result.metadata["pdf_text_length"] = len(full_text)

        except Exception as e:
            result.add_message(
                code="PDF_PROCESSING_ERROR",
                message=f"Failed to process PDF: {e}",
                severity=ValidationStatus.ERROR,
                validator=self.name,
                details={"error": str(e)},
            )
            result.status = ValidationStatus.ERROR

        return result

    def _extract_metadata(self, pdf: Any) -> dict[str, Any]:
        """Extract metadata from PDF.

        Args:
            pdf: pdfplumber PDF object

        Returns:
            Dict of metadata
        """
        metadata: dict[str, Any] = {}

        if hasattr(pdf, "metadata") and pdf.metadata:
            pdf_meta = pdf.metadata
            # Common PDF metadata fields
            field_mapping = {
                "Title": "title",
                "Author": "author",
                "Subject": "subject",
                "Creator": "creator",
                "Producer": "producer",
                "CreationDate": "created_at",
                "ModDate": "modified_at",
                "Keywords": "keywords",
            }

            for pdf_key, our_key in field_mapping.items():
                if pdf_key in pdf_meta and pdf_meta[pdf_key]:
                    metadata[our_key] = pdf_meta[pdf_key]

        metadata["page_count"] = len(pdf.pages)

        return metadata

    def _ocr_fallback(self, pdf_bytes: bytes) -> str:
        """Attempt OCR on PDF pages.

        Args:
            pdf_bytes: Raw PDF bytes

        Returns:
            Extracted text via OCR
        """
        try:
            import io

            from pdf2image import convert_from_bytes
            import pytesseract

            # Convert PDF to images
            images = convert_from_bytes(pdf_bytes)

            # OCR each page
            texts = []
            for img in images:
                text = pytesseract.image_to_string(img)
                texts.append(text)

            return "\n\n".join(texts)

        except ImportError:
            return "[OCR unavailable - install pytesseract and pdf2image]"
        except Exception:
            return "[OCR failed]"
