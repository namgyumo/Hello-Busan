-- ============================================================
-- Hello-Busan  |  003_cleanup_policies.sql
-- 데이터 정리 함수 (매일 새벽 3시 Supabase cron 또는 수동 호출)
-- ============================================================

-- 오래된 데이터 일괄 정리 함수
CREATE OR REPLACE FUNCTION cleanup_old_data()
RETURNS TABLE(
    table_name TEXT,
    deleted_count BIGINT
) AS $$
DECLARE
    cnt BIGINT;
BEGIN
    -- crowd_data: 7일 보존
    DELETE FROM crowd_data WHERE timestamp < NOW() - INTERVAL '7 days';
    GET DIAGNOSTICS cnt = ROW_COUNT;
    table_name := 'crowd_data'; deleted_count := cnt; RETURN NEXT;

    -- weather_data: 7일 보존
    DELETE FROM weather_data WHERE timestamp < NOW() - INTERVAL '7 days';
    GET DIAGNOSTICS cnt = ROW_COUNT;
    table_name := 'weather_data'; deleted_count := cnt; RETURN NEXT;

    -- transport_data: 3일 보존
    DELETE FROM transport_data WHERE timestamp < NOW() - INTERVAL '3 days';
    GET DIAGNOSTICS cnt = ROW_COUNT;
    table_name := 'transport_data'; deleted_count := cnt; RETURN NEXT;

    -- comfort_scores: 1일 보존
    DELETE FROM comfort_scores WHERE timestamp < NOW() - INTERVAL '1 day';
    GET DIAGNOSTICS cnt = ROW_COUNT;
    table_name := 'comfort_scores'; deleted_count := cnt; RETURN NEXT;

    -- api_call_logs: 30일 보존
    DELETE FROM api_call_logs WHERE called_at < NOW() - INTERVAL '30 days';
    GET DIAGNOSTICS cnt = ROW_COUNT;
    table_name := 'api_call_logs'; deleted_count := cnt; RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- 사용법: SELECT * FROM cleanup_old_data();
-- Supabase cron 등록 (pg_cron 확장 사용 시):
-- SELECT cron.schedule('cleanup-old-data', '0 3 * * *', 'SELECT * FROM cleanup_old_data()');
