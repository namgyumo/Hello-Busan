-- ============================================================
-- Hello-Busan  |  004_create_user_events.sql
-- 사용자 행동 로그 수집 테이블
-- ============================================================

-- user_events (사용자 행동 이벤트 로그)
CREATE TABLE IF NOT EXISTS user_events (
    id            BIGSERIAL     PRIMARY KEY,
    session_id    VARCHAR(36)   NOT NULL,
    event_type    VARCHAR(30)   NOT NULL,
    event_data    JSONB         DEFAULT '{}',
    spot_id       INTEGER       REFERENCES tourist_spots(id) ON DELETE SET NULL,
    page          VARCHAR(50)   NOT NULL,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- 인덱스: 세션 기반 조회
CREATE INDEX IF NOT EXISTS idx_user_events_session
    ON user_events(session_id, created_at);

-- 인덱스: 이벤트 타입별 조회
CREATE INDEX IF NOT EXISTS idx_user_events_type
    ON user_events(event_type, created_at);

-- 인덱스: 관광지별 이벤트 조회
CREATE INDEX IF NOT EXISTS idx_user_events_spot
    ON user_events(spot_id, created_at)
    WHERE spot_id IS NOT NULL;

-- 인덱스: 생성 시간 기반 (오래된 데이터 정리용)
CREATE INDEX IF NOT EXISTS idx_user_events_created_at
    ON user_events(created_at);

-- event_type 체크 제약조건
ALTER TABLE user_events
    ADD CONSTRAINT chk_event_type
    CHECK (event_type IN (
        'page_view',
        'spot_click',
        'category_click',
        'search',
        'map_move',
        'detail_view',
        'detail_leave',
        'share',
        'favorite'
    ));

-- 30일 이상 오래된 이벤트 자동 정리 정책 (선택적)
-- Supabase pg_cron 이 활성화된 경우 사용 가능:
-- SELECT cron.schedule('cleanup-old-events', '0 3 * * *',
--     $$DELETE FROM user_events WHERE created_at < NOW() - INTERVAL '30 days'$$
-- );
