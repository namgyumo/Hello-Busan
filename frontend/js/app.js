/**
 * app.js — 지도+추천 페이지 오케스트레이터
 */
(async () => {
    const API_BASE = '/api/v1';
    let userLat = null;
    let userLng = null;
    let currentOffset = 0;
    let loading = false;

    // 0) 행동 로그 수집 초기화
    if (typeof Analytics !== 'undefined') Analytics.init();

    // 1) i18n 초기화 (init이 lang-select 리스너도 등록)
    await I18n.init();

    // 2) 지도 초기화
    MapModule.init();

    // 2.5) 코스 플래너 초기화
    if (typeof CourseModule !== 'undefined') CourseModule.init();

    // 3) 카테고리 필터 초기화
    Category.init(() => {
        currentOffset = 0;
        loadSpots(false);
    });

    // 3.5) 검색 초기화
    Search.init(() => {
        currentOffset = 0;
        loadSpots(false);
    });

    // 4) URL 파라미터로 카테고리 자동 선택
    const urlParams = new URLSearchParams(window.location.search);
    const initCategory = urlParams.get('category');
    if (initCategory) {
        Category.select(initCategory);
    }

    // 5) 초기 데이터 로드
    await loadSpots(false);
    loadHeatmap();

    // 6) SSE 연결
    SSE.on('comfort_update', (data) => {
        if (data && data.spots) {
            MapModule.updateMarkers(data.spots);
        }
        showToast(I18n.t('comfort_updated'));
    });

    SSE.on('heatmap_update', (data) => {
        if (data && data.points) {
            MapModule.updateHeatmap(data.points);
        }
    });

    SSE.connect();

    // 7) 위치 버튼
    const btnLocation = document.getElementById('btn-location');
    if (btnLocation) {
        btnLocation.addEventListener('click', requestLocation);
    }

    // 8) 더 보기 버튼
    const btnMore = document.getElementById('btn-more');
    if (btnMore) {
        btnMore.addEventListener('click', () => loadSpots(true));
    }

    // 9) Mobile map/list toggle
    const handleEl = document.getElementById('map-list-handle');
    if (handleEl) {
        handleEl.addEventListener('click', (e) => {
            const tab = e.target.closest('.map-list-handle__tab');
            if (!tab) return;
            const view = tab.dataset.view;
            const layout = document.querySelector('.main-layout');
            if (!layout) return;

            layout.classList.remove('view--map', 'view--list');
            if (view === 'map') layout.classList.add('view--map');
            else if (view === 'list') layout.classList.add('view--list');

            handleEl.querySelectorAll('.map-list-handle__tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Invalidate map size after transition
            setTimeout(() => {
                const map = MapModule.getMap();
                if (map) map.invalidateSize();
            }, 350);
        });
    }

    // 10) 언어 변경 시 재로드
    window.addEventListener('langchange', () => {
        currentOffset = 0;
        loadSpots(false);
        loadHeatmap();
    });

    // ── 함수 정의 ──

    async function loadSpots(append) {
        if (loading) return;
        loading = true;

        if (!append) {
            Recommend.showSkeleton();
            currentOffset = 0;
        }

        try {
            const categories = Category.getSelected();
            const searchQuery = Search.getQuery();
            const json = await Recommend.fetchSpots(userLat, userLng, categories, currentOffset, searchQuery);

            if (!json.success) {
                showFallback();
                Recommend.renderList([], false);
                return;
            }

            const items = json.data || [];
            Recommend.renderList(items, append);
            MapModule.updateMarkers(items);

            // When searching or filtering, zoom map to fit results
            if (!append && (searchQuery || categories.length > 0) && items.length > 0) {
                MapModule.fitToSpots(items);
            }

            currentOffset += items.length;

            const btnMore = document.getElementById('btn-more');
            if (btnMore) {
                btnMore.style.display = items.length >= Recommend.PAGE_SIZE ? '' : 'none';
            }
        } catch (e) {
            console.error('추천 로드 실패:', e);
            showFallback();
            if (!append) Recommend.renderList([], false);
        } finally {
            loading = false;
        }
    }

    async function loadHeatmap() {
        try {
            const res = await fetch(`${API_BASE}/heatmap?lang=${I18n.getLang()}`);
            const json = await res.json();
            if (json.success && json.data && json.data.points) {
                MapModule.updateHeatmap(json.data.points);
            }
        } catch (e) {
            console.warn('히트맵 로드 실패:', e);
        }
    }

    function requestLocation() {
        if (!navigator.geolocation) {
            showToast(I18n.t('location_unavailable'));
            return;
        }

        const btn = document.getElementById('btn-location');
        if (btn) btn.disabled = true;

        navigator.geolocation.getCurrentPosition(
            (pos) => {
                userLat = pos.coords.latitude;
                userLng = pos.coords.longitude;
                MapModule.setUserLocation(userLat, userLng);
                currentOffset = 0;
                loadSpots(false);
                if (btn) btn.disabled = false;
            },
            (err) => {
                console.warn('위치 오류:', err);
                showToast(I18n.t('location_error'));
                if (btn) btn.disabled = false;
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    }

    function showToast(msg) {
        const el = document.getElementById('toast');
        if (!el) return;
        el.textContent = msg;
        el.classList.add('show');
        setTimeout(() => el.classList.remove('show'), 3000);
    }

    function showFallback() {
        const banner = document.getElementById('fallback-banner');
        if (banner) banner.classList.add('visible');
    }
})();
