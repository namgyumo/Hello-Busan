-- ============================================================
-- Hello-Busan  |  005_create_festivals.sql
-- 축제/이벤트 캘린더 테이블
-- ============================================================

CREATE TABLE IF NOT EXISTS festivals (
    id                 SERIAL        PRIMARY KEY,
    content_id         VARCHAR(50)   NOT NULL UNIQUE,
    title              VARCHAR(200)  NOT NULL,
    address            VARCHAR(300),
    lat                DECIMAL(10,7) NOT NULL,
    lng                DECIMAL(10,7) NOT NULL,
    images             JSONB         DEFAULT '[]',
    phone              VARCHAR(50),
    description        TEXT,
    homepage           VARCHAR(500),
    event_start_date   VARCHAR(10),
    event_end_date     VARCHAR(10),
    event_place        VARCHAR(200),
    sponsor            VARCHAR(200),
    use_time           VARCHAR(200),
    is_active          BOOLEAN       NOT NULL DEFAULT true,
    created_at         TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_festivals_active     ON festivals(is_active);
CREATE INDEX IF NOT EXISTS idx_festivals_start_date ON festivals(event_start_date);
CREATE INDEX IF NOT EXISTS idx_festivals_end_date   ON festivals(event_end_date);
CREATE INDEX IF NOT EXISTS idx_festivals_content_id ON festivals(content_id);

CREATE TRIGGER trg_festivals_updated_at
    BEFORE UPDATE ON festivals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
