import os
import time
from app.services.document_processor import document_processor
from app.services.faiss_service import faiss_service
from app.services.rag_pipeline import rag_retriever
from loguru import logger


def index_files(file_paths):
    logger.info(f"Indexing files: {file_paths}")
    chunks = document_processor.process_documents(file_paths)
    logger.info(f"Created {len(chunks)} chunks. Adding to FAISS...")
    faiss_service.add_documents(chunks)
    logger.info("Indexing complete.")


def run_query(query):
    logger.info(f"\n--- Running query: {query}")
    docs = rag_retriever.retrieve(query)
    logger.info(f"Retrieved {len(docs)} final documents from RagRetriever")

    # Print retrieval trace: show metadata sources and previews
    for i, d in enumerate(docs, 1):
        src = d.metadata.get("file_name") or d.metadata.get("source")
        preview = d.page_content[:300].replace('\n', ' ')
        logger.info(f"{i}. Source: {src} | Preview: {preview[:200]}...")

    # Also show full context assembly length
    context = "\n\n---\n\n".join([d.page_content.replace("\n", " ").strip() for d in docs])
    logger.info(f"Assembled context length: {len(context)} characters\n")
    # Return tuple for checks
    return docs, context


def main():
    # Prepare sample files
    base_dir = os.getcwd()
    sample_dir = os.path.join(base_dir, "tmp_samples")
    os.makedirs(sample_dir, exist_ok=True)

    # Test case 1: CSV
    csv_file = os.path.join("data", "uploads", "cars.csv")
    if not os.path.exists(csv_file):
        csv_file = os.path.join(sample_dir, "sample.csv")
        with open(csv_file, "w", encoding="utf-8") as f:
            f.write("model,year,owner\nTestCar,2020,Alice\n")

    # Test case 2: ipynb
    ipynb_file = os.path.join("data", "uploads", "Mini_GPT_From_Scratch.ipynb")
    if not os.path.exists(ipynb_file):
        # fallback: create a tiny ipynb-like text file
        ipynb_file = os.path.join(sample_dir, "sample.ipynb")
        with open(ipynb_file, "w", encoding="utf-8") as f:
            f.write("{\"cells\": [{\"cell_type\": \"markdown\", \"source\": [\"This is a sample notebook about Riya's experience.\"]}]}")

    # Test case 3: two resumes -> simulate with two text files
    resume1 = os.path.join(sample_dir, "resume_alice.txt")
    resume2 = os.path.join(sample_dir, "resume_bob.txt")
    with open(resume1, "w", encoding="utf-8") as f:
        f.write("Alice\nExperience: 5 years in ML. Skills: Python, PyTorch. Education: MSc.")
    with open(resume2, "w", encoding="utf-8") as f:
        f.write("Bob\nExperience: 3 years in data engineering. Skills: SQL, Spark. Education: BSc.")

    # Index and run tests sequentially (note: this will add to the global FAISS index)
    logger.info("\n=== Test 1: CSV retrieval ===")
    index_files([csv_file])
    docs1, ctx1 = run_query("Who owns TestCar?")
    if len(docs1) < 3 or not ctx1.strip():
        logger.error("Validation failure: CSV retrieval returned insufficient documents or empty context")
        raise SystemExit(1)

    logger.info("\n=== Test 2: Notebook retrieval ===")
    index_files([ipynb_file])
    docs2, ctx2 = run_query("Riya experience")
    if len(docs2) < 3 or not ctx2.strip():
        logger.error("Validation failure: Notebook retrieval returned insufficient documents or empty context")
        raise SystemExit(1)

    logger.info("\n=== Test 3: Multi-document comparison retrieval ===")
    index_files([resume1, resume2])
    docs3, ctx3 = run_query("Compare Alice and Bob experience")
    # Ensure both resume files are present in retrieved sources
    sources = [d.metadata.get("file_name") or d.metadata.get("source") for d in docs3]
    found1 = any("resume_alice" in str(s).lower() or "alice" in str(s).lower() for s in sources)
    found2 = any("resume_bob" in str(s).lower() or "bob" in str(s).lower() for s in sources)
    if len(docs3) < 3 or not ctx3.strip() or not (found1 and found2):
        logger.error("Validation failure: Multi-document comparison did not retrieve both files or returned insufficient documents/context")
        raise SystemExit(1)

    logger.info("All validation tests passed")
    return 0


if __name__ == '__main__':
    main()
