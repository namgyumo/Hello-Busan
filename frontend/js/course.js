/**
 * course.js -- Course Planner (코스 추천 플래너)
 */
const CourseModule = (() => {
    const API_BASE = '/api/v1';
    let courseLayer = null;
    let polylineLayer = null;
    let startMarker = null;
    let pickingStart = false;
    let startLat = null;
    let startLng = null;
    let mapClickHandler = null;

    function init() {
        const btn = document.getElementById('btn-course');
        if (btn) {
            btn.addEventListener('click', openPanel);
        }

        const closeBtn = document.getElementById('course-panel-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', closePanel);
        }

        const overlay = document.getElementById('course-overlay');
        if (overlay) {
            overlay.addEventListener('click', closePanel);
        }

        const generateBtn = document.getElementById('course-generate-btn');
        if (generateBtn) {
            generateBtn.addEventListener('click', generate);
        }

        const resetBtn = document.getElementById('course-reset-btn');
        if (resetBtn) {
            resetBtn.addEventListener('click', resetCourse);
        }

        const regenBtn = document.getElementById('course-regen-btn');
        if (regenBtn) {
            regenBtn.addEventListener('click', generate);
        }

        // Start location radio buttons
        const startRadios = document.querySelectorAll('input[name="course-start"]');
        startRadios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                _handleStartChange(e.target.value);
            });
        });

        // Map click handler for picking start location
        const map = MapModule.getMap();
        if (map) {
            mapClickHandler = (e) => {
                if (!pickingStart) return;
                startLat = e.latlng.lat;
                startLng = e.latlng.lng;
                _placeStartMarker(startLat, startLng);
                pickingStart = false;
                const notice = document.getElementById('course-map-notice');
                if (notice) notice.style.display = 'none';
                const mapEl = document.getElementById('map');
                if (mapEl) mapEl.style.cursor = '';
            };
            map.on('click', mapClickHandler);
        }
    }

    function openPanel() {
        const panel = document.getElementById('course-panel');
        const overlay = document.getElementById('course-overlay');
        if (panel) {
            panel.classList.add('open');
            if (overlay) overlay.classList.add('open');
            _showSettings();
            // On mobile, switch to map view when opening course planner
            if (window.innerWidth < 768) {
                const layout = document.querySelector('.main-layout');
                if (layout) {
                    layout.classList.remove('view--list');
                    layout.classList.add('view--map');
                }
                const handleEl = document.getElementById('map-list-handle');
                if (handleEl) {
                    handleEl.querySelectorAll('.map-list-handle__tab').forEach(t => t.classList.remove('active'));
                    const mapTab = handleEl.querySelector('[data-view="map"]');
                    if (mapTab) mapTab.classList.add('active');
                }
                setTimeout(() => {
                    const m = MapModule.getMap();
                    if (m) m.invalidateSize();
                }, 350);
            }
        }
    }

    function closePanel() {
        const panel = document.getElementById('course-panel');
        const overlay = document.getElementById('course-overlay');
        if (panel) panel.classList.remove('open');
        if (overlay) overlay.classList.remove('open');
        pickingStart = false;
        const mapEl = document.getElementById('map');
        if (mapEl) mapEl.style.cursor = '';
        const notice = document.getElementById('course-map-notice');
        if (notice) notice.style.display = 'none';
    }

    function _showSettings() {
        const settingsEl = document.getElementById('course-settings');
        const resultEl = document.getElementById('course-result');
        if (settingsEl) settingsEl.style.display = '';
        if (resultEl) resultEl.style.display = 'none';
    }

    function _showResult() {
        const settingsEl = document.getElementById('course-settings');
        const resultEl = document.getElementById('course-result');
        if (settingsEl) settingsEl.style.display = 'none';
        if (resultEl) resultEl.style.display = '';
    }

    function _handleStartChange(value) {
        const notice = document.getElementById('course-map-notice');
        const mapEl = document.getElementById('map');
        if (value === 'current') {
            pickingStart = false;
            if (mapEl) mapEl.style.cursor = '';
            if (notice) notice.style.display = 'none';
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        startLat = pos.coords.latitude;
                        startLng = pos.coords.longitude;
                        _placeStartMarker(startLat, startLng);
                    },
                    () => {
                        startLat = null;
                        startLng = null;
                    }
                );
            }
        } else if (value === 'map') {
            pickingStart = true;
            if (mapEl) mapEl.style.cursor = 'crosshair';
            if (notice) {
                notice.textContent = I18n.t('course_click_map');
                notice.style.display = 'block';
            }
        } else {
            // default: Busan Station
            pickingStart = false;
            if (mapEl) mapEl.style.cursor = '';
            if (notice) notice.style.display = 'none';
            startLat = null;
            startLng = null;
        }
    }

    function _placeStartMarker(lat, lng) {
        const map = MapModule.getMap();
        if (!map) return;
        if (startMarker) {
            map.removeLayer(startMarker);
        }
        startMarker = L.marker([lat, lng], {
            icon: L.divIcon({
                className: 'course-start-icon',
                html: '<div class="course-marker course-marker--start">S</div>',
                iconSize: [32, 32],
                iconAnchor: [16, 32],
            }),
        }).addTo(map);
        map.setView([lat, lng], 13);
    }

    async function generate() {
        const duration = document.querySelector('input[name="course-duration"]:checked');
        const durationValue = duration ? duration.value : 'half';

        // Gather selected categories
        const catChecks = document.querySelectorAll('.course-cat-check:checked');
        const categories = Array.from(catChecks).map(c => c.value);

        const maxSpotsInput = document.getElementById('course-max-spots');
        const maxSpots = maxSpotsInput ? parseInt(maxSpotsInput.value, 10) || 5 : 5;

        const params = new URLSearchParams();
        params.set('duration', durationValue);
        if (startLat != null && startLng != null) {
            params.set('start_lat', startLat);
            params.set('start_lng', startLng);
        }
        if (categories.length) {
            params.set('categories', categories.join(','));
        }
        params.set('max_spots', maxSpots);
        params.set('lang', I18n.getLang());

        // Show loading with spinner
        const resultList = document.getElementById('course-list');
        const summaryEl = document.getElementById('course-summary');
        const genBtn = document.getElementById('course-generate-btn');
        const regenBtn = document.getElementById('course-regen-btn');
        if (genBtn) genBtn.disabled = true;
        if (regenBtn) regenBtn.disabled = true;
        if (resultList) resultList.innerHTML = `<div class="course-loading"><div class="course-loading-spinner"></div><span>${I18n.t('course_generating')}</span></div>`;
        _showResult();

        try {
            const res = await fetch(`${API_BASE}/course/generate?${params}`);
            const json = await res.json();

            if (!json.success || !json.data || !json.data.course || json.data.course.length === 0) {
                if (resultList) {
                    resultList.innerHTML = `<div class="course-empty">${I18n.t('course_no_results')}</div>`;
                }
                if (summaryEl) summaryEl.innerHTML = '';
                return;
            }

            const data = json.data;
            _renderCourseOnMap(data);
            _renderCourseList(data);
        } catch (e) {
            console.error('Course generation failed:', e);
            if (resultList) {
                resultList.innerHTML = `<div class="course-empty">${I18n.t('course_no_results')}</div>`;
            }
        } finally {
            if (genBtn) genBtn.disabled = false;
            if (regenBtn) regenBtn.disabled = false;
        }
    }

    function _renderCourseOnMap(data) {
        const map = MapModule.getMap();
        if (!map) return;

        // Clear previous course layers
        if (courseLayer) {
            map.removeLayer(courseLayer);
        }
        if (polylineLayer) {
            map.removeLayer(polylineLayer);
        }

        courseLayer = L.layerGroup().addTo(map);

        // Start marker
        const startPt = [data.start_lat, data.start_lng];
        if (startMarker) map.removeLayer(startMarker);
        startMarker = L.marker(startPt, {
            icon: L.divIcon({
                className: 'course-start-icon',
                html: '<div class="course-marker course-marker--start">S</div>',
                iconSize: [32, 32],
                iconAnchor: [16, 32],
            }),
        }).addTo(courseLayer);

        // Course points
        const latlngs = [startPt];
        data.course.forEach(item => {
            const spot = item.spot;
            if (spot.lat == null || spot.lng == null) return;
            const pt = [spot.lat, spot.lng];
            latlngs.push(pt);

            L.marker(pt, {
                icon: L.divIcon({
                    className: 'course-order-icon',
                    html: `<div class="course-marker course-marker--order">${item.order}</div>`,
                    iconSize: [32, 32],
                    iconAnchor: [16, 32],
                }),
            }).addTo(courseLayer).bindPopup(`
                <strong>${item.order}. ${_escapeHtml(spot.name)}</strong><br>
                ${I18n.t('course_comfort')}: ${spot.comfort_score != null ? spot.comfort_score : '--'}<br>
                ${I18n.t('course_travel_time')}: ${item.travel_time}${I18n.t('course_minutes')} / ${I18n.t('course_stay_time')}: ${item.stay_time}${I18n.t('course_minutes')}
            `);
        });

        // Polyline
        polylineLayer = L.polyline(latlngs, {
            color: getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim() || '#0066CC',
            weight: 4,
            opacity: 0.8,
            dashArray: '10, 8',
            lineCap: 'round',
        }).addTo(courseLayer);

        // Fit bounds
        if (latlngs.length > 1) {
            map.fitBounds(L.latLngBounds(latlngs).pad(0.15));
        }
    }

    function _renderCourseList(data) {
        const resultList = document.getElementById('course-list');
        const summaryEl = document.getElementById('course-summary');

        if (!resultList) return;
        resultList.innerHTML = '';

        data.course.forEach(item => {
            const spot = item.spot;
            const scoreClass = _scoreClass(spot.comfort_score);

            const card = document.createElement('div');
            card.className = 'course-item';
            card.innerHTML = `
                <div class="course-item__order">${item.order}</div>
                <div class="course-item__body">
                    <div class="course-item__name">${_escapeHtml(spot.name)}</div>
                    <div class="course-item__meta">
                        <span class="course-item__comfort ${scoreClass}">${spot.comfort_score != null ? spot.comfort_score : '--'}</span>
                        <span class="course-item__dist">${I18n.t('course_distance_from_prev')} ${item.distance_from_prev}km</span>
                        <span class="course-item__time">${I18n.t('course_travel_time')} ${item.travel_time}${I18n.t('course_minutes')}</span>
                    </div>
                </div>
            `;
            card.addEventListener('click', () => {
                if (spot.lat != null && spot.lng != null) {
                    const map = MapModule.getMap();
                    if (map) map.setView([spot.lat, spot.lng], 15);
                }
            });
            resultList.appendChild(card);
        });

        // Summary
        if (summaryEl) {
            const hours = Math.floor(data.total_time / 60);
            const mins = data.total_time % 60;
            const timeStr = hours > 0 ? `${hours}h ${mins}${I18n.t('course_minutes')}` : `${mins}${I18n.t('course_minutes')}`;
            summaryEl.innerHTML = `
                <div class="course-summary__item">
                    <span class="course-summary__label">${I18n.t('course_total_distance')}</span>
                    <span class="course-summary__value">${data.total_distance}km</span>
                </div>
                <div class="course-summary__item">
                    <span class="course-summary__label">${I18n.t('course_total_time')}</span>
                    <span class="course-summary__value">${timeStr}</span>
                </div>
            `;
        }
    }

    function resetCourse() {
        const map = MapModule.getMap();
        if (map && courseLayer) {
            map.removeLayer(courseLayer);
            courseLayer = null;
        }
        if (map && polylineLayer) {
            map.removeLayer(polylineLayer);
            polylineLayer = null;
        }
        if (map && startMarker) {
            map.removeLayer(startMarker);
            startMarker = null;
        }
        startLat = null;
        startLng = null;
        pickingStart = false;

        _showSettings();

        // Reset form
        const defaultRadio = document.querySelector('input[name="course-start"][value="default"]');
        if (defaultRadio) defaultRadio.checked = true;
        const halfRadio = document.querySelector('input[name="course-duration"][value="half"]');
        if (halfRadio) halfRadio.checked = true;
        document.querySelectorAll('.course-cat-check').forEach(c => c.checked = false);
        const maxInput = document.getElementById('course-max-spots');
        if (maxInput) maxInput.value = '5';
    }

    function _scoreClass(score) {
        if (score == null) return '';
        if (score >= 80) return 'score--good';
        if (score >= 60) return 'score--normal';
        if (score >= 40) return 'score--crowded';
        return 'score--very-crowded';
    }

    function _escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    return { init, openPanel, closePanel, resetCourse };
})();
