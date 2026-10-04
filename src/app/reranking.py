"""Native Cohere reranking, with shared trial pacing and explicit client cleanup."""

import os

import cohere
import httpx
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_cohere import CohereRerank
from langchain_core.rate_limiters import InMemoryRateLimiter

from src.config import get_params


class PacedCohereClient(cohere.ClientV2):
    """Pace calls with LangChain; SDK retries cannot bypass the trial limit."""

    def __init__(self, *, api_key, timeout, requests_per_minute):
        self.http_client = httpx.Client(timeout=timeout)
        self.rate_limiter = InMemoryRateLimiter(
            requests_per_second=requests_per_minute / 60,
            max_bucket_size=1,
        )
        super().__init__(
            api_key=api_key, timeout=timeout, httpx_client=self.http_client
        )

    def rerank(self, **kwargs):
        self.rate_limiter.acquire()
        # The pipeline checkpoints failures; hidden SDK retries would be unpaced.
        return super().rerank(**kwargs, request_options={"max_retries": 0})

    def close(self):
        self.http_client.close()


def cohere_api_key():
    """Validate credentials without constructing a client or making a request."""
    api_key = os.environ.get("COHERE_API_KEY", "").strip()
    if not api_key or api_key.startswith("replace-with-"):
        raise ValueError("Set COHERE_API_KEY to a Cohere trial key in your local .env.")
    return api_key


def build_reranking_retriever(base_retriever):
    settings = get_params().reranking
    client = PacedCohereClient(
        api_key=cohere_api_key(),
        timeout=settings.timeout_seconds,
        requests_per_minute=settings.requests_per_minute,
    )
    # CohereRerank sends only page_content and copies original text and metadata.
    compressor = CohereRerank(
        client=client, model=settings.model, top_n=get_params().retrieval.k
    )
    return ContextualCompressionRetriever(
        base_retriever=base_retriever, base_compressor=compressor
    )
