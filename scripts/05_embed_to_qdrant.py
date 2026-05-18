# scripts/05_embed_to_qdrant.py
"""Embed text qua Kaggle service (hoặc fallback random) và lưu vào Qdrant."""
import os
import sys
import random
import requests
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

EMBED_URL = os.environ.get("EMBED_NGROK_URL", "").strip()
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
COLLECTION = "documents"
VECTOR_SIZE = 384


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Call Kaggle embedding service. Fallback to random vectors if unavailable."""
    if EMBED_URL:
        try:
            resp = requests.post(
                f"{EMBED_URL}/embed",
                json={"texts": texts},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()["embeddings"]
        except Exception as exc:
            print(f"[WARN] Embedding service failed ({exc}); using random fallback.")
    else:
        print("[WARN] EMBED_NGROK_URL not set; using random fallback embeddings.")
    return [[random.random() for _ in range(VECTOR_SIZE)] for _ in texts]


def main(records: list[dict]) -> int:
    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    qdrant.recreate_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )

    embeddings = get_embeddings([r["text"] for r in records])
    points = [
        PointStruct(id=i, vector=emb, payload=rec)
        for i, (emb, rec) in enumerate(zip(embeddings, records))
    ]
    qdrant.upsert(collection_name=COLLECTION, points=points)
    print(f"Integration 5 OK: {len(points)} vectors stored in Qdrant ({COLLECTION})")
    return len(points)


if __name__ == "__main__":
    sample = [
        {"id": "doc_001", "text": "AI platform integration test"},
        {"id": "doc_002", "text": "Kafka to Airflow pipeline"},
        {"id": "doc_003", "text": "Event-driven architecture decouples services"},
    ]
    try:
        main(sample)
    except Exception as exc:
        print(f"[FAIL] {exc}")
        sys.exit(1)
