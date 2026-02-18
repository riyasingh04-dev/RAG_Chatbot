import os
import pickle
from typing import List, Optional
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from loguru import logger
from app.core.config import settings

class FAISSService:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)
        self.index_path = settings.INDEX_PATH
        self.vector_db: Optional[FAISS] = None
        self.bm25_retriever: Optional[BM25Retriever] = None
        self._load_all_indices()

    def _load_all_indices(self):
        """Loads FAISS and BM25 indices from disk."""
        # Load FAISS
        if os.path.exists(os.path.join(self.index_path, "index.faiss")):
            try:
                self.vector_db = FAISS.load_local(
                    self.index_path, 
                    self.embeddings, 
                    allow_dangerous_deserialization=True
                )
                logger.info("Loaded existing FAISS index.")
            except Exception as e:
                logger.error(f"Error loading FAISS index: {e}")

        # Load BM25 (serialized via pickle)
        bm25_path = os.path.join(self.index_path, "bm25_retriever.pkl")
        if os.path.exists(bm25_path):
            try:
                with open(bm25_path, "rb") as f:
                    self.bm25_retriever = pickle.load(f)
                logger.info("Loaded existing BM25 index.")
            except Exception as e:
                logger.error(f"Error loading BM25 index: {e}")

    def add_documents(self, chunks: List[Document]):
        """Adds chunks to both FAISS and BM25 indices."""
        if not chunks:
            return

        # Update FAISS
        if self.vector_db is None:
            self.vector_db = FAISS.from_documents(chunks, self.embeddings)
        else:
            self.vector_db.add_documents(chunks)
        
        # Update BM25 (re-build is necessary for rank-bm25 in current langchain impl)
        # Note: In a production system with millions of docs, we'd use a more scalable keyword search.
        # For this scale, re-initializing from all documents is fine.
        all_docs = self.vector_db.docstore._dict.values()
        self.bm25_retriever = BM25Retriever.from_documents(list(all_docs))
        # Increase BM25 k to ensure we return enough candidates for downstream reranking
        # Keep reasonably high to support multi-file queries
        self.bm25_retriever.k = 50
        
        # Save both
        os.makedirs(self.index_path, exist_ok=True)
        self.vector_db.save_local(self.index_path)
        
        bm25_path = os.path.join(self.index_path, "bm25_retriever.pkl")
        with open(bm25_path, "wb") as f:
            pickle.dump(self.bm25_retriever, f)
            
        logger.info(f"Indexed {len(chunks)} new chunks. Total docs: {len(all_docs)}")

    def get_hybrid_retriever(self, semantic_weight: float = 0.8, keyword_weight: float = 0.2):
        """Returns an EnsembleRetriever combining FAISS and BM25."""
        if not self.vector_db or not self.bm25_retriever:
            logger.warning("Indices not fully initialized for hybrid search.")
            if self.vector_db:
                return self.vector_db.as_retriever(search_kwargs={"k": 15})
            return None

        ensemble_retriever = EnsembleRetriever(
            retrievers=[
                # Increase FAISS retriever k to ensure upstream callers requesting
                # larger top_k (e.g. 25) receive enough candidates from the vector store.
                self.vector_db.as_retriever(search_kwargs={"k": 50}),
                self.bm25_retriever
            ],
            weights=[semantic_weight, keyword_weight]
        )
        return ensemble_retriever

    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        """Hybrid search with ensemble retrieval."""
        retriever = self.get_hybrid_retriever()
        if not retriever:
            return []
        import time
        from app.core.config import settings

        # Request candidates from the ensemble retriever and then slice to the
        # requested `k`. If the retriever returns too few candidates, retry
        # once with a larger k to improve recall (safeguard).
        start = time.time()
        results = retriever.get_relevant_documents(query)
        retrieval_latency = (time.time() - start)

        # record metrics
        try:
            from app.services.metrics import record_retrieval
            sources = [d.metadata.get("file_name") or d.metadata.get("source") for d in results]
            record_retrieval(retrieval_latency, len(results), sources)
        except Exception:
            sources = []

        if settings.DEBUG_RAG:
            logger.debug(f"FAISS hybrid retriever returned {len(results)} candidates for requested k={k} (latency={retrieval_latency:.3f}s)")
            try:
                logger.debug(f"FAISS hybrid retriever candidate sources: {sources}")
            except Exception:
                pass

        # Safeguard: if fewer than 3 candidates, retry once with increased k
        if len(results) < 3 and k < 100:
            # Expand candidate window and retry once
            retry_k = min(100, max(k * 3, 25))
            if settings.DEBUG_RAG:
                logger.info(f"Insufficient candidates ({len(results)}) for k={k}, retrying retriever with k={retry_k}")
            start2 = time.time()
            results_retry = retriever.get_relevant_documents(query)
            retry_latency = (time.time() - start2)
            # update metrics with retry result if better
            try:
                from app.services.metrics import record_retrieval
                sources_retry = [d.metadata.get("file_name") or d.metadata.get("source") for d in results_retry]
                record_retrieval(retry_latency, len(results_retry), sources_retry)
            except Exception:
                pass
            if settings.DEBUG_RAG:
                logger.debug(f"Retry returned {len(results_retry)} candidates (latency={retry_latency:.3f}s)")
            # Choose the larger result set
            if len(results_retry) > len(results):
                results = results_retry

        return results[:k]

faiss_service = FAISSService()
