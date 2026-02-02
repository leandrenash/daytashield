"""DataShield LangChain Integration Example.

This example demonstrates how to use DataShield with LangChain
to validate documents in a RAG (Retrieval Augmented Generation) pipeline.
"""

from datashield import FreshnessValidator, SchemaValidator, ValidationPipeline
from datashield.integrations.langchain import ValidatedRetriever, ValidationError

# Note: This example requires langchain and a vector store to be installed
# pip install langchain langchain-community faiss-cpu


def mock_retriever_example() -> None:
    """Demonstrate ValidatedRetriever with mock data."""
    print("=" * 60)
    print("DataShield LangChain Integration Example")
    print("=" * 60)

    # In a real application, you would create a vector store like this:
    #
    # from langchain_community.vectorstores import FAISS
    # from langchain_openai import OpenAIEmbeddings
    #
    # texts = ["Document 1 content", "Document 2 content"]
    # metadatas = [
    #     {"source": "doc1.pdf", "timestamp": "2024-01-15"},
    #     {"source": "doc2.pdf", "timestamp": "2023-06-01"},  # Old document
    # ]
    # vectorstore = FAISS.from_texts(texts, OpenAIEmbeddings(), metadatas=metadatas)
    # base_retriever = vectorstore.as_retriever()

    # For this example, we'll demonstrate the validation logic directly
    print("\n1. Setting up Validators")
    print("-" * 40)

    # Define document schema
    doc_schema = {
        "type": "object",
        "required": ["content"],
        "properties": {
            "content": {"type": "string", "minLength": 1},
            "source": {"type": "string"},
            "timestamp": {"type": "string"},
        },
    }

    validators = [
        SchemaValidator(schema=doc_schema),
        FreshnessValidator(max_age="90d"),  # Documents must be < 90 days old
    ]

    print(f"Configured {len(validators)} validators:")
    for v in validators:
        print(f"  - {v.name}")

    # Create validation pipeline
    print("\n2. Validating Documents")
    print("-" * 40)

    pipeline = ValidationPipeline(validators)

    # Simulate retrieved documents
    documents = [
        {
            "content": "Our refund policy allows returns within 30 days.",
            "source": "policy.pdf",
            "timestamp": "2024-01-10T00:00:00Z",
        },
        {
            "content": "Products can be exchanged for store credit.",
            "source": "faq.pdf",
            "timestamp": "2023-06-15T00:00:00Z",  # This might be stale
        },
        {
            "content": "",  # Empty content - should fail schema validation
            "source": "empty.pdf",
        },
    ]

    for i, doc in enumerate(documents, 1):
        result = pipeline.validate(doc)
        status_emoji = "✅" if result.passed else "❌"
        print(f"\nDocument {i} ({doc.get('source', 'unknown')}): {status_emoji} {result.status.value}")

        if result.messages:
            for msg in result.messages:
                print(f"    [{msg.severity.value}] {msg.message}")

    # Demonstrate ValidatedRetriever behavior
    print("\n3. ValidatedRetriever Modes")
    print("-" * 40)

    print("""
The ValidatedRetriever supports different modes for handling validation failures:

1. on_fail="filter" (default)
   - Invalid documents are silently removed from results
   - Use when you want only valid documents

2. on_fail="raise"  
   - Raises ValidationError for any invalid document
   - Use when data quality is critical

3. on_fail="warn"
   - Logs a warning but includes the document
   - Use for monitoring without blocking

4. on_fail="tag"
   - Adds validation metadata to document
   - Use when you want to handle validation downstream

Example usage:

    retriever = ValidatedRetriever(
        base_retriever=vectorstore.as_retriever(),
        validators=[
            SchemaValidator(schema=doc_schema),
            FreshnessValidator(max_age="7d"),
        ],
        on_fail="filter",
    )
    
    # Only returns documents that pass validation
    docs = retriever.invoke("What is the refund policy?")
""")

    print("\n4. Semantic Validation Example")
    print("-" * 40)

    print("""
For content-aware validation, you can add SemanticValidator:

    from datashield import SemanticValidator
    
    validators = [
        SchemaValidator(schema=doc_schema),
        SemanticValidator(
            prompt="Check if this document is relevant to customer support",
            criteria=["is_support_related", "is_professional", "is_factual"],
        ),
    ]

This uses an LLM to evaluate document quality beyond schema checks.
Requires: pip install litellm
""")

    print("\n" + "=" * 60)
    print("LangChain integration example complete!")
    print("=" * 60)


def main() -> None:
    """Run the LangChain integration example."""
    mock_retriever_example()


if __name__ == "__main__":
    main()
