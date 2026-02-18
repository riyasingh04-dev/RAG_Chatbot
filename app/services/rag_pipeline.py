from typing import List, Optional
import asyncio
from langchain_core.documents import Document
from loguru import logger
from app.services.faiss_service import faiss_service
from app.core.config import settings
from app.services.reranker import reranker
# Import llm_service cleanly to avoid circular dependency issues at module level if any
# We will use lazy import inside methods if needed, but top level is likely fine given dependency graph.
from app.services.llm_service import llm_service

class RagRetriever:
    def __init__(self, top_k: int = 25, top_n: int = 15):
        self.top_k = top_k  # Number of docs to retrieve initially (increased for better recall)
        self.top_n = top_n  # Number of docs after reranking (increased to 15 for multi-resume queries)

    def _is_comparison_query(self, query: str) -> bool:
        """Detect if query is asking for comparison."""
        comparison_keywords = ['vs', 'versus', 'compare', 'than', 'better', 'more', 'less', 'difference between', 'who has']
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in comparison_keywords)

    async def _translate_query_if_needed(self, query: str) -> str:
        """
        Detects if query is non-English (simple heuristic + LLM check) and translates to English.
        """
        # 1. Heuristic: Check for non-ASCII characters (e.g., Hindi, Chinese, etc.)
        # This is a fast check. If mostly ASCII, we assume English/Code and skip translation to save latency.
        is_ascii = all(ord(c) < 128 for c in query.replace(" ", ""))
        if is_ascii:
            return query

        # 2. LLM Translation
        logger.info(f"Non-ASCII characters detected in query: '{query}'. Attempting translation...")
        try:
            # We use a direct minimal prompt for translation
            system_prompt = (
                "You are a precise translator. Translate the following user query to English "
                "so it can be used for vector retrieval. Output ONLY the translated query. "
                "Do not explain. If it is already English, output it as is."
            )
            
            # Using llm_service helper if available, or direct call. 
            # llm_service.generate_response is a generator, so we collect needed parts.
            # We'll create a lightweight non-streaming call or just collect the stream.
            translated = ""
            async for chunk in llm_service.generate_response(
                query=query,
                context=" ", # Dummy context to bypass strict safeguards in generate_response if any, or we should add a specific simple method in llm_service
                role="Research AI", # Use a standard role
                chat_history=[]
            ):
                translated += chunk
            
            # Cleanup
            translated = translated.strip().strip('"')
            logger.info(f"Translated query: '{query}' -> '{translated}'")
            return translated
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return query

    def _extract_entities(self, query: str) -> list:
        """Extract potential entity names from query (simple keyword extraction)."""
        import re
        words = query.split()
        entities = []
        skip_words = {"resume", "cv", "vs", "versus", "compare", "difference", "between", "and", "or", "better", "experience", "skills"}
        
        for word in words:
            # Remove punctuation
            clean_word = re.sub(r'[^\w\s]', '', word)
            if clean_word and clean_word[0].isupper() and len(clean_word) > 2 and clean_word.lower() not in skip_words:
                entities.append(clean_word)
        return entities

    def retrieve_for_comparison(self, query: str, entities: list) -> List[Document]:
        """
        Special retrieval for comparison queries.
        Runs separate retrievals for each entity and combines results.
        """
        all_docs = []
        seen_ids = set() 
        
        logger.info(f"Running multi-entity retrieval for: {entities}")
        
        # Detect if this is a resume comparison
        is_resume_query = any(keyword in query.lower() for keyword in ['resume', 'cv', 'experience', 'skills', 'background', 'qualification'])
        
        # Retrieve for each entity
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
            # Increase k for candidate generation to ensure we get the right person's doc
            base_docs = faiss_service.similarity_search(entity_query, k=max(self.top_k, 50))
            
            # Verify we actually got docs for this entity (simple keyword check in source/content)
            # If not, retry with even higher k
            entity_docs_filtered = [d for d in base_docs if entity.lower() in d.page_content.lower() or entity.lower() in d.metadata.get("source", "").lower()]
            
            if not entity_docs_filtered:
                 logger.warning(f"No specific docs found for {entity} with k={self.top_k}, retrying with k=100")
                 base_docs = faiss_service.similarity_search(entity_query, k=100)
            
            retrieval_time = time.time() - start_retrieval
            if settings.DEBUG_RAG:
                logger.debug(f"Entity '{entity}': retrieved {len(base_docs)} candidate chunks (latency={retrieval_time:.3f}s)")
            
            if base_docs:
                # Rerank
                start_rerank = time.time()
                # Use a good top_n for this entity
                reranked_docs = reranker.rerank(entity_query, base_docs, top_n=10)
                rerank_time = time.time() - start_rerank
                
                # record rerank metric
                try:
                    from app.services.metrics import record_rerank
                    record_rerank(rerank_time)
                except Exception:
                    pass

                # Add to all_docs with deduplication
                added_count = 0
                for doc in reranked_docs:
                    # Deduplicate by unique chunk_id if available, else standard fallback
                    # We WANT multiple chunks from the same file, just not the exact same chunk.
                    unique_id = doc.metadata.get("chunk_id")
                    if not unique_id:
                        # Fallback signature: source + page + content_start
                        unique_id = f"{doc.metadata.get('source')}_{doc.metadata.get('page')}_{hash(doc.page_content[:50])}"
                    
                    if unique_id not in seen_ids:
                        all_docs.append(doc)
                        seen_ids.add(unique_id)
                        added_count += 1
                        # Limit per entity to avoid overwhelming context
                        if added_count >= 7:
                            break
        
        # If we still have very few docs, fallback to standard retrieval
        if len(all_docs) < 3:
            logger.info("Multi-entity retrieval yielded few results, falling back to standard retrieval.")
            extra_docs = faiss_service.similarity_search(query, k=self.top_k)
            reranked_extra = reranker.rerank(query, extra_docs, top_n=self.top_n)
            for doc in reranked_extra:
                unique_id = doc.metadata.get("chunk_id")
                if not unique_id:
                    unique_id = f"{doc.metadata.get('source')}_{doc.metadata.get('page')}_{hash(doc.page_content[:50])}"
                
                if unique_id not in seen_ids:
                    all_docs.append(doc)
                    seen_ids.add(unique_id)
        
        logger.info(f"Multi-entity retrieval returned {len(all_docs)} documents")
        return all_docs[:self.top_n]

    async def retrieve(self, query: str) -> List[Document]:
        """Full retrieval pipeline with comparison query support."""
        
        # Translate if needed
        query = await self._translate_query_if_needed(query)
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
