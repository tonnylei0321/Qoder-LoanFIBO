-- ============================================================
-- SaaS Agent Service - DDL Migration
-- 创建时间: 2026-04-20
-- 用途: Agent服务的4张核心表
-- 依赖: fi_applicant_org 表已存在
-- ============================================================

-- 1. Agent凭证表
CREATE TABLE IF NOT EXISTS agent_credential (
    client_id       VARCHAR(64)     NOT NULL,
    client_secret_hash VARCHAR(128) NOT NULL,
    org_id          UUID            NOT NULL REFERENCES fi_applicant_org(id),
    datasource      VARCHAR(64)     NOT NULL,
    created_at      TIMESTAMPTZ     DEFAULT now(),
    revoked_at      TIMESTAMPTZ     NULL,

    CONSTRAINT pk_agent_credential PRIMARY KEY (client_id)
);

CREATE INDEX IF NOT EXISTS idx_credential_org_datasource
    ON agent_credential (org_id, datasource);

-- 2. Agent版本表
CREATE TABLE IF NOT EXISTS agent_version (
    id              UUID            NOT NULL DEFAULT gen_random_uuid(),
    version         VARCHAR(32)     NOT NULL,
    platform        VARCHAR(16)     NOT NULL,
    download_url    VARCHAR(512)    NOT NULL,
    min_version     VARCHAR(32)     DEFAULT '1.0.0',
    created_at      TIMESTAMPTZ     DEFAULT now(),

    CONSTRAINT pk_agent_version PRIMARY KEY (id)
);

-- 3. Agent审计日志表
CREATE TABLE IF NOT EXISTS agent_audit_log (
    id              UUID            NOT NULL DEFAULT gen_random_uuid(),
    org_id          UUID            NOT NULL REFERENCES fi_applicant_org(id),
    action          VARCHAR(64)     NOT NULL,
    operator        VARCHAR(128)    NOT NULL,
    ip              VARCHAR(64)     NULL,
    detail          JSONB           NULL,
    created_at      TIMESTAMPTZ     DEFAULT now(),

    CONSTRAINT pk_agent_audit_log PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_audit_org_created
    ON agent_audit_log (org_id, created_at);

-- 4. Agent链路追踪表
CREATE TABLE IF NOT EXISTS agent_trace (
    trace_id        VARCHAR(64)     NOT NULL,
    org_id          UUID            NOT NULL REFERENCES fi_applicant_org(id),
    datasource      VARCHAR(64)     NULL,
    action          VARCHAR(64)     NULL,
    status          VARCHAR(32)     NULL,
    spans           JSONB           NULL,
    duration_ms     INTEGER         NULL,
    created_at      TIMESTAMPTZ     DEFAULT now(),

    CONSTRAINT pk_agent_trace PRIMARY KEY (trace_id)
);

CREATE INDEX IF NOT EXISTS idx_trace_org_created
    ON agent_trace (org_id, created_at);

CREATE INDEX IF NOT EXISTS idx_trace_spans
    ON agent_trace USING gin (spans);
