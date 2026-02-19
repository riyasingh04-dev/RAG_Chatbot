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
        comparison_keywords = ['vs', 'versus', 'compare', 'difference between', 'who has', 'better', 'more experience', 'higher']
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in comparison_keywords)

    def _is_resume_query(self, query: str) -> bool:
        """Detect if query is likely about resumes/CVs."""
        resume_keywords = ['resume', 'cv', 'experience', 'skills', 'background', 'qualification', 'candidate', 'education']
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in resume_keywords)

    def _get_unique_resumes(self) -> List[str]:
        """Fetch unique file names that look like resumes from the vector store."""
        if not faiss_service.vector_db:
            return []
        
        all_docs = faiss_service.vector_db.docstore._dict.values()
        resumes = set()
        resume_exts = {'.pdf', '.docx', '.txt'} # Common resume files
        
        for doc in all_docs:
            source = doc.metadata.get("file_name", "").lower()
            if any(k in source for k in ['resume', 'cv', 'profile', 'candidate']) or \
               any(source.endswith(ext) for ext in resume_exts):
                # Filter out obvious non-resumes like tutorials if they were indexed
                if 'pattern' not in source and 'tutorial' not in source:
                    resumes.add(doc.metadata["file_name"])
        
        return list(resumes)

    async def _translate_query_if_needed(self, query: str) -> str:
        """Detects if query is non-English and translates to English."""
        # Check for non-ASCII characters
        is_ascii = all(ord(c) < 128 for c in query.replace(" ", ""))
        if is_ascii:
            return query

        logger.info(f"Non-ASCII characters detected in query: '{query}'. Attempting translation...")
        try:
            system_prompt = (
                "You are a precise translator. Translate the following user query to English "
                "so it can be used for vector retrieval. Output ONLY the translated query. "
                "Do not explain. If it is already English, output it as is."
            )
            
            translated = ""
            async for chunk in llm_service.generate_response(
                query=query,
                context=" ", 
                role="Research AI", 
                chat_history=[]
            ):
                translated += chunk
            
            translated = translated.strip().strip('"')
            logger.info(f"Translated query: '{query}' -> '{translated}'")
            return translated
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return query

    def _extract_entities(self, query: str) -> list:
        """Extract potential entity names from query."""
        import re
        words = query.split()
        entities = []
        skip_words = {"resume", "cv", "vs", "versus", "compare", "difference", "between", "and", "or", "better", "experience", "skills", "candidate", "more", "most", "less"}
        
        for word in words:
            clean_word = re.sub(r'[^\w\s]', '', word)
            if clean_word and clean_word[0].isupper() and len(clean_word) > 2 and clean_word.lower() not in skip_words:
                entities.append(clean_word)
        return entities

    def retrieve_for_comparison(self, query: str, entities: list) -> List[Document]:
        """Specialized retrieval for comparison queries with file scoping."""
        all_docs = []
        seen_ids = set() 
        
        is_resume_q = self._is_resume_query(query)
        
        # If no specific entities found but it's a resume comparison, use all resumes
        if not entities and is_resume_q:
            entities = self._get_unique_resumes()
            logger.info(f"No specific entities found for resume comparison. Using all discovered resumes: {entities}")

        for entity in entities:
            # Source scoping: filter candidates by entity name in filename/content
            entity_query = f"{entity} experience skills background"
            if is_resume_q:
                entity_query = f"{entity} resume CV highlights"

            logger.info(f"Retrieving for entity: {entity}")
            
            # Initial search with higher recall for the specific entity
            base_docs = faiss_service.similarity_search(entity_query, k=50)
            
            # HARD FILTER: Ensure docs belong to the entity or document scope
            entity_docs = []
            for d in base_docs:
                source = d.metadata.get("file_name", "").lower()
                content = d.page_content.lower()
                if entity.lower() in source or entity.lower() in content:
                    entity_docs.append(d)
                # If it's a resume query, also allow chunks from resume-named files even if name match fails
                elif is_resume_q and ('resume' in source or 'cv' in source):
                    entity_docs.append(d)

            if entity_docs:
                # Rerank the filtered set
                reranked_docs = reranker.rerank(entity_query, entity_docs, top_n=7)
                added = 0
                for doc in reranked_docs:
                    uid = doc.metadata.get("chunk_id") or f"{doc.metadata.get('source')}_{doc.metadata.get('page')}_{hash(doc.page_content[:50])}"
                    if uid not in seen_ids:
                        all_docs.append(doc)
                        seen_ids.add(uid)
                        added += 1
                        if added >= 5: break

        return all_docs[:self.top_n]

    def _is_visual_query(self, query: str) -> bool:
        """Detect if query is seeking visual output, with basic negation handling."""
        visual_keywords = ['show', 'graph', 'diagram', 'chart', 'figure', 'candle', 'plot', 'visualization', 'sample', 'image', 'picture', 'snapshot', 'ss']
        negation_keywords = ['no', 'none', 'without', 'dont', 'don\'t', 'do not', 'stop', 'not', 'never']
        
        query_lower = query.lower().replace("-", " ").replace("_", " ")
        words = query_lower.split()
        
        # Check if any visual keyword is present
        has_visual_kw = any(kw in query_lower for kw in visual_keywords)
        if not has_visual_kw:
            return False
            
        # Check for negation: if a negation word appears before or near a visual keyword
        for i, word in enumerate(words):
            if word in negation_keywords:
                # Look ahead a few words for a visual keyword
                for j in range(i + 1, min(i + 4, len(words))):
                    if any(kw == words[j] for kw in visual_keywords):
                        logger.info(f"Visual negation detected in query: '{query}'")
                        return False
        
        return True

    async def retrieve(self, query: str) -> List[Document]:
        """Enhanced retrieval pipeline with intent-based filtering."""
        query = await self._translate_query_if_needed(query)
        
        # 1. Comparison Queries
        if self._is_comparison_query(query):
            entities = self._extract_entities(query)
            # If no entities but is resume query, or if entities found
            if entities or self._is_resume_query(query):
                return self.retrieve_for_comparison(query, entities)
        
        # 2. Standard Retrieval with File Scoping
        is_visual = self._is_visual_query(query)
        is_resume = self._is_resume_query(query)
        
        fetch_k = 100 if (is_visual or is_resume) else self.top_k
        base_docs = faiss_service.similarity_search(query, k=fetch_k)
        
        if not base_docs:
            return []

        # Intent Filtering: If resume query, remove unrelated technical docs early
        if is_resume:
            filtered = [d for d in base_docs if 'pattern' not in d.metadata.get('file_name', '').lower()]
            if filtered: base_docs = filtered

        # Visual Prioritization
        if is_visual:
            visual_docs = [d for d in base_docs if d.metadata.get("image_url")]
            other_docs = [d for d in base_docs if not d.metadata.get("image_url")]
            base_docs = visual_docs + other_docs

        final_docs = reranker.rerank(query, base_docs, top_n=self.top_n)
        return final_docs

    async def get_relevant_context(self, query: str) -> str:
        """Helper for websocket/standard chat to get a formatted context string."""
        docs = await self.retrieve(query)
        if not docs:
            return ""
            
        context_parts = []
        for doc in docs:
            source = doc.metadata.get("file_name", "Source")
            page = doc.metadata.get("page", "?")
            image_url = doc.metadata.get("image_url")
            content = doc.page_content.replace("\n", " ").strip()
            
            ref_str = f"[Source: {source} (Pg {page})]"
            if image_url:
                ref_str += f"\n[Image Reference: {image_url}]"
                
            context_parts.append(f"{ref_str}\n{content}")
            
        return "\n\n---\n\n".join(context_parts)

rag_retriever = RagRetriever()
