-- ============================================================
-- AML Monitoring System — Initial Schema
-- Migration: 001_initial_schema.sql
-- ============================================================

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── ENUM Types ────────────────────────────────────────────────────────────────
CREATE TYPE risk_level      AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
CREATE TYPE kyc_level       AS ENUM ('Full', 'Partial', 'None');
CREATE TYPE account_type    AS ENUM ('Individual', 'Business', 'Joint', 'NRI', 'Offshore');
CREATE TYPE txn_status      AS ENUM ('Pending', 'Completed', 'Reversed', 'Blocked');
CREATE TYPE alert_status    AS ENUM ('Open', 'Under Review', 'Escalated', 'Closed-SAR Filed', 'Closed-False Positive', 'Closed-No Action');
CREATE TYPE alert_severity  AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');

-- ── Users ─────────────────────────────────────────────────────────────────────
CREATE TABLE users (
    user_id                         VARCHAR(20)  PRIMARY KEY,
    account_type                    account_type NOT NULL DEFAULT 'Individual',
    country                         CHAR(2)      NOT NULL,
    occupation                      VARCHAR(60),
    kyc_level                       kyc_level    NOT NULL DEFAULT 'Partial',
    is_pep                          BOOLEAN      NOT NULL DEFAULT FALSE,
    account_created_date            DATE,
    last_active_date                DATE,
    dormant_days_before_activation  INTEGER      DEFAULT 0,
    avg_monthly_txn_volume_usd      NUMERIC(18,4),
    credit_score                    SMALLINT,
    num_linked_accounts             SMALLINT     DEFAULT 1,
    sanctions_hit                   BOOLEAN      DEFAULT FALSE,
    adverse_media_flag              BOOLEAN      DEFAULT FALSE,
    industry                        VARCHAR(80),
    risk_tier                       risk_level   NOT NULL DEFAULT 'LOW',
    created_at                      TIMESTAMPTZ  DEFAULT NOW(),
    updated_at                      TIMESTAMPTZ  DEFAULT NOW()
);

-- ── Transactions ──────────────────────────────────────────────────────────────
CREATE TABLE transactions (
    txn_id                  VARCHAR(20)   PRIMARY KEY,
    sender_id               VARCHAR(20)   NOT NULL REFERENCES users(user_id),
    receiver_id             VARCHAR(20)   NOT NULL REFERENCES users(user_id),
    amount_usd              NUMERIC(18,4) NOT NULL,
    amount_local            NUMERIC(18,4) NOT NULL,
    currency                CHAR(3)       NOT NULL,
    fx_rate_to_usd          NUMERIC(14,6) DEFAULT 1,
    payment_method          VARCHAR(20),
    txn_type                VARCHAR(30),
    timestamp               TIMESTAMPTZ   NOT NULL,
    hour_of_day             SMALLINT,
    day_of_week             VARCHAR(10),
    is_weekend              BOOLEAN       DEFAULT FALSE,
    is_cross_border         BOOLEAN       DEFAULT FALSE,
    sender_country          CHAR(2),
    receiver_country        CHAR(2),
    transaction_fee_usd     NUMERIC(12,4),

    -- Rule flags
    flag_large_transaction  BOOLEAN DEFAULT FALSE,
    flag_high_risk_country  BOOLEAN DEFAULT FALSE,
    flag_pep_involved       BOOLEAN DEFAULT FALSE,
    flag_structuring        BOOLEAN DEFAULT FALSE,
    flag_dormant_account    BOOLEAN DEFAULT FALSE,
    flag_crypto             BOOLEAN DEFAULT FALSE,
    flag_night_transaction  BOOLEAN DEFAULT FALSE,
    flag_round_amount       BOOLEAN DEFAULT FALSE,

    -- Scores
    rule_score              NUMERIC(5,4)  DEFAULT 0,
    ml_score                NUMERIC(5,4)  DEFAULT 0,
    graph_score             NUMERIC(5,4)  DEFAULT 0,
    composite_risk_score    NUMERIC(5,4)  DEFAULT 0,
    risk_label              risk_level    DEFAULT 'LOW',

    -- Meta
    pattern_type            VARCHAR(30)   DEFAULT 'normal',
    is_sar_filed            BOOLEAN       DEFAULT FALSE,
    status                  txn_status    DEFAULT 'Pending',
    device_fingerprint      VARCHAR(32),
    ip_country              CHAR(2),
    channel                 VARCHAR(30),
    created_at              TIMESTAMPTZ   DEFAULT NOW()
);

