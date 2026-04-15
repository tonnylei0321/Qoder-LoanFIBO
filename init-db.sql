-- 启用 pg_trgm 扩展用于模糊匹配
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- DDL 解析结果
CREATE TABLE IF NOT EXISTS table_registry (
    id              BIGSERIAL PRIMARY KEY,
    database_name   VARCHAR(128) NOT NULL,
    table_name      VARCHAR(256) NOT NULL,
    raw_ddl         TEXT NOT NULL,
    parsed_fields   JSONB NOT NULL DEFAULT '[]',
    mapping_status  VARCHAR(32) NOT NULL DEFAULT 'pending',
    -- pending / mapped / unmappable / llm_parse_error
    parse_error     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (database_name, table_name)
);
CREATE INDEX IF NOT EXISTS idx_table_registry_status ON table_registry(mapping_status);
CREATE INDEX IF NOT EXISTS idx_table_registry_db ON table_registry(database_name);

-- 本体类索引
CREATE TABLE IF NOT EXISTS ontology_class_index (
    id              BIGSERIAL PRIMARY KEY,
    class_uri       VARCHAR(512) NOT NULL UNIQUE,
    label_zh        VARCHAR(256),
    label_en        VARCHAR(256),
    comment_zh      TEXT,
    comment_en      TEXT,
    parent_uri      VARCHAR(512),
    namespace       VARCHAR(256),
    search_vector   TSVECTOR,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_class_search ON ontology_class_index USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_class_namespace ON ontology_class_index(namespace);

-- 本体属性索引
CREATE TABLE IF NOT EXISTS ontology_property_index (
    id              BIGSERIAL PRIMARY KEY,
    property_uri    VARCHAR(512) NOT NULL UNIQUE,
    property_type   VARCHAR(32) NOT NULL,
    label_zh        VARCHAR(256),
    label_en        VARCHAR(256),
    domain_uri      VARCHAR(512),
    range_uri       VARCHAR(512),
    namespace       VARCHAR(256),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_property_domain ON ontology_property_index(domain_uri);

-- TTL 索引版本管理
CREATE TABLE IF NOT EXISTS ontology_index_meta (
    id              BIGSERIAL PRIMARY KEY,
    file_name       VARCHAR(256) NOT NULL,
    file_md5        VARCHAR(64) NOT NULL,
    class_count     INTEGER NOT NULL DEFAULT 0,
    property_count  INTEGER NOT NULL DEFAULT 0,
    built_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

-- Pipeline 任务
CREATE TABLE IF NOT EXISTS mapping_job (
    id              BIGSERIAL PRIMARY KEY,
    job_name        VARCHAR(256),
    scope_databases JSONB,
    status          VARCHAR(32) NOT NULL DEFAULT 'pending',
    phase           VARCHAR(32) NOT NULL DEFAULT 'parse_ddl',
    total_tables    INTEGER NOT NULL DEFAULT 0,
    processed_tables INTEGER NOT NULL DEFAULT 0,
    mapped_count    INTEGER NOT NULL DEFAULT 0,
    unmappable_count INTEGER NOT NULL DEFAULT 0,
    approved_count  INTEGER NOT NULL DEFAULT 0,
    needs_revision_count INTEGER NOT NULL DEFAULT 0,
    manual_review_count  INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    report          JSONB,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE
);

-- 表级映射结果
CREATE TABLE IF NOT EXISTS table_mapping (
    id              BIGSERIAL PRIMARY KEY,
    job_id          BIGINT REFERENCES mapping_job(id),
    database_name   VARCHAR(128) NOT NULL,
    table_name      VARCHAR(256) NOT NULL,
    fibo_class_uri  VARCHAR(512),
    confidence_level VARCHAR(16),
    mapping_reason  TEXT,
    mapping_status  VARCHAR(32) NOT NULL DEFAULT 'pending',
    review_status   VARCHAR(32) NOT NULL DEFAULT 'pending',
    revision_count  INTEGER NOT NULL DEFAULT 0,
    model_used      VARCHAR(64),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by      VARCHAR(128),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (job_id, database_name, table_name)
);
CREATE INDEX IF NOT EXISTS idx_table_mapping_review ON table_mapping(review_status);
CREATE INDEX IF NOT EXISTS idx_table_mapping_confidence ON table_mapping(confidence_level);

-- 字段级映射结果
CREATE TABLE IF NOT EXISTS field_mapping (
    id              BIGSERIAL PRIMARY KEY,
    table_mapping_id BIGINT NOT NULL REFERENCES table_mapping(id),
    field_name      VARCHAR(256) NOT NULL,
    field_type      VARCHAR(128),
    fibo_property_uri VARCHAR(512),
    confidence_level VARCHAR(16),
    mapping_reason  TEXT,
    proj_ext_uri    VARCHAR(512),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by      VARCHAR(128),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (table_mapping_id, field_name),
    CONSTRAINT chk_field_has_mapping CHECK (
        fibo_property_uri IS NOT NULL OR proj_ext_uri IS NOT NULL OR confidence_level = 'UNRESOLVED'
    )
);

-- 检核意见
CREATE TABLE IF NOT EXISTS mapping_review (
    id              BIGSERIAL PRIMARY KEY,
    table_mapping_id BIGINT NOT NULL REFERENCES table_mapping(id),
    field_mapping_id BIGINT REFERENCES field_mapping(id),
    review_round    INTEGER NOT NULL DEFAULT 0,
    issue_type      VARCHAR(32) NOT NULL,
    severity        VARCHAR(4) NOT NULL,
    is_must_fix     BOOLEAN NOT NULL DEFAULT FALSE,
    issue_description TEXT NOT NULL,
    suggested_fix   TEXT,
    is_resolved     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_review_table_mapping ON mapping_review(table_mapping_id);
CREATE INDEX IF NOT EXISTS idx_review_severity ON mapping_review(severity);
CREATE INDEX IF NOT EXISTS idx_review_must_fix ON mapping_review(table_mapping_id, is_must_fix) WHERE is_must_fix = TRUE;

-- 修订历史
CREATE TABLE IF NOT EXISTS mapping_revision_log (
    id                  BIGSERIAL PRIMARY KEY,
    table_mapping_id    BIGINT NOT NULL REFERENCES table_mapping(id),
    revision_round      INTEGER NOT NULL,
    model_used          VARCHAR(64),
    prompt_tokens       INTEGER NOT NULL DEFAULT 0,
    completion_tokens   INTEGER NOT NULL DEFAULT 0,
    prev_fibo_class_uri VARCHAR(512),
    prev_confidence     VARCHAR(16),
    new_fibo_class_uri  VARCHAR(512),
    new_confidence      VARCHAR(16),
    field_changes       JSONB,
    resolved_review_ids JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_revision_log_table ON mapping_revision_log(table_mapping_id);

-- LLM 调用日志
CREATE TABLE IF NOT EXISTS llm_call_log (
    id              BIGSERIAL PRIMARY KEY,
    job_id          BIGINT REFERENCES mapping_job(id),
    table_mapping_id BIGINT REFERENCES table_mapping(id),
    call_type       VARCHAR(32) NOT NULL,
    model_name      VARCHAR(64) NOT NULL,
    prompt_tokens   INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    latency_ms      INTEGER NOT NULL DEFAULT 0,
    is_fallback     BOOLEAN NOT NULL DEFAULT FALSE,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
