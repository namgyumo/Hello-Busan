/**
 * app.js — 메인 오케스트레이터
 */
(async () => {
    const API_BASE = '/api/v1';
    let userLat = null;
    let userLng = null;
    let currentOffset = 0;
    let loading = false;

    // 1) i18n 초기화
    await I18n.init();
    const langSelect = document.getElementById('lang-select');
    if (langSelect) {
        langSelect.value = I18n.getLang();
        langSelect.addEventListener('change', () => {
            I18n.setLang(langSelect.value);
        });
    }

    // 2) 지도 초기화
    MapModule.init();

    // 3) 카테고리 필터 초기화
    Category.init(() => {
        currentOffset = 0;
        loadSpots(false);
    });

    // 4) 초기 데이터 로드
    await loadSpots(false);
    loadHeatmap();

    // 5) SSE 연결
    SSE.on('comfort_update', (data) => {
        if (data && data.spots) {
            MapModule.updateMarkers(data.spots);
        }
        showToast('쾌적도가 업데이트되었습니다');
    });

    SSE.on('heatmap_update', (data) => {
        if (data && data.points) {
            MapModule.updateHeatmap(data.points);
        }
    });

    SSE.connect();

    // 6) 위치 버튼
    const btnLocation = document.getElementById('btn-location');
    if (btnLocation) {
        btnLocation.addEventListener('click', requestLocation);
    }

    // 7) 더 보기 버튼
    const btnMore = document.getElementById('btn-more');
    if (btnMore) {
        btnMore.addEventListener('click', () => loadSpots(true));
    }

    // 8) 언어 변경 시 재로드
    window.addEventListener('langchange', () => {
        if (langSelect) langSelect.value = I18n.getLang();
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
            const json = await Recommend.fetchSpots(userLat, userLng, categories, currentOffset);

            if (!json.success) {
                showFallback();
                Recommend.renderList([], false);
                return;
            }

            const items = json.data || [];
            Recommend.renderList(items, append);
            MapModule.updateMarkers(items);

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
                MapModule.updateHeatmap(
                    json.data.points.map(p => [p.lat, p.lng, p.intensity])
                );
            }
        } catch (e) {
            console.warn('히트맵 로드 실패:', e);
        }
    }

    function requestLocation() {
        if (!navigator.geolocation) {
            showToast('위치 서비스를 사용할 수 없습니다');
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
                showToast('위치를 가져올 수 없습니다');
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
        if (banner) banner.style.display = '';
    }
})();
