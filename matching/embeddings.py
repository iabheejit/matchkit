"""Embedding generation using Azure OpenAI."""
import logging
import time
from typing import List, Optional

from openai import AzureOpenAI
from config.settings import settings

logger = logging.getLogger(__name__)

# Maximum inputs per batch call (OpenAI limit is 2048)
MAX_BATCH_SIZE = 256


class EmbeddingGenerator:
    """Generate embeddings using Azure OpenAI."""

    def __init__(self):
        if settings.azure_openai_endpoint and settings.azure_openai_api_key:
            self.client = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version="2024-02-01",
            )
            logger.info("Azure OpenAI client initialized")
        else:
            self.client = None
            logger.warning("Azure OpenAI credentials not configured — embeddings disabled")

    def generate(self, text: str, retries: int = 3) -> Optional[List[float]]:
        """Generate embedding for a single text with retry logic."""
        if not self.client:
            return None
        if not text or not text.strip():
            return None

        for attempt in range(1, retries + 1):
            try:
                response = self.client.embeddings.create(
                    model=settings.azure_openai_embedding_deployment,
                    input=text.strip(),
                )
                return response.data[0].embedding
            except Exception as e:
                logger.warning(f"Embedding attempt {attempt}/{retries} failed: {e}")
                if attempt < retries:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Embedding generation failed after {retries} attempts: {e}")
                    return None

    def generate_batch(self, texts: List[str], retries: int = 3) -> List[Optional[List[float]]]:
        """Generate embeddings for multiple texts using batch API."""
        if not self.client:
            return [None] * len(texts)

        results: List[Optional[List[float]]] = [None] * len(texts)

        for chunk_start in range(0, len(texts), MAX_BATCH_SIZE):
            chunk_end = min(chunk_start + MAX_BATCH_SIZE, len(texts))
            chunk_texts = texts[chunk_start:chunk_end]

            valid_indices = []
            valid_texts = []
            for i, text in enumerate(chunk_texts):
                if text and text.strip():
                    valid_indices.append(chunk_start + i)
                    valid_texts.append(text.strip())

            if not valid_texts:
                continue

            for attempt in range(1, retries + 1):
                try:
                    response = self.client.embeddings.create(
                        model=settings.azure_openai_embedding_deployment,
                        input=valid_texts,
                    )
                    for j, embedding_data in enumerate(response.data):
                        results[valid_indices[j]] = embedding_data.embedding

                    logger.info(
                        f"Generated {len(valid_texts)} embeddings "
                        f"(batch {chunk_start // MAX_BATCH_SIZE + 1})"
                    )
                    break
                except Exception as e:
                    logger.warning(
                        f"Batch embedding attempt {attempt}/{retries} failed: {e}"
                    )
                    if attempt < retries:
                        time.sleep(2 ** attempt)
                    else:
                        logger.error(f"Batch embedding failed after {retries} attempts")

        return results

    def generate_for_organization(self, org) -> Optional[List[float]]:
        """Generate embedding for an Organization model instance."""
        text = org.to_profile_text()
        return self.generate(text)


# Singleton instance
embedding_generator = EmbeddingGenerator()
