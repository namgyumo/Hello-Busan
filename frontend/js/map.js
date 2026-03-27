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
    let userMarker = null;

    function init() {
        map = L.map('map').setView(BUSAN_CENTER, DEFAULT_ZOOM);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 18,
        }).addTo(map);

        markerLayer = L.layerGroup().addTo(map);

        // Hide loading overlay once tiles are loaded
        map.once('load', _hideLoading);
        map.whenReady(() => {
            setTimeout(_hideLoading, 500);
        });

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
                const labelEl = toggleBtn.querySelector('.map-ctrl-btn__label');
                if (labelEl) {
                    labelEl.textContent = typeof I18n !== 'undefined'
                        ? I18n.t(heatmapVisible ? 'heatmap_on' : 'heatmap_off')
                        : (heatmapVisible ? '히트맵 ON' : '히트맵 OFF');
                }
                toggleBtn.classList.toggle('active', heatmapVisible);
                if (heatLayer) {
                    heatmapVisible ? heatLayer.addTo(map) : map.removeLayer(heatLayer);
                }
            });
        }
    }

    function _hideLoading() {
        const overlay = document.getElementById('map-loading');
        if (overlay) {
            overlay.classList.add('map-loading-overlay--hidden');
            setTimeout(() => { overlay.style.display = 'none'; }, 400);
        }
    }

    function setUserLocation(lat, lng) {
        if (!map) return;
        // Remove previous user marker
        if (userMarker) {
            markerLayer.removeLayer(userMarker);
        }
        map.setView([lat, lng], 14);
        userMarker = L.marker([lat, lng], {
            icon: L.divIcon({
                className: 'user-location-icon',
                html: '<div class="user-location-marker"><div class="user-location-dot"></div><div class="user-location-pulse"></div></div>',
                iconSize: [24, 24],
                iconAnchor: [12, 12],
            }),
        }).addTo(markerLayer).bindPopup('<div class="map-popup map-popup--user"><strong>' + (typeof I18n !== 'undefined' ? I18n.t('current_location') : '현재 위치') + '</strong></div>');
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

    function _escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function _categoryEmoji(cat) {
        var emojiMap = {
            nature: '\u{1F3D4}', culture: '\u{1F3DB}', food: '\u{1F35C}',
            activity: '\u{1F3C4}', shopping: '\u{1F6CD}', nightview: '\u{1F319}',
        };
        return emojiMap[cat] || '\u{1F30A}';
    }

    function _categoryLabel(cat) {
        if (typeof I18n === 'undefined') return cat || '';
        var keyMap = {
            nature: 'category_nature', culture: 'category_culture', food: 'category_food',
            activity: 'category_activity', shopping: 'category_shopping', nightview: 'category_nightview',
        };
        return keyMap[cat] ? I18n.t(keyMap[cat]) : (cat || '');
    }

    function updateMarkers(spots) {
        if (!markerLayer) return;
        markerLayer.clearLayers();
        // Re-add user marker if it exists
        if (userMarker) userMarker.addTo(markerLayer);

        var bounds = [];
        spots.forEach(spot => {
            if (spot.lat == null || spot.lng == null) return;
            bounds.push([spot.lat, spot.lng]);

            var badge = _comfortBadgeHtml(spot.comfort_score, spot.comfort_grade);
            var safeName = _escapeHtml(spot.name);
            var catEmoji = _categoryEmoji(spot.category);
            var catLabel = _categoryLabel(spot.category);

            // Enhanced popup with category, image, and more info
            var thumbUrl = spot.thumbnail_url || (spot.images && spot.images.length > 0 ? spot.images[0] : '');
            var thumbHtml = thumbUrl
                ? '<div class="map-popup__thumb"><img src="' + _escapeHtml(thumbUrl) + '" alt="" loading="lazy"></div>'
                : '';

            var popupContent = '<div class="map-popup">'
                + thumbHtml
                + '<div class="map-popup__body">'
                + (catLabel ? '<span class="map-popup__cat">' + catEmoji + ' ' + catLabel + '</span>' : '')
                + '<strong class="map-popup__name">' + safeName + '</strong>'
                + (badge ? '<div class="map-popup__comfort">' + badge + '</div>' : '')
                + (spot.address ? '<div class="map-popup__address">' + _escapeHtml(spot.address) + '</div>' : '')
                + '<a class="map-popup__link" href="/detail.html?id=' + encodeURIComponent(spot.id) + '">'
                + (typeof I18n !== 'undefined' ? I18n.t('view_detail') : '상세보기') + ' &rarr;</a>'
                + '</div></div>';

            var marker = L.marker([spot.lat, spot.lng], {
                icon: L.divIcon({
                    className: 'spot-marker-icon',
                    html: '<div class="spot-marker spot-marker--' + _comfortClass(spot.comfort_score) + '"><span>' + catEmoji + '</span></div>',
                    iconSize: [36, 36],
                    iconAnchor: [18, 36],
                    popupAnchor: [0, -36],
                }),
            }).addTo(markerLayer);
            var popupMaxWidth = window.innerWidth < 400 ? 200 : 260;
            marker.bindPopup(popupContent, { maxWidth: popupMaxWidth, className: 'map-popup-container' });
        });

        // Update spot count display
        _updateSpotCount(spots.length);
    }

    /** Zoom the map to fit given spots */
    function fitToSpots(spots) {
        if (!map || !spots || spots.length === 0) return;
        var bounds = [];
        spots.forEach(function(s) {
            if (s.lat != null && s.lng != null) bounds.push([s.lat, s.lng]);
        });
        if (bounds.length === 1) {
            map.setView(bounds[0], 15);
        } else if (bounds.length > 1) {
            map.fitBounds(L.latLngBounds(bounds).pad(0.15));
        }
    }

    function _updateSpotCount(count) {
        var el = document.getElementById('spot-count');
        if (!el) return;
        if (count > 0) {
            el.textContent = count + (typeof I18n !== 'undefined' ? I18n.t('spot_count_suffix') : '개');
            el.style.display = '';
        } else {
            el.style.display = 'none';
        }
    }

    function _comfortClass(score) {
        if (score == null) return 'default';
        if (score >= 80) return 'good';
        if (score >= 60) return 'normal';
        if (score >= 40) return 'crowded';
        return 'very-crowded';
    }

    function _comfortBadgeHtml(score, grade) {
        if (!score && score !== 0) return '';
        var cls = _comfortClass(score);
        var gradeText = typeof I18n !== 'undefined' ? _gradeTextFromScore(score) : (grade || '');
        var unitScore = typeof I18n !== 'undefined' ? I18n.t('unit_score') : '점';
        return '<span class="comfort-badge comfort-badge--' + cls + '">' + gradeText + ' ' + score + unitScore + '</span>';
    }

    function _gradeTextFromScore(score) {
        if (score == null) return '';
        if (score >= 80) return I18n.t('comfort_good');
        if (score >= 60) return I18n.t('comfort_normal');
        if (score >= 40) return I18n.t('comfort_crowded');
        return I18n.t('comfort_very_crowded');
    }

    function getMap() { return map; }

    return { init, setUserLocation, updateHeatmap, updateMarkers, fitToSpots, getMap };
})();
