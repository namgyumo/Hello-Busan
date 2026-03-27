/**
 * analytics.js — 사용자 행동 로그 수집 모듈
 *
 * - 세션 ID 생성 (UUID v4, sessionStorage)
 * - 이벤트 큐 + 5초 또는 10개 이벤트마다 배치 전송
 * - 페이지 언로드 시 navigator.sendBeacon으로 잔여 이벤트 전송
 * - 개인정보 패턴 필터링 (전화번호, 이메일)
 */
const Analytics = (() => {
    const ENDPOINT = '/api/v1/analytics/events';
    const FLUSH_INTERVAL = 5000;  // 5초
    const FLUSH_THRESHOLD = 10;   // 10개 이벤트
    const SESSION_KEY = 'hello_busan_session_id';

    let queue = [];
    let flushTimer = null;
    let currentPage = '';
    let detailEnterTime = null;

    // 개인정보 패턴 (전화번호, 이메일)
    const PII_PATTERNS = [
        /\b\d{2,4}[-.\s]?\d{3,4}[-.\s]?\d{4}\b/g,                    // 전화번호
        /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g,     // 이메일
        /\b\d{6}[-]?\d{7}\b/g,                                        // 주민등록번호
    ];

    function _generateUUID() {
        if (crypto && crypto.randomUUID) {
            return crypto.randomUUID();
        }
        // fallback
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            var r = Math.random() * 16 | 0;
            var v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    function _getSessionId() {
        let sid = sessionStorage.getItem(SESSION_KEY);
        if (!sid) {
            sid = _generateUUID();
            sessionStorage.setItem(SESSION_KEY, sid);
        }
        return sid;
    }

    function _stripPII(text) {
        if (typeof text !== 'string') return text;
        let result = text;
        PII_PATTERNS.forEach(function (pattern) {
            pattern.lastIndex = 0;
            result = result.replace(pattern, '[REDACTED]');
        });
        return result;
    }

    function _sanitizeData(data) {
        if (!data || typeof data !== 'object') return data;
        var sanitized = {};
        Object.keys(data).forEach(function (key) {
            var val = data[key];
            sanitized[key] = typeof val === 'string' ? _stripPII(val) : val;
        });
        return sanitized;
    }

    function _detectPage() {
        var path = window.location.pathname;
        if (path === '/' || path === '/index.html') return 'home';
        if (path === '/map.html') return 'map';
        if (path === '/detail.html') return 'detail';
        return path.replace(/^\//, '').replace(/\.html$/, '') || 'unknown';
    }

    /**
     * 이벤트를 큐에 추가
     */
    function track(eventType, data, spotId) {
        var event = {
            session_id: _getSessionId(),
            event_type: eventType,
            event_data: _sanitizeData(data || {}),
            page: currentPage || _detectPage(),
        };
        if (spotId != null) {
            var parsed = parseInt(spotId, 10);
            if (!isNaN(parsed)) {
                event.spot_id = parsed;
            }
        }

        queue.push(event);

        if (queue.length >= FLUSH_THRESHOLD) {
            _flush();
        }
    }

    /**
     * 큐에 쌓인 이벤트를 서버로 전송
     */
    function _flush() {
        if (queue.length === 0) return;

        var batch = queue.splice(0, 50);
        var payload = JSON.stringify({ events: batch });

        try {
            fetch(ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: payload,
                keepalive: true,
            }).catch(function () {
                // 전송 실패 시 무시 (사용자 경험에 영향 없음)
            });
        } catch (e) {
            // 무시
        }
    }

    /**
     * sendBeacon으로 잔여 이벤트 전송 (페이지 언로드 시)
     */
    function _flushBeacon() {
        if (queue.length === 0) return;

        var batch = queue.splice(0, 50);
        var payload = JSON.stringify({ events: batch });

        if (navigator.sendBeacon) {
            navigator.sendBeacon(ENDPOINT, new Blob([payload], { type: 'application/json' }));
        } else {
            // sendBeacon 미지원 시 동기 fetch
            try {
                fetch(ENDPOINT, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: payload,
                    keepalive: true,
                });
            } catch (e) {
                // 무시
            }
        }
    }

    /**
     * 초기화 — 자동 page_view 전송 + 타이머 시작
     */
    function init() {
        currentPage = _detectPage();

        // page_view 이벤트 자동 전송
        track('page_view', {
            url: window.location.pathname + window.location.search,
            referrer: document.referrer || null,
        });

        // 상세 페이지 체류시간 측정 시작
        if (currentPage === 'detail') {
            var params = new URLSearchParams(window.location.search);
            var spotId = params.get('id');
            detailEnterTime = Date.now();
            if (spotId) {
                track('detail_view', {}, spotId);
            }
        }

        // 주기적 flush 타이머
        flushTimer = setInterval(_flush, FLUSH_INTERVAL);

        // 페이지 언로드 시 잔여 이벤트 전송
        window.addEventListener('visibilitychange', function () {
            if (document.visibilityState === 'hidden') {
                // 상세 페이지 이탈 시 체류시간 포함
                if (currentPage === 'detail' && detailEnterTime) {
                    var params = new URLSearchParams(window.location.search);
                    var spotId = params.get('id');
                    var dwellTime = Math.round((Date.now() - detailEnterTime) / 1000);
                    track('detail_leave', { dwell_seconds: dwellTime }, spotId);
                    detailEnterTime = null;
                }
                _flushBeacon();
            }
        });

        window.addEventListener('pagehide', function () {
            if (currentPage === 'detail' && detailEnterTime) {
                var params = new URLSearchParams(window.location.search);
                var spotId = params.get('id');
                var dwellTime = Math.round((Date.now() - detailEnterTime) / 1000);
                track('detail_leave', { dwell_seconds: dwellTime }, spotId);
                detailEnterTime = null;
            }
            _flushBeacon();
        });
    }

    // 편의 메서드: 특정 이벤트 추적
    function trackSpotClick(spotId, spotName) {
        track('spot_click', { spot_name: spotName }, spotId);
    }

    function trackCategoryClick(categoryId) {
        track('category_click', { category: categoryId });
    }

    function trackSearch(query) {
        track('search', { query: _stripPII(query) });
    }

    function trackMapMove(center, zoom) {
        track('map_move', { lat: center.lat, lng: center.lng, zoom: zoom });
    }

    function trackShare(spotId, method) {
        track('share', { method: method }, spotId);
    }

    function trackFavorite(spotId, action) {
        track('favorite', { action: action }, spotId);
    }

    return {
        init: init,
        track: track,
        trackSpotClick: trackSpotClick,
        trackCategoryClick: trackCategoryClick,
        trackSearch: trackSearch,
        trackMapMove: trackMapMove,
        trackShare: trackShare,
        trackFavorite: trackFavorite,
    };
})();