-- ── Alerts ────────────────────────────────────────────────────────────────────
CREATE TABLE alerts (
    alert_id                VARCHAR(20)    PRIMARY KEY,
    txn_id                  VARCHAR(20)    REFERENCES transactions(txn_id),
    user_id                 VARCHAR(20)    REFERENCES users(user_id),
    alert_rule              VARCHAR(60),
    severity                alert_severity DEFAULT 'MEDIUM',
    composite_risk_score    NUMERIC(5,4),
    rule_score              NUMERIC(5,4),
    ml_score                NUMERIC(5,4),
    graph_score             NUMERIC(5,4),
    alert_created_at        TIMESTAMPTZ    DEFAULT NOW(),
    alert_resolved_at       TIMESTAMPTZ,
    resolution_time_hours   NUMERIC(8,2),
    assigned_analyst        VARCHAR(60),
    alert_status            alert_status   DEFAULT 'Open',
    sar_filed               BOOLEAN        DEFAULT FALSE,
    false_positive          BOOLEAN        DEFAULT FALSE,
    notes                   TEXT,
    updated_at              TIMESTAMPTZ    DEFAULT NOW()
);

-- ── Risk Scores ───────────────────────────────────────────────────────────────
CREATE TABLE risk_scores (
    id              UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type     VARCHAR(20)   NOT NULL,  -- 'transaction' | 'user'
    entity_id       VARCHAR(20)   NOT NULL,
    rule_score      NUMERIC(5,4),
    ml_score        NUMERIC(5,4),
    graph_score     NUMERIC(5,4),
    final_score     NUMERIC(5,4)  NOT NULL,
    risk_level      risk_level    NOT NULL,
    scored_at       TIMESTAMPTZ   DEFAULT NOW(),
    model_version   VARCHAR(20)   DEFAULT 'v1',
    UNIQUE (entity_type, entity_id, scored_at)
);

-- ── PEP Profiles ─────────────────────────────────────────────────────────────
CREATE TABLE pep_profiles (
    pep_id                  VARCHAR(20)   PRIMARY KEY,
    user_id                 VARCHAR(20)   REFERENCES users(user_id),
    role                    VARCHAR(80),
    country                 CHAR(2),
    designation_date        DATE,
    expiry_date             DATE,
    risk_weight_multiplier  NUMERIC(4,2)  DEFAULT 1.5,
    source                  VARCHAR(60),
    last_verified           DATE,
    created_at              TIMESTAMPTZ   DEFAULT NOW()
);

-- ── Country Risk ──────────────────────────────────────────────────────────────
CREATE TABLE country_risk (
    country_code            CHAR(2)      PRIMARY KEY,
    risk_level              risk_level   NOT NULL,
    risk_score_0_100        NUMERIC(5,1),
    fatf_greylist           BOOLEAN      DEFAULT FALSE,
    fatf_blacklist          BOOLEAN      DEFAULT FALSE,
    ofac_sanctions          BOOLEAN      DEFAULT FALSE,
    corruption_index        NUMERIC(5,1),
    aml_deficiency_flag     BOOLEAN      DEFAULT FALSE,
    last_updated            DATE
);

-- ── Graph Nodes ───────────────────────────────────────────────────────────────
CREATE TABLE graph_nodes (
    user_id                  VARCHAR(20)  PRIMARY KEY REFERENCES users(user_id),
    out_degree               INTEGER      DEFAULT 0,
    in_degree                INTEGER      DEFAULT 0,
    betweenness_centrality   NUMERIC(12,8),
    pagerank                 NUMERIC(14,10),
    clustering_coefficient   NUMERIC(12,8),
    is_hub                   BOOLEAN      DEFAULT FALSE,
    computed_at              TIMESTAMPTZ  DEFAULT NOW()
);

-- ── Graph Edges ───────────────────────────────────────────────────────────────
CREATE TABLE graph_edges (
    id              BIGSERIAL    PRIMARY KEY,
    source          VARCHAR(20)  NOT NULL REFERENCES users(user_id),
    target          VARCHAR(20)  NOT NULL REFERENCES users(user_id),
    txn_id          VARCHAR(20)  REFERENCES transactions(txn_id),
    weight          NUMERIC(18,4),
    composite_risk_score NUMERIC(5,4),
    timestamp       TIMESTAMPTZ
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX idx_txn_sender          ON transactions(sender_id);
CREATE INDEX idx_txn_receiver        ON transactions(receiver_id);
CREATE INDEX idx_txn_timestamp       ON transactions(timestamp DESC);
CREATE INDEX idx_txn_risk            ON transactions(composite_risk_score DESC);
CREATE INDEX idx_txn_pattern         ON transactions(pattern_type);
CREATE INDEX idx_alerts_user         ON alerts(user_id);
CREATE INDEX idx_alerts_txn          ON alerts(txn_id);
CREATE INDEX idx_alerts_status       ON alerts(alert_status);
CREATE INDEX idx_alerts_severity     ON alerts(severity);
CREATE INDEX idx_risk_entity         ON risk_scores(entity_type, entity_id);
CREATE INDEX idx_graph_edges_source  ON graph_edges(source);
CREATE INDEX idx_graph_edges_target  ON graph_edges(target);
