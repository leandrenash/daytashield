"""LangChain integration for validated retrieval."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Literal

from pydantic import Field

from datashield.core.pipeline import ValidationPipeline
from datashield.core.result import ValidationResult, ValidationStatus, create_result

if TYPE_CHECKING:
    from langchain_core.callbacks import CallbackManagerForRetrieverRun
    from langchain_core.documents import Document
    from langchain_core.retrievers import BaseRetriever

logger = logging.getLogger(__name__)


OnFailAction = Literal["filter", "raise", "warn", "tag"]


class ValidatedRetriever:
    """A LangChain retriever wrapper that validates documents before returning.

    Wraps any LangChain retriever and applies DataShield validation to
    retrieved documents. Invalid documents can be filtered, flagged, or
    cause exceptions based on configuration.

    Example:
        >>> from langchain_community.vectorstores import FAISS
        >>> from datashield import SchemaValidator, FreshnessValidator
        >>> from datashield.integrations.langchain import ValidatedRetriever
        >>>
        >>> # Create base retriever
        >>> vectorstore = FAISS.from_texts(texts, embeddings)
        >>> base_retriever = vectorstore.as_retriever()
        >>>
        >>> # Wrap with validation
        >>> retriever = ValidatedRetriever(
        ...     base_retriever=base_retriever,
        ...     validators=[
        ...         SchemaValidator(schema={"type": "object"}),
        ...         FreshnessValidator(max_age="7d"),
        ...     ],
        ...     on_fail="filter",
        ... )
        >>>
        >>> # Use like any retriever
        >>> docs = retriever.invoke("search query")

    Actions on validation failure:
    - "filter": Remove invalid documents from results
    - "raise": Raise ValidationError for any invalid document
    - "warn": Log warning but include document
    - "tag": Add validation metadata to document
    """

    def __init__(
        self,
        base_retriever: BaseRetriever,
        validators: list[Any] | None = None,
        pipeline: ValidationPipeline | None = None,
        on_fail: OnFailAction = "filter",
        validate_metadata: bool = True,
        validate_content: bool = True,
        min_confidence: float = 0.0,
    ):
        """Initialize the validated retriever.

        Args:
            base_retriever: The underlying LangChain retriever
            validators: List of validators to apply (creates pipeline)
            pipeline: Pre-configured ValidationPipeline (alternative to validators)
            on_fail: Action when validation fails
            validate_metadata: Validate document metadata
            validate_content: Validate document content
            min_confidence: Minimum confidence score to pass (for semantic validation)
        """
        self.base_retriever = base_retriever
        self.on_fail = on_fail
        self.validate_metadata = validate_metadata
        self.validate_content = validate_content
        self.min_confidence = min_confidence

        # Set up validation pipeline
        if pipeline is not None:
            self.pipeline = pipeline
        elif validators:
            self.pipeline = ValidationPipeline(validators=validators)
        else:
            self.pipeline = ValidationPipeline()

        # Statistics
        self._stats = {
            "total_retrieved": 0,
            "total_validated": 0,
            "total_passed": 0,
            "total_filtered": 0,
        }

    def invoke(
        self,
        input: str,  # noqa: A002
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[Document]:
        """Retrieve and validate documents.

        Args:
            input: The search query
            config: Optional config for the retriever
            **kwargs: Additional arguments for base retriever

        Returns:
            List of validated Document objects
        """
        # Retrieve documents from base retriever
        docs = self.base_retriever.invoke(input, config=config, **kwargs)
        self._stats["total_retrieved"] += len(docs)

        # Validate each document
        validated_docs: list[Document] = []

        for doc in docs:
            result = self._validate_document(doc)
            self._stats["total_validated"] += 1

            if result.passed:
                self._stats["total_passed"] += 1
                validated_docs.append(self._tag_document(doc, result))
            else:
                self._handle_failed_validation(doc, result, validated_docs)

        return validated_docs

    def _validate_document(self, doc: Document) -> ValidationResult:
        """Validate a single document.

        Args:
            doc: LangChain Document to validate

        Returns:
            ValidationResult
        """
        # Build data dict from document
        data: dict[str, Any] = {}

        if self.validate_content:
            data["content"] = doc.page_content

        if self.validate_metadata and doc.metadata:
            data["metadata"] = doc.metadata
            # Also add metadata fields at top level for validators
            data.update(doc.metadata)

        # Run validation
        result = self.pipeline.validate(data)

        # Check confidence threshold
        confidence = result.metadata.get("semantic_confidence", 1.0)
        if confidence < self.min_confidence:
            result.add_message(
                code="LOW_CONFIDENCE",
                message=f"Confidence {confidence:.2f} below threshold {self.min_confidence}",
                severity=ValidationStatus.FAILED,
                validator="langchain_retriever",
            )
            result.status = ValidationStatus.FAILED

        return result

    def _handle_failed_validation(
        self,
        doc: Document,
        result: ValidationResult,
        validated_docs: list[Document],
    ) -> None:
        """Handle a document that failed validation.

        Args:
            doc: The failed document
            result: Validation result
            validated_docs: List to potentially add document to
        """
        if self.on_fail == "filter":
            self._stats["total_filtered"] += 1
            logger.debug(f"Filtered document due to validation failure: {result}")

        elif self.on_fail == "raise":
            error_messages = [str(m) for m in result.errors]
            raise ValidationError(
                f"Document validation failed: {'; '.join(error_messages)}",
                result=result,
            )

        elif self.on_fail == "warn":
            logger.warning(f"Document validation warning: {result}")
            validated_docs.append(self._tag_document(doc, result))

        elif self.on_fail == "tag":
            validated_docs.append(self._tag_document(doc, result))

    def _tag_document(self, doc: Document, result: ValidationResult) -> Document:
        """Add validation metadata to document.

        Args:
            doc: Document to tag
            result: Validation result

        Returns:
            Tagged document (same object, modified metadata)
        """
        doc.metadata["_datashield_status"] = result.status.value
        doc.metadata["_datashield_passed"] = result.passed
        doc.metadata["_datashield_message_count"] = len(result.messages)

        if result.errors:
            doc.metadata["_datashield_errors"] = [str(e) for e in result.errors[:5]]

        if "semantic_confidence" in result.metadata:
            doc.metadata["_datashield_confidence"] = result.metadata["semantic_confidence"]

        return doc

    @property
    def stats(self) -> dict[str, int]:
        """Get retrieval and validation statistics."""
        return dict(self._stats)

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        for key in self._stats:
            self._stats[key] = 0

    # LangChain Retriever interface methods

    def get_relevant_documents(
        self,
        query: str,
        *,
        callbacks: CallbackManagerForRetrieverRun | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        run_name: str | None = None,
        **kwargs: Any,
    ) -> list[Document]:
        """Legacy method for LangChain compatibility."""
        return self.invoke(query, **kwargs)

    async def ainvoke(
        self,
        input: str,  # noqa: A002
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[Document]:
        """Async version of invoke."""
        # For now, just call sync version
        # Could be optimized with async validation in the future
        return self.invoke(input, config=config, **kwargs)

    def __repr__(self) -> str:
        return (
            f"ValidatedRetriever(base={self.base_retriever.__class__.__name__}, "
            f"validators={len(self.pipeline.validators)}, on_fail={self.on_fail!r})"
        )


class ValidationError(Exception):
    """Raised when document validation fails and on_fail='raise'."""

    def __init__(self, message: str, result: ValidationResult | None = None):
        super().__init__(message)
        self.result = result


class ValidatedDocumentLoader:
    """A document loader wrapper that validates documents during loading.

    Wraps any LangChain document loader and validates documents as they're
    loaded. Useful for validating data at ingestion time.

    Example:
        >>> from langchain_community.document_loaders import PyPDFLoader
        >>> from datashield.integrations.langchain import ValidatedDocumentLoader
        >>>
        >>> loader = ValidatedDocumentLoader(
        ...     base_loader=PyPDFLoader("document.pdf"),
        ...     validators=[ComplianceValidator(rules=["hipaa"])],
        ...     on_fail="filter",
        ... )
        >>> docs = loader.load()  # Only compliant documents returned
    """

    def __init__(
        self,
        base_loader: Any,
        validators: list[Any] | None = None,
        pipeline: ValidationPipeline | None = None,
        on_fail: OnFailAction = "filter",
        transform: Callable[[Document], dict[str, Any]] | None = None,
    ):
        """Initialize the validated loader.

        Args:
            base_loader: The underlying LangChain document loader
            validators: List of validators to apply
            pipeline: Pre-configured ValidationPipeline
            on_fail: Action when validation fails
            transform: Optional function to transform document to validation input
        """
        self.base_loader = base_loader
        self.on_fail = on_fail
        self.transform = transform

        if pipeline is not None:
            self.pipeline = pipeline
        elif validators:
            self.pipeline = ValidationPipeline(validators=validators)
        else:
            self.pipeline = ValidationPipeline()

    def load(self) -> list[Document]:
        """Load and validate documents.

        Returns:
            List of validated documents
        """
        docs = self.base_loader.load()
        return self._validate_docs(docs)

    def lazy_load(self) -> Any:
        """Lazily load and validate documents.

        Yields:
            Validated documents one at a time
        """
        for doc in self.base_loader.lazy_load():
            data = self._doc_to_data(doc)
            result = self.pipeline.validate(data)

            if result.passed:
                yield doc
            elif self.on_fail == "warn":
                logger.warning(f"Document validation warning: {result}")
                yield doc
            elif self.on_fail == "tag":
                doc.metadata["_datashield_validation"] = result.to_dict()
                yield doc
            elif self.on_fail == "raise":
                raise ValidationError(f"Document validation failed: {result}", result)
            # "filter" - just don't yield

    def _validate_docs(self, docs: list[Document]) -> list[Document]:
        """Validate a list of documents."""
        validated = []
        for doc in docs:
            data = self._doc_to_data(doc)
            result = self.pipeline.validate(data)

            if result.passed:
                validated.append(doc)
            elif self.on_fail == "warn":
                logger.warning(f"Document validation warning: {result}")
                validated.append(doc)
            elif self.on_fail == "tag":
                doc.metadata["_datashield_validation"] = result.to_dict()
                validated.append(doc)
            elif self.on_fail == "raise":
                raise ValidationError(f"Document validation failed: {result}", result)

        return validated

    def _doc_to_data(self, doc: Document) -> dict[str, Any]:
        """Convert document to validation data."""
        if self.transform:
            return self.transform(doc)

        return {
            "content": doc.page_content,
            "metadata": doc.metadata,
            **doc.metadata,
        }


# Type alias for the Document type (avoid import at module level)
try:
    from langchain_core.documents import Document
except ImportError:
    Document = Any  # type: ignore[misc, assignment]
