from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.rag_pipeline import rag_retriever
from app.services.llm_service import llm_service
from app.services.cache_service import cache_service
from app.auth.jwt_handler import decode_access_token
from loguru import logger
import json
from app.core.config import settings

router = APIRouter()

@router.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str, token: str = None):
    # Verify token
    if not token or not decode_access_token(token):
        await websocket.accept()
        await websocket.send_text(json.dumps({"type": "error", "content": "Unauthorized"}))
        await websocket.close()
        return

    await websocket.accept()
    logger.info(f"WebSocket session {session_id} connected (Authenticated).")
    
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            query = payload.get("message")
            role = payload.get("role", "Research AI")
            logger.info(f"Received query from session {session_id}: {query}")
            
            # 1. Check Cache / History
            try:
                history = cache_service.get_session_history(session_id)
                logger.debug(f"History items found: {len(history)}")
            except Exception as e:
                logger.error(f"History fetch failed: {e}")
                history = []
            
            # 2. Retrieve Context (with hybrid search and reranking)
            logger.debug("Retrieving context...")
            # Use .retrieve() to get Document objects so we can pass raw content to the LLM
            context_docs = rag_retriever.retrieve(query)
            logger.info(f"Context retrieved (len: {len(context_docs)})")
            # Debug: list files retrieved
            try:
                retrieved_files = [d.metadata.get("file_name") or d.metadata.get("source") for d in context_docs]
                logger.debug(f"Retrieved document sources: {retrieved_files}")
            except Exception:
                logger.debug("Could not list retrieved document sources")
            # Debug: print query, retrieved chunks count and top chunk preview
            logger.debug(f"Query: {query}")
            logger.debug(f"Retrieved chunks: {len(context_docs)}")
            if context_docs:
                top_preview = context_docs[0].page_content[:200].replace("\n", " ")
                logger.debug(f"Top chunk preview (200 chars): {top_preview}")
            
            # 3. Stream LLM Response & Sources
            
            # Extract sources from context to send to UI
            sources = []
            seen_images = set()
            for doc in context_docs:
                img_url = doc.metadata.get("image_url")
                if img_url and img_url not in seen_images:
                    sources.append({"image_url": img_url, "title": doc.metadata.get("file_name", "Document")})
                    seen_images.add(img_url)
            
            # Send sources immediately if available
            if sources:
                 await websocket.send_text(json.dumps({"type": "chunk", "content": "", "sources": sources}))

            # Format context for LLM (without source labels)
            context_str = ""
            if context_docs:
                parts = []
                for doc in context_docs:
                    content = doc.page_content.replace("\n", " ").strip()
                    parts.append(content)
                context_str = "\n\n---\n\n".join(parts)

            # If no context, immediately respond with the required fallback message
            if not context_str.strip():
                # Send structured error when no context found
                await websocket.send_text(json.dumps({"type": "error", "error": "empty_context", "reason": "No relevant documents retrieved"}))
                await websocket.send_text(json.dumps({"type": "done"}))
                # Save history with user question and assistant fallback
                try:
                    cache_service.add_to_history(session_id, "user", query)
                    cache_service.add_to_history(session_id, "assistant", "Answer not found in uploaded documents.")
                except Exception as e:
                    logger.error(f"History save failed: {e}")
                continue

            full_response = ""
            import time
            start_total = time.time()
            async for chunk in llm_service.generate_response(
                query=query,
                context=context_str,
                role=role,
                chat_history=history
            ):
                full_response += chunk
                await websocket.send_text(json.dumps({"type": "chunk", "content": chunk}))
            total_time = time.time() - start_total
            if settings.DEBUG_RAG:
                logger.info(f"LLM generation total time (ws): {total_time:.3f}s")
            try:
                from app.services.metrics import record_generation
                record_generation(total_time)
            except Exception:
                pass
            
            # 4. Finalize & Save History
            await websocket.send_text(json.dumps({"type": "done"}))
            try:
                cache_service.add_to_history(session_id, "user", query)
                cache_service.add_to_history(session_id, "assistant", full_response)
            except Exception as e:
                logger.error(f"History save failed: {e}")
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket session {session_id} disconnected.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()
