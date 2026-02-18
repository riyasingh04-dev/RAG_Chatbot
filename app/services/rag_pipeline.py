from typing import List
from langchain_core.documents import Document
from loguru import logger
from app.services.faiss_service import faiss_service
from app.core.config import settings
from app.services.reranker import reranker

class RagRetriever:
    def __init__(self, top_k: int = 25, top_n: int = 15):
        self.top_k = top_k  # Number of docs to retrieve initially (increased for better recall)
        self.top_n = top_n  # Number of docs after reranking (increased to 15 for multi-resume queries)

    def _is_comparison_query(self, query: str) -> bool:
        """Detect if query is asking for comparison."""
        comparison_keywords = ['vs', 'versus', 'compare', 'than', 'better', 'more', 'less', 'difference between', 'who has']
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in comparison_keywords)

    def _extract_entities(self, query: str) -> list:
        """Extract potential entity names from query (simple keyword extraction)."""
        import re
        words = query.split()
        entities = []
        for word in words:
            # Remove punctuation and check if starts with capital
            clean_word = re.sub(r'[^\w\s]', '', word)
            if clean_word and clean_word[0].isupper() and len(clean_word) > 2:
                entities.append(clean_word)
        return entities

    def retrieve_for_comparison(self, query: str, entities: list) -> List[Document]:
        """
        Special retrieval for comparison queries.
        Runs separate retrievals for each entity and combines results.
        """
        all_docs = []
        seen_content = set()  # Use content hash to avoid duplicates
        
        logger.info(f"Running multi-entity retrieval for: {entities}")
        
        # Detect if this is a resume comparison
        is_resume_query = any(keyword in query.lower() for keyword in ['resume', 'cv', 'experience', 'skills', 'background', 'qualification'])
        
        # Retrieve for each entity (top 5 from each to ensure balanced representation)
        for entity in entities:
            # Build entity-specific query
            if is_resume_query:
                entity_query = f"{entity} resume CV experience skills education projects certifications"
            else:
                entity_query = f"{entity} experience skills background"
            
            logger.info(f"Retrieving for entity: {entity} (resume query: {is_resume_query})")
            
            # Get initial docs
            import time
            start_retrieval = time.time()
            base_docs = faiss_service.similarity_search(entity_query, k=self.top_k)
            retrieval_time = time.time() - start_retrieval
            if settings.DEBUG_RAG:
                logger.debug(f"Entity '{entity}': retrieved {len(base_docs)} candidate chunks from hybrid retriever (latency={retrieval_time:.3f}s)")
            if base_docs:
                # Log sources before rerank
                pre_sources = [d.metadata.get("file_name") or d.metadata.get("source") for d in base_docs]
                logger.debug(f"Entity '{entity}': pre-rerank sources: {pre_sources}")

                # Rerank
                # Rerank and time it
                start_rerank = time.time()
                entity_docs = reranker.rerank(entity_query, base_docs, top_n=7)
                rerank_time = time.time() - start_rerank
                # record rerank metric
                try:
                    from app.services.metrics import record_rerank
                    record_rerank(rerank_time)
                except Exception:
                    pass
                if settings.DEBUG_RAG:
                    logger.debug(f"Entity '{entity}': post-rerank returned {len(entity_docs)} chunks (latency={rerank_time:.3f}s)")
                    post_sources = [d.metadata.get("file_name") or d.metadata.get("source") for d in entity_docs]
                    logger.debug(f"Entity '{entity}': post-rerank sources: {post_sources}")

                # Take top 5 from this entity
                for doc in entity_docs[:5]:
                    # Use the document `source` (full path) or `file_name` as the
                    # de-duplication key so separate files are not collapsed by
                    # short-content collisions. Fall back to a content hash only
                    # if no metadata is present.
                    source_key = doc.metadata.get("source") or doc.metadata.get("file_name")
                    if not source_key:
                        source_key = str(hash(doc.page_content))

                    if source_key not in seen_content:
                        all_docs.append(doc)
                        seen_content.add(source_key)
        
        # Fill remaining slots with original query results if needed
        if len(all_docs) < self.top_n:
            logger.info("Filling remaining slots with original query results")
            start_retrieval = time.time()
            base_docs = faiss_service.similarity_search(query, k=self.top_k)
            retrieval_time = time.time() - start_retrieval
            if settings.DEBUG_RAG:
                logger.debug(f"Original query retrieval returned {len(base_docs)} candidates (latency={retrieval_time:.3f}s)")
            if base_docs:
                start_rerank = time.time()
                original_docs = reranker.rerank(query, base_docs, top_n=self.top_n)
                rerank_time = time.time() - start_rerank
                if settings.DEBUG_RAG:
                    logger.debug(f"Original query: post-rerank returned {len(original_docs)} chunks (latency={rerank_time:.3f}s)")
                for doc in original_docs:
                    if len(all_docs) >= self.top_n:
                        break
                    source_key = doc.metadata.get("source") or doc.metadata.get("file_name")
                    if not source_key:
                        source_key = str(hash(doc.page_content))

                    if source_key not in seen_content:
                        all_docs.append(doc)
                        seen_content.add(source_key)
        
        logger.info(f"Multi-entity retrieval returned {len(all_docs)} documents")
        return all_docs[:self.top_n]

    def retrieve(self, query: str) -> List[Document]:
        """Full retrieval pipeline with comparison query support."""
        logger.info(f"Retrieving documents for query: {query}")
        
        # Check if this is a comparison query
        if self._is_comparison_query(query):
            entities = self._extract_entities(query)
            if len(entities) >= 2:
                logger.info(f"🔍 Detected comparison query with entities: {entities}")
                return self.retrieve_for_comparison(query, entities)
        
        # Standard retrieval for non-comparison queries
        base_docs = faiss_service.similarity_search(query, k=self.top_k)
        
        if not base_docs:
            logger.warning("No documents retrieved from knowledge base.")
            return []

        # Re-ranking (Cross-Encoder for better relevance)
        final_docs = reranker.rerank(query, base_docs, top_n=self.top_n)
        
        return final_docs

    async def get_relevant_context(self, query: str) -> str:
        """Helper for websocket/standard chat to get a formatted context string."""
        docs = self.retrieve(query)
        if not docs:
            return ""
            
        # Format context with metadata references
        context_parts = []
        for doc in docs:
            source = doc.metadata.get("file_name", "Unknown Source")
            content = doc.page_content.replace("\n", " ").strip()
            context_parts.append(f"[Source: {source}]\n{content}")
            
        return "\n\n---\n\n".join(context_parts)

rag_retriever = RagRetriever()
