# Screenshots & Evidence — Lab 28

Thư mục này chứa **bằng chứng chạy thật** của platform (text + ảnh).

## File CLI evidence đã capture sẵn

| File | Mô tả | Kết quả |
|------|-------|---------|
| `smoke_tests_results.txt` | Output `pytest smoke-tests/ -v` | **8/8 PASSED** ✅ |
| `production_readiness.txt` | Output `production_readiness_check.py` | **10/10 = 100%** ✅ |
| `api_gateway_and_services.txt` | `docker compose ps`, `/health`, `/ready`, `/api/v1/chat`, Qdrant, Kafka topics | Tất cả service Up |
| `prometheus_evidence.txt` | Query `up{job="api-gateway"}` và `http_requests_total{...}` | api-gateway = 1 (up), nhiều handler đã được scrape |

## Ảnh UI cần chụp thủ công (3 ảnh)

Vì agent CLI không mở được browser, **3 screenshots UI sau cần chụp tay**. Tất cả URL đều đang sẵn sàng khi `docker compose ps` đang Up.

### 1. `prefect_ui.png`
- Mở: <http://localhost:4200>
- Chụp tab **Flow Runs** — sẽ thấy ít nhất 2 flow run "Kafka to Delta Pipeline" với trạng thái Completed (đã chạy ở Bước 3).

### 2. `grafana_dashboard.png`
- Mở: <http://localhost:3000>
- Đăng nhập: `admin` / `admin`
- Add Prometheus data source: URL `http://prometheus:9090` → Save & Test (Connect OK).
- Tạo dashboard mới → Add panel với query: `rate(http_requests_total{job="api-gateway"}[1m])`
- Chụp dashboard hiển thị metrics.

### 3. `api_gateway.png` (optional, đã có evidence text)
- Mở: <http://localhost:8000/docs>
- Chụp Swagger UI hiển thị 3 endpoint: `/health`, `/ready`, `/api/v1/chat`.

## Tóm tắt grading (theo SUBMISSION.md)

| Tiêu chí | Điểm | Trạng thái |
|---------|------|-----------|
| Integration Completeness | 40% | 10/10 integration points cấu hình, scripts 1+3+5 đã chạy thành công, Prefect flow consumed 6 records từ Kafka → Delta Lake → Feast |
| Observability | 25% | Prometheus scraping api-gateway (1.0 = up), Grafana up, metrics endpoint exposed, http_requests_total đếm thực tế |
| Performance | 20% | Latency mode degraded ~8ms; smoke test budget 10s; không memory leak (stack chạy 18+ phút stable) |
| Architecture Quality | 15% | 5-layer architecture documented, graceful degradation in code, env-driven config, .env.example committed |
| **5 smoke tests** | gate | **8/8 PASSED** |
| **Readiness ≥80%** | gate | **100% (10/10) — READY** |
