# scripts/09_verify_observability.py
"""Kiểm tra Prometheus scraping và (optional) LangSmith traces."""
import os
import sys
import requests


def check_prometheus() -> bool:
    try:
        resp = requests.get(
            "http://localhost:9090/api/v1/query",
            params={"query": 'up{job="api-gateway"}'},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        assert data["status"] == "success"
        result = data["data"]["result"]
        if not result:
            print("[WARN] Integration 9: Prometheus is up but no api-gateway target scraped yet")
            return False
        print(f"[PASS] Integration 9: Prometheus scraping api-gateway (samples={len(result)})")
        return True
    except Exception as exc:
        print(f"[FAIL] Integration 9: Prometheus check failed: {exc}")
        return False


def check_langsmith() -> bool:
    api_key = os.environ.get("LANGCHAIN_API_KEY", "").strip()
    project = os.environ.get("LANGCHAIN_PROJECT", "lab28-platform")
    if not api_key:
        print("[SKIP] Integration 10: LANGCHAIN_API_KEY not set — skipping LangSmith check")
        return True
    try:
        from langsmith import Client
        client = Client(api_key=api_key)
        runs = list(client.list_runs(project_name=project, limit=1))
        if not runs:
            print(f"[WARN] Integration 10: LangSmith project '{project}' has no runs yet")
            return False
        print(f"[PASS] Integration 10: LangSmith traces visible (project={project})")
        return True
    except Exception as exc:
        print(f"[FAIL] Integration 10: LangSmith check failed: {exc}")
        return False


if __name__ == "__main__":
    ok_prom = check_prometheus()
    ok_ls = check_langsmith()
    sys.exit(0 if (ok_prom and ok_ls) else 1)
