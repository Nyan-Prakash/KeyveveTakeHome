"""Utilities for generating and working with embeddings."""

from openai import OpenAI

from backend.app.config import get_openai_api_key


def generate_embedding(text: str, model: str = "text-embedding-3-small", dimensions: int = 1536) -> list[float] | None:
    """Generate embedding vector for text.

    Args:
        text: Text to embed
        model: OpenAI embedding model to use
        dimensions: Dimensionality of output vector

    Returns:
        Embedding vector or None if generation fails
    """
    try:
        client = OpenAI(api_key=get_openai_api_key())
        response = client.embeddings.create(
            model=model,
            input=text,
            dimensions=dimensions,
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Warning: Failed to generate embedding: {e}")
        return None


def batch_generate_embeddings(
    texts: list[str], model: str = "text-embedding-3-small", dimensions: int = 1536
) -> list[list[float] | None]:
    """Generate embeddings for multiple texts in a single API call.

    More efficient than calling generate_embedding multiple times.

    Args:
        texts: List of texts to embed (max 2048 for OpenAI)
        model: OpenAI embedding model to use
        dimensions: Dimensionality of output vectors

    Returns:
        List of embedding vectors (None for failed items)
    """
    if not texts:
        return []

    try:
        client = OpenAI(api_key=get_openai_api_key())
        response = client.embeddings.create(
            model=model,
            input=texts,
            dimensions=dimensions,
        )
        # Return embeddings in original order
        return [item.embedding for item in response.data]
    except Exception as e:
        print(f"Warning: Batch embedding generation failed: {e}")
        # Fall back to None for all items
        return [None] * len(texts)
