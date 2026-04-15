## Spec: Pipeline API Route Test Coverage

### Capability: api-pipeline-route-coverage

### Overview

`tests/unit/api/test_pipeline.py` 提供对 `backend/app/api/v1/pipeline.py` 全部路由的单元级测试覆盖，通过 `dependency_overrides` 和 mock patch 实现零 DB 依赖。

### Test Coverage

| Test | Route | Method | Assertions |
|------|-------|--------|-----------|
| `test_health_check` | `/health` | GET | 200, `status=healthy` |
| `test_root_endpoint` | `/` | GET | 200, `api_prefix=/api/v1` |
| `test_create_job_success` | `/api/v1/pipeline/jobs` | POST | 200, `data.job_id` exists |
| `test_create_job_defaults` | `/api/v1/pipeline/jobs` | POST | 200, empty body accepted |
| `test_create_job_invalid_concurrency_zero` | `/api/v1/pipeline/jobs` | POST | 422, concurrency=0 |
| `test_create_job_invalid_concurrency_over_max` | `/api/v1/pipeline/jobs` | POST | 422, concurrency=21 |
| `test_get_job` | `/api/v1/pipeline/jobs/42` | GET | 200, `data.job_id=42` |
| `test_get_job_string_id_returns_422` | `/api/v1/pipeline/jobs/abc` | GET | 422, invalid path param |
| `test_pause_job` | `/api/v1/pipeline/jobs/1/pause` | POST | 200, `code=0` |
| `test_resume_job` | `/api/v1/pipeline/jobs/1/resume` | POST | 200, `code=0` |
| `test_query_mappings_default` | `/api/v1/pipeline/mappings` | GET | 200, `data.items` is list |
| `test_query_mappings_pagination` | `/api/v1/pipeline/mappings?page=2` | GET | 200, `data.page=2` |
| `test_query_mappings_with_filters` | `/api/v1/pipeline/mappings?mapping_status=mapped` | GET | 200 |
| `test_get_mapping_detail` | `/api/v1/pipeline/mappings/1` | GET | 200, `code=0` |
| `test_update_mapping` | `/api/v1/pipeline/mappings/1` | PATCH | 200, `code=0` |
| `test_get_stats` | `/api/v1/pipeline/stats` | GET | 200, `data.total_tables` exists |
| `test_trigger_ttl_index` | `/api/v1/pipeline/ttl/index` | POST | 200, `code=0` |
| `test_get_ttl_index_status` | `/api/v1/pipeline/ttl/index/status` | GET | 200, `data.status` exists |

### Files

- `tests/unit/api/__init__.py` — 空文件，标记为 Python 包
- `tests/unit/api/test_pipeline.py` — 18 个测试
