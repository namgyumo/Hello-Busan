/**
 * map.js — Leaflet 지도 + 히트맵
 */
const MapModule = (() => {
    const BUSAN_CENTER = [35.1796, 129.0756];
    const DEFAULT_ZOOM = 12;
    let map = null;
    let heatLayer = null;
    let markerLayer = null;
    let heatmapVisible = true;

    function init() {
        map = L.map('map').setView(BUSAN_CENTER, DEFAULT_ZOOM);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 18,
        }).addTo(map);

        markerLayer = L.layerGroup().addTo(map);

        // 지도 이동 시 행동 로그 수집 (디바운스)
        let mapMoveTimer = null;
        map.on('moveend', () => {
            if (mapMoveTimer) clearTimeout(mapMoveTimer);
            mapMoveTimer = setTimeout(() => {
                if (typeof Analytics !== 'undefined') {
                    var center = map.getCenter();
                    Analytics.trackMapMove(center, map.getZoom());
                }
            }, 1000);
        });

        // 히트맵 토글 버튼
        const toggleBtn = document.getElementById('btn-heatmap-toggle');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => {
                heatmapVisible = !heatmapVisible;
                toggleBtn.textContent = heatmapVisible ? '히트맵 ON' : '히트맵 OFF';
                if (heatLayer) {
                    heatmapVisible ? heatLayer.addTo(map) : map.removeLayer(heatLayer);
                }
            });
        }
    }

    function setUserLocation(lat, lng) {
        if (!map) return;
        map.setView([lat, lng], 14);
        L.marker([lat, lng], {
            icon: L.divIcon({
                className: '',
                html: '<div style="font-size:1.5rem">📍</div>',
                iconSize: [24, 24],
                iconAnchor: [12, 24],
            }),
        }).addTo(markerLayer).bindPopup('현재 위치');
    }

    function updateHeatmap(points) {
        if (!map) return;
        if (heatLayer) map.removeLayer(heatLayer);

        heatLayer = L.heatLayer(points, {
            radius: 25,
            blur: 15,
            maxZoom: 17,
            gradient: { 0.4: 'green', 0.6: 'yellow', 0.8: 'orange', 1.0: 'red' },
        });

        if (heatmapVisible) heatLayer.addTo(map);
    }

    function updateMarkers(spots) {
        if (!markerLayer) return;
        markerLayer.clearLayers();

        spots.forEach(spot => {
            if (!spot.lat || !spot.lng) return;
            const badge = _comfortBadgeHtml(spot.comfort_score, spot.comfort_grade);
            const marker = L.marker([spot.lat, spot.lng]).addTo(markerLayer);
            marker.bindPopup(`
                <strong>${spot.name}</strong><br>
                ${badge}
                <br><a href="/detail.html?id=${spot.id}">상세보기</a>
            `);
        });
    }

    function _comfortBadgeHtml(score, grade) {
        if (!score && score !== 0) return '';
        const clsMap = { '쾌적': 'good', '보통': 'normal', '혼잡': 'crowded', '매우혼잡': 'very-crowded' };
        const cls = clsMap[grade] || 'normal';
        return `<span class="comfort-badge comfort-badge--${cls}">${grade} ${score}점</span>`;
    }

    function getMap() { return map; }

    return { init, setUserLocation, updateHeatmap, updateMarkers, getMap };
})();
