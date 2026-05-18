# smoke-tests/test_e2e.py
"""5 smoke tests covering critical user journeys."""
import json
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
PROM_URL = os.environ.get("PROM_URL", "http://localhost:9090")
GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://localhost:3000")
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:29092")
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")

# Latency budget (ms). vLLM via ngrok can be slow; default is generous.
LATENCY_BUDGET_MS = int(os.environ.get("LATENCY_BUDGET_MS", "10000"))


# ── Test 1: Happy Path ──────────────────────────────────────────
class TestHappyPath:
    def test_full_inference_returns_200(self):
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat",
            json={"query": "What is platform engineering?", "embedding": [0.1] * 384},
            timeout=60,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "answer" in data
        assert len(data["answer"]) > 0
        assert data["latency_ms"] < LATENCY_BUDGET_MS

    def test_health_check_passes(self):
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ── Test 2: Data Ingestion Journey ──────────────────────────────
class TestDataIngestion:
    def test_kafka_ingest_and_qdrant_store(self):
        from kafka import KafkaProducer

        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode(),
        )
        producer.send("data.raw", {"id": "smoke_001", "text": "smoke test document"})
        producer.flush()
        producer.close()

        # Wait a moment for any consumer to pick up; this test only checks Qdrant
        # has at least one collection populated by the embedding pipeline.
        time.sleep(2)

        resp = requests.get(f"{QDRANT_URL}/collections/documents", timeout=5)
        assert resp.status_code == 200, resp.text
        count = resp.json()["result"]["points_count"]
        assert count > 0, "Qdrant 'documents' collection is empty — run scripts/05_embed_to_qdrant.py first"


# ── Test 3: Observability Journey ───────────────────────────────
class TestObservability:
    def test_prometheus_scrapes_api_gateway(self):
        resp = requests.get(
            f"{PROM_URL}/api/v1/query",
            params={"query": 'up{job="api-gateway"}'},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()["data"]["result"]
        assert len(result) > 0, "No api-gateway target in Prometheus"
        assert result[0]["value"][1] == "1", "api-gateway is reported as down by Prometheus"

    def test_grafana_dashboard_accessible(self):
        resp = requests.get(f"{GRAFANA_URL}/api/health", auth=("admin", "admin"), timeout=5)
        assert resp.status_code == 200


# ── Test 4: Error Handling & Failure Path ───────────────────────
class TestFailurePath:
    def test_invalid_request_returns_422(self):
        resp = requests.post(f"{BASE_URL}/api/v1/chat", json={}, timeout=5)
        assert resp.status_code in (400, 422), resp.text

    def test_timeout_handled_gracefully(self):
        try:
            requests.post(
                f"{BASE_URL}/api/v1/chat",
                json={"query": "test", "embedding": [0.1] * 384},
                timeout=0.001,
            )
        except requests.exceptions.Timeout:
            pass  # expected
        # Service must still be healthy after a client-side timeout
        health = requests.get(f"{BASE_URL}/health", timeout=5)
        assert health.status_code == 200


# ── Test 5: Feature Store Journey ───────────────────────────────
class TestFeatureStore:
    def test_feast_redis_has_features(self):
        import redis

        r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
        keys = r.keys("feature:*")
        assert len(keys) > 0, "No 'feature:*' keys in Redis — run scripts/03_delta_to_feast.py first"
