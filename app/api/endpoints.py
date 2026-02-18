import os
import shutil
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from app.models.schemas import ChatRequest, UploadResponse
from app.services.document_processor import document_processor
from app.services.faiss_service import faiss_service
from app.services.rag_pipeline import rag_retriever
from app.services.llm_service import llm_service
from app.services.metrics import get_metrics, record_generation
from app.services.health_utils import collect_system_metrics
from app.core.config import settings

router = APIRouter()

@router.post("/upload", response_model=UploadResponse)
async def upload_documents(files: List[UploadFile] = File(...)):
    uploaded_files = []
    for file in files:
        file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        uploaded_files.append(file_path)
    
    logger.info(f"Uploaded {len(uploaded_files)} files: {uploaded_files}")
    
    # Process and Index
    chunks = document_processor.process_documents(uploaded_files)
    if chunks:
        faiss_service.add_documents(chunks)
        return UploadResponse(message="Documents indexed successfully", files=[f.filename for f in files])
    else:
        raise HTTPException(status_code=400, detail="Failed to process documents.")

@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    # Retrieve Documents with hybrid search and reranking (so we can log counts/previews)
    docs = rag_retriever.retrieve(request.message)

    # Debug: list retrieved sources
    try:
        retrieved_sources = [d.metadata.get("file_name") or d.metadata.get("source") for d in docs]
        logger.debug(f"Retrieved document sources: {retrieved_sources}")
    except Exception:
        logger.debug("Could not enumerate retrieved document sources")

    # Debug logs required: query, retrieved chunks count, first 200 chars of context
    logger.debug(f"Query: {request.message}")
    logger.debug(f"Retrieved chunks: {len(docs)}")
    if docs:
        top_preview = docs[0].page_content[:200].replace('\n', ' ')
        logger.debug(f"Top chunk preview (200 chars): {top_preview}")

    # Build context string for LLM
    context = ""
    if docs:
        parts = []
        for doc in docs:
            parts.append(doc.page_content.replace("\n", " ").strip())
        context = "\n\n---\n\n".join(parts)

    # If no context, immediately return the required fallback message
    if not context.strip():
        # Structured error for empty context
        def error_stream():
            return ("{\"error\": \"empty_context\", \"reason\": \"No relevant documents retrieved\"}",)
        return StreamingResponse(error_stream(), media_type="application/json")

    # Generate (Streaming)
    async def stream_generator():
        import time
        start_total = time.time()
        # We don't measure LLM internal time precisely, but measure overall generation
        async for chunk in llm_service.generate_response(
            query=request.message,
            context=context,
            role=request.role,
            chat_history=request.chat_history
        ):
            yield chunk
        total_time = time.time() - start_total
        logger.info(f"LLM generation total time: {total_time:.3f}s")
        try:
            record_generation(total_time)
        except Exception:
            pass

    return StreamingResponse(stream_generator(), media_type="text/plain")


@router.get('/rag-health')
def rag_health():
    """Lightweight health endpoint returning retrieval and system diagnostics."""
    # Metrics
    metrics = get_metrics()

    # Index size
    try:
        index_size = 0
        if faiss_service.vector_db and hasattr(faiss_service.vector_db, 'docstore'):
            index_size = len(list(faiss_service.vector_db.docstore._dict.values()))
    except Exception:
        index_size = None

    # Vector store type
    vector_store_type = 'FAISS' if faiss_service.vector_db else 'None'

    # retriever_k and bm25_k
    try:
        bm25_k = faiss_service.bm25_retriever.k if faiss_service.bm25_retriever else None
    except Exception:
        bm25_k = None
    # Our FAISS retriever default used in code is 50; attempt to reflect that as best-effort
    retriever_k = 50

    system = collect_system_metrics()

    response = {
        "status": "ok" if faiss_service.vector_db else "no_index",
        "index_size": index_size or 0,
        "vector_store_type": vector_store_type,
        "embedding_model_name": settings.EMBEDDING_MODEL,
        "avg_retrieval_time_ms": int((metrics.get('avg_retrieval_time') or 0) * 1000),
        "avg_rerank_time_ms": int((metrics.get('last_rerank_time') or 0) * 1000),
        "avg_generation_time_ms": int((metrics.get('avg_generation_time') or 0) * 1000),
        "last_query_sources": metrics.get('last_retrieval_sources') or [],
        "last_docs_retrieved_count": metrics.get('last_retrieval_count') or 0,
        "retriever_k": retriever_k,
        "bm25_k": bm25_k,
        "debug_mode": bool(settings.DEBUG_RAG),
        "system_memory_usage_mb": system.get('system_memory_usage_mb'),
        "system_cpu_usage_percent": system.get('system_cpu_usage_percent'),
        "uptime_seconds": system.get('uptime_seconds'),
    }

    return response
