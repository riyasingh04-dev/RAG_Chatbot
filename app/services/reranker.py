from typing import List
from flashrank import Ranker, RerankRequest
from langchain_core.documents import Document
from loguru import logger

class EnterpriseReranker:
    def __init__(self, model_name: str = "ms-marco-TinyBERT-L-2-v2"):
        try:
            self.ranker = Ranker(model_name=model_name, cache_dir="db/flashrank_cache")
            logger.info(f"Initialized FlashRanker: {model_name}")
        except Exception as e:
            logger.error(f"Reranker failed to init: {e}")
            self.ranker = None

    def rerank(self, query: str, documents: List[Document], top_n: int = 5) -> List[Document]:
        """Rerank retrieved chunks for relevance."""
        if not self.ranker or not documents:
            return documents[:top_n]

        passages = [
            {"id": i, "text": doc.page_content, "meta": doc.metadata}
            for i, doc in enumerate(documents)
        ]

        results = self.ranker.rerank(RerankRequest(query=query, passages=passages))
        
        return [
            Document(page_content=res["text"], metadata=res["meta"])
            for res in results[:top_n]
        ]

reranker = EnterpriseReranker()
