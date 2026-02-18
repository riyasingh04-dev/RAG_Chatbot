import os
import time
from loguru import logger
from app.services.document_processor import document_processor
from app.services.faiss_service import faiss_service
from app.services.rag_pipeline import rag_retriever


def index_and_query(files, query):
    start = time.time()
    chunks = document_processor.process_documents(files)
    faiss_service.add_documents(chunks)
    idx_time = time.time() - start
    logger.info(f"Indexed {len(chunks)} chunks from {len(files)} files in {idx_time:.3f}s")

    # Run retrieval and measure times
    start_r = time.time()
    docs = rag_retriever.retrieve(query)
    retrieval_time = time.time() - start_r

    logger.info(f"Query: {query}")
    logger.info(f"Retrieved {len(docs)} docs (retrieval_time={retrieval_time:.3f}s)")
    for i, d in enumerate(docs, 1):
        src = d.metadata.get('file_name') or d.metadata.get('source')
        preview = d.page_content[:200].replace('\n', ' ')
        logger.info(f"{i}. {src} | {preview}")

    return docs


def run_tests():
    base = os.getcwd()
    sample_dir = os.path.join(base, 'tmp_samples')
    os.makedirs(sample_dir, exist_ok=True)

    # Prepare 10 small text files
    files = []
    for i in range(10):
        p = os.path.join(sample_dir, f'sample_{i}.txt')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(f"Document {i}\nThis is a test file number {i} about data and ML.")
        files.append(p)

    # Test 1: 10+ files upload
    logger.info("=== Stress Test: 10+ files ===")
    docs = index_and_query(files, "Tell me about data and ML")

    # Test 2: same file twice
    logger.info("=== Stress Test: duplicate file upload ===")
    dup = [files[0], files[0]]
    docs2 = index_and_query(dup, "Document 0")

    # Test 3: query referring to multiple docs
    logger.info("=== Stress Test: multi-doc query ===")
    docs3 = index_and_query([files[1], files[2], files[3]], "test file number 2")

    # Test 4: query referring to non-existing info
    logger.info("=== Stress Test: non-existing info ===")
    docs4 = index_and_query([files[4]], "Who is the president of Mars?")

    # Summarize
    logger.info("Stress tests complete")


if __name__ == '__main__':
    run_tests()
