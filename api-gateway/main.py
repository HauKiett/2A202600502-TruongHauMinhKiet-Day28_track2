# api-gateway/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from prometheus_fastapi_instrumentator import Instrumentator
import httpx
import os
import time
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api-gateway")

app = FastAPI(title="AI Platform API Gateway")
Instrumentator().instrument(app).expose(app)

VLLM_URL = os.environ.get("VLLM_URL", "")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4")


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    embedding: list[float] | None = None


@app.post("/api/v1/chat")
async def chat(req: ChatRequest):
    start = time.time()
    context: list = []

    embedding = req.embedding or [0.0] * 384
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            search_resp = await client.post(
                f"{QDRANT_URL}/collections/documents/points/search",
                json={"vector": embedding, "limit": 3},
            )
        if search_resp.status_code == 200:
            context = search_resp.json().get("result", []) or []
        else:
            log.warning("qdrant non-200: %s", search_resp.status_code)
    except Exception as exc:
        log.warning("qdrant unreachable, degrading: %s", exc)

    if not VLLM_URL:
        latency = (time.time() - start) * 1000
        return {
            "answer": f"[degraded] No VLLM_URL configured. Echo query: {req.query}",
            "latency_ms": round(latency, 2),
            "model": "fallback-echo",
            "context_hits": len(context),
            "degraded": True,
        }

    prompt = f"Context: {context}\n\nQuery: {req.query}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            llm_resp = await client.post(
                f"{VLLM_URL}/v1/chat/completions",
                json={
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        llm_resp.raise_for_status()
        result = llm_resp.json()
        latency = (time.time() - start) * 1000
        return {
            "answer": result["choices"][0]["message"]["content"],
            "latency_ms": round(latency, 2),
            "model": result.get("model", MODEL_NAME),
            "context_hits": len(context),
            "degraded": False,
        }
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="LLM upstream timeout")
    except Exception as exc:
        log.error("LLM upstream error: %s", exc)
        latency = (time.time() - start) * 1000
        return {
            "answer": f"[degraded] LLM upstream error. Echo query: {req.query}",
            "latency_ms": round(latency, 2),
            "model": "fallback-echo",
            "context_hits": len(context),
            "degraded": True,
        }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    checks = {"qdrant": False, "vllm": bool(VLLM_URL)}
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get(f"{QDRANT_URL}/healthz")
            checks["qdrant"] = r.status_code == 200
    except Exception:
        pass
    return {"status": "ok" if all(checks.values()) else "degraded", "checks": checks}
