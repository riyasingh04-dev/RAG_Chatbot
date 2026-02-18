import threading
from typing import Dict, Any

_lock = threading.Lock()
_metrics: Dict[str, Any] = {
    "last_retrieval_time": None,
    "last_retrieval_count": 0,
    "last_retrieval_sources": [],
    "retrieval_samples": [],
    "last_rerank_time": None,
    "generation_samples": [],
    "last_generation_time": None,
}


def record_retrieval(latency: float, count: int, sources: list):
    with _lock:
        _metrics["last_retrieval_time"] = latency
        _metrics["last_retrieval_count"] = count
        _metrics["last_retrieval_sources"] = sources
        _metrics["retrieval_samples"].append({"latency": latency, "count": count})
        # keep only the last 50 samples
        if len(_metrics["retrieval_samples"]) > 50:
            _metrics["retrieval_samples"] = _metrics["retrieval_samples"][-50:]


def record_rerank(latency: float):
    with _lock:
        _metrics["last_rerank_time"] = latency


def record_generation(latency: float):
    with _lock:
        _metrics["last_generation_time"] = latency
        _metrics["generation_samples"].append({"latency": latency})
        if len(_metrics["generation_samples"]) > 100:
            _metrics["generation_samples"] = _metrics["generation_samples"][-100:]


def get_metrics() -> Dict[str, Any]:
    with _lock:
        # compute average retrieval latency from samples
        samples = list(_metrics["retrieval_samples"])
    avg = None
    if samples:
        avg = sum(s["latency"] for s in samples) / len(samples)
    gen_samples = list(_metrics.get("generation_samples", []))
    avg_gen = None
    if gen_samples:
        avg_gen = sum(s["latency"] for s in gen_samples) / len(gen_samples)

    data = {
        "last_retrieval_time": _metrics.get("last_retrieval_time"),
        "last_retrieval_count": _metrics.get("last_retrieval_count"),
        "last_retrieval_sources": _metrics.get("last_retrieval_sources"),
        "avg_retrieval_time": avg,
        "last_rerank_time": _metrics.get("last_rerank_time"),
        "avg_generation_time": avg_gen,
        "last_generation_time": _metrics.get("last_generation_time"),
    }
    return data
