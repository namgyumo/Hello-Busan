-- ============================================================
-- Hello-Busan  |  001_create_tables.sql
-- ERD v1.0 기준 전체 테이블 생성
-- Supabase (PostgreSQL 15.x) 대상
-- ============================================================

-- 1. categories (카테고리 마스터)
CREATE TABLE IF NOT EXISTS categories (
    id            VARCHAR(20)   PRIMARY KEY,
    name_ko       VARCHAR(50)   NOT NULL,
    name_en       VARCHAR(50)   NOT NULL,
    name_ja       VARCHAR(50),
    name_zh       VARCHAR(50),
    name_ru       VARCHAR(50),
    icon          VARCHAR(30)   NOT NULL,
    sort_order    INTEGER       NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- 2. tourist_spots (관광지 마스터)
CREATE TABLE IF NOT EXISTS tourist_spots (
    id               SERIAL        PRIMARY KEY,
    external_id      VARCHAR(50)   NOT NULL UNIQUE,
    name             VARCHAR(200)  NOT NULL,
    category_id      VARCHAR(20)   NOT NULL REFERENCES categories(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    lat              DECIMAL(10,7) NOT NULL,
    lng              DECIMAL(10,7) NOT NULL,
    address          VARCHAR(300),
    description      TEXT,
    images           JSONB         DEFAULT '[]',
    operating_hours  VARCHAR(200),
    admission_fee    VARCHAR(100),
    phone            VARCHAR(20),
    capacity         INTEGER,
    region_code      VARCHAR(10),
    is_active        BOOLEAN       NOT NULL DEFAULT true,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spots_category   ON tourist_spots(category_id);
CREATE INDEX IF NOT EXISTS idx_spots_region     ON tourist_spots(region_code);
CREATE INDEX IF NOT EXISTS idx_spots_lat_lng    ON tourist_spots(lat, lng);
CREATE INDEX IF NOT EXISTS idx_spots_active     ON tourist_spots(is_active);

-- updated_at 자동 갱신 트리거
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_spots_updated_at
    BEFORE UPDATE ON tourist_spots
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- 3. spot_translations (다국어 번역)
CREATE TABLE IF NOT EXISTS spot_translations (
    id            SERIAL        PRIMARY KEY,
    spot_id       INTEGER       NOT NULL REFERENCES tourist_spots(id) ON DELETE CASCADE ON UPDATE CASCADE,
    lang          VARCHAR(5)    NOT NULL,
    name          VARCHAR(200)  NOT NULL,
    description   TEXT,
    address       VARCHAR(300),
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE(spot_id, lang)
);

CREATE INDEX IF NOT EXISTS idx_translations_lang ON spot_translations(lang);

CREATE TRIGGER trg_translations_updated_at
    BEFORE UPDATE ON spot_translations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- 4. crowd_data (유동인구/혼잡도)
CREATE TABLE IF NOT EXISTS crowd_data (
    id            BIGSERIAL     PRIMARY KEY,
    spot_id       INTEGER       NOT NULL REFERENCES tourist_spots(id) ON DELETE CASCADE ON UPDATE CASCADE,
    timestamp     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    crowd_count   INTEGER,
    crowd_level   VARCHAR(20)   NOT NULL DEFAULT 'unknown',
    crowd_ratio   DECIMAL(5,2),
    source        VARCHAR(50)   NOT NULL DEFAULT 'data_go_kr',
    raw_data      JSONB
);

CREATE INDEX IF NOT EXISTS idx_crowd_spot_timestamp ON crowd_data(spot_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_crowd_timestamp       ON crowd_data(timestamp);

-- 5. weather_data (날씨)
CREATE TABLE IF NOT EXISTS weather_data (
    id             BIGSERIAL     PRIMARY KEY,
    region_code    VARCHAR(10)   NOT NULL,
    timestamp      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    temperature    DECIMAL(4,1),
    sky_code       VARCHAR(10),
    rain_type      VARCHAR(10),
    rain_amount    DECIMAL(5,1)  DEFAULT 0,
    humidity       INTEGER,
    wind_speed     DECIMAL(4,1),
    weather_score  INTEGER,
    raw_data       JSONB
);

CREATE INDEX IF NOT EXISTS idx_weather_region_ts  ON weather_data(region_code, timestamp);
CREATE INDEX IF NOT EXISTS idx_weather_timestamp  ON weather_data(timestamp);

-- 6. transport_data (교통 접근성)
CREATE TABLE IF NOT EXISTS transport_data (
    id                     BIGSERIAL     PRIMARY KEY,
    spot_id                INTEGER       NOT NULL REFERENCES tourist_spots(id) ON DELETE CASCADE ON UPDATE CASCADE,
    timestamp              TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    nearest_station        VARCHAR(100),
    station_line           VARCHAR(20),
    walk_from_station_min  INTEGER,
    bus_routes             JSONB         DEFAULT '[]',
    transit_score          INTEGER
);

CREATE INDEX IF NOT EXISTS idx_transport_spot_ts ON transport_data(spot_id, timestamp);

-- 7. comfort_scores (쾌적함 지수)
CREATE TABLE IF NOT EXISTS comfort_scores (
    id               BIGSERIAL     PRIMARY KEY,
    spot_id          INTEGER       NOT NULL UNIQUE REFERENCES tourist_spots(id) ON DELETE CASCADE ON UPDATE CASCADE,
    timestamp        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    total_score      INTEGER       NOT NULL,
    grade            VARCHAR(20)   NOT NULL,
    weather_score    INTEGER,
    crowd_score      INTEGER,
    transport_score  INTEGER,
    components       JSONB,
    is_partial       BOOLEAN       NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_comfort_spot_ts    ON comfort_scores(spot_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_comfort_grade      ON comfort_scores(grade);
CREATE INDEX IF NOT EXISTS idx_comfort_timestamp  ON comfort_scores(timestamp);

-- 8. api_call_logs (API 호출 로그)
CREATE TABLE IF NOT EXISTS api_call_logs (
    id               BIGSERIAL     PRIMARY KEY,
    api_name         VARCHAR(50)   NOT NULL,
    endpoint         VARCHAR(500)  NOT NULL,
    status_code      INTEGER,
    success          BOOLEAN       NOT NULL,
    response_time_ms INTEGER,
    error_message    TEXT,
    called_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_logs_name_time  ON api_call_logs(api_name, called_at);
CREATE INDEX IF NOT EXISTS idx_api_logs_success    ON api_call_logs(success);
CREATE INDEX IF NOT EXISTS idx_api_logs_called_at  ON api_call_logs(called_at);
