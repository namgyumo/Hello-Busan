/**
 * directions.js -- Transit Directions (대중교통 길찾기)
 * Used in detail.html for navigating to a tourist spot
 * and in map.html for route visualization.
 */
const DirectionsModule = (() => {
    const API_BASE = '/api/v1';
    let routeLayer = null;
    let currentRoutes = [];
    let selectedRouteIdx = 0;

    // detail.html: attach click handler to the directions button
    function initDetail() {
        const btn = document.getElementById('btn-directions');
        if (!btn) return;
        btn.addEventListener('click', _onDirectionsClick);
    }

    // map.html: provide method for external callers
    function showRouteOnMap(route) {
        const map = typeof MapModule !== 'undefined' ? MapModule.getMap() : null;
        if (!map || !route) return;
        _clearRouteLayer(map);
        _drawRoute(map, route);
    }

    function clearRoute() {
        const map = typeof MapModule !== 'undefined' ? MapModule.getMap() : null;
        if (map && routeLayer) {
            map.removeLayer(routeLayer);
            routeLayer = null;
        }
    }

    async function _onDirectionsClick() {
        const btn = document.getElementById('btn-directions');
        const panel = document.getElementById('directions-panel');
        if (!panel) return;

        // Toggle panel visibility
        if (panel.classList.contains('directions-panel--open')) {
            panel.classList.remove('directions-panel--open');
            return;
        }

        if (btn) btn.disabled = true;
        panel.classList.add('directions-panel--open');
        panel.innerHTML = '<div class="directions-loading"><div class="directions-loading-spinner"></div><span>' + I18n.t('directions_searching') + '</span></div>';

        // Get spot coordinates from the page
        const spotLat = parseFloat(panel.dataset.lat);
        const spotLng = parseFloat(panel.dataset.lng);
        const spotId = panel.dataset.spotId || '';

        if (isNaN(spotLat) || isNaN(spotLng)) {
            panel.innerHTML = '<div class="directions-error">' + _escapeHtml(I18n.t('directions_error')) + '</div>';
            if (btn) btn.disabled = false;
            return;
        }

        // Get current location
        try {
            const pos = await _getCurrentPosition();
            const originLat = pos.coords.latitude;
            const originLng = pos.coords.longitude;

            const params = new URLSearchParams();
            params.set('origin_lat', originLat);
            params.set('origin_lng', originLng);
            if (spotId) {
                params.set('dest_id', spotId);
            } else {
                params.set('dest_lat', spotLat);
                params.set('dest_lng', spotLng);
            }
            params.set('lang', I18n.getLang());

            const res = await fetch(API_BASE + '/transport/directions?' + params);
            const json = await res.json();

            if (!json.success || !json.data || !json.data.routes || json.data.routes.length === 0) {
                panel.innerHTML = '<div class="directions-error">' + _escapeHtml(I18n.t('directions_no_routes')) + '</div>';
                if (btn) btn.disabled = false;
                return;
            }

            currentRoutes = json.data.routes;
            selectedRouteIdx = 0;
            _renderDirectionsPanel(panel, json.data);

        } catch (e) {
            if (e.code === 1) {
                // Permission denied
                panel.innerHTML = '<div class="directions-error">' + _escapeHtml(I18n.t('location_error')) + '</div>';
            } else {
                console.error('Directions error:', e);
                panel.innerHTML = '<div class="directions-error">' + _escapeHtml(I18n.t('directions_error')) + '</div>';
            }
        }

        if (btn) btn.disabled = false;
    }

    function _getCurrentPosition() {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                reject(new Error('Geolocation not supported'));
                return;
            }
            navigator.geolocation.getCurrentPosition(resolve, reject, {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 60000,
            });
        });
    }

    function _renderDirectionsPanel(panel, data) {
        const routes = data.routes;
        let html = '<div class="directions-header">';
        html += '<h4 class="directions-header__title">' + _escapeHtml(I18n.t('directions_title')) + '</h4>';
        html += '<button class="directions-header__close" id="directions-close" aria-label="' + _escapeHtml(I18n.t('course_close')) + '">&times;</button>';
        html += '</div>';

        html += '<div class="directions-distance">' + _escapeHtml(I18n.t('directions_direct_distance')) + ': ' + data.direct_distance_km + 'km</div>';

        // Route option tabs
        html += '<div class="directions-tabs" role="tablist">';
        routes.forEach((route, idx) => {
            const active = idx === selectedRouteIdx ? ' directions-tab--active' : '';
            const icon = _modeIcon(route.type);
            html += '<button class="directions-tab' + active + '" data-route-idx="' + idx + '" role="tab">';
            html += '<span class="directions-tab__icon">' + icon + '</span>';
            html += '<span class="directions-tab__time">' + route.total_time + _escapeHtml(I18n.t('course_minutes')) + '</span>';
            html += '</button>';
        });
        html += '</div>';

        // Selected route detail
        html += _renderRouteDetail(routes[selectedRouteIdx]);

        panel.innerHTML = html;

        // Attach tab click handlers
        panel.querySelectorAll('.directions-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                selectedRouteIdx = parseInt(tab.dataset.routeIdx, 10);
                _renderDirectionsPanel(panel, data);
            });
        });

        // Close button
        const closeBtn = panel.querySelector('#directions-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                panel.classList.remove('directions-panel--open');
            });
        }

        // Draw route on detail page map
        _drawRouteOnDetailMap(routes[selectedRouteIdx]);
    }

    function _renderRouteDetail(route) {
        let html = '<div class="directions-route-detail">';

        // Summary
        html += '<div class="directions-summary">';
        html += '<div class="directions-summary__item"><span class="directions-summary__label">' + _escapeHtml(I18n.t('directions_type')) + '</span><span class="directions-summary__value">' + _escapeHtml(_routeTypeLabel(route.type)) + '</span></div>';
        html += '<div class="directions-summary__item"><span class="directions-summary__label">' + _escapeHtml(I18n.t('directions_time')) + '</span><span class="directions-summary__value">' + route.total_time + _escapeHtml(I18n.t('course_minutes')) + '</span></div>';
        html += '<div class="directions-summary__item"><span class="directions-summary__label">' + _escapeHtml(I18n.t('directions_distance')) + '</span><span class="directions-summary__value">' + route.total_distance_km + 'km</span></div>';
        html += '<div class="directions-summary__item"><span class="directions-summary__label">' + _escapeHtml(I18n.t('directions_fare')) + '</span><span class="directions-summary__value">' + _formatFare(route.fare) + '</span></div>';
        if (route.transfers > 0) {
            html += '<div class="directions-summary__item"><span class="directions-summary__label">' + _escapeHtml(I18n.t('directions_transfers')) + '</span><span class="directions-summary__value">' + route.transfers + _escapeHtml(I18n.t('directions_transfers_unit')) + '</span></div>';
        }
        html += '</div>';

        // Segments
        html += '<div class="directions-segments">';
        route.segments.forEach((seg, idx) => {
            const modeClass = 'directions-segment--' + seg.mode;
            const icon = _modeIcon(seg.mode);
            html += '<div class="directions-segment ' + modeClass + '">';
            html += '<div class="directions-segment__icon">' + icon + '</div>';
            html += '<div class="directions-segment__body">';
            html += '<div class="directions-segment__mode">' + _escapeHtml(_modeLabel(seg.mode)) + '</div>';
            html += '<div class="directions-segment__info">' + _escapeHtml(seg.from.name) + ' &rarr; ' + _escapeHtml(seg.to.name) + '</div>';
            html += '<div class="directions-segment__meta">' + seg.distance_km + 'km / ' + seg.time_min + _escapeHtml(I18n.t('course_minutes')) + '</div>';
            html += '</div>';
            html += '</div>';
        });
        html += '</div>';

        html += '</div>';
        return html;
    }

    function _drawRouteOnDetailMap(route) {
        // Find the Leaflet map instance on detail page
        // detail.js stores the map reference as _leaflet_map on the container
        const mapEl = document.getElementById('detail-map');
        if (!mapEl) return;

        const map = mapEl._leaflet_map || null;
        if (!map) return;

        _clearRouteLayer(map);
        _drawRoute(map, route);
    }

    function _clearRouteLayer(map) {
        if (routeLayer) {
            map.removeLayer(routeLayer);
            routeLayer = null;
        }
    }

    function _drawRoute(map, route) {
        if (!route.polyline || route.polyline.length < 2) return;

        routeLayer = L.layerGroup().addTo(map);

        // Draw each segment with different colors
        const segments = route.segments || [];
        let prevPoint = route.polyline[0];

        segments.forEach(seg => {
            const from = [seg.from.lat, seg.from.lng];
            const to = [seg.to.lat, seg.to.lng];
            const color = _modeColor(seg.mode);
            const dashArray = seg.mode === 'walk' ? '6, 8' : null;

            const line = L.polyline([from, to], {
                color: color,
                weight: 5,
                opacity: 0.85,
                dashArray: dashArray,
                lineCap: 'round',
            }).addTo(routeLayer);
        });

        // Fit bounds
        const bounds = L.latLngBounds(route.polyline);
        map.fitBounds(bounds.pad(0.2));
    }

    function _modeColor(mode) {
        switch (mode) {
            case 'bus': return '#2ECC71';
            case 'subway': return '#3498DB';
            case 'walk': return '#95A5A6';
            default: return '#0066CC';
        }
    }

    function _modeIcon(type) {
        switch (type) {
            case 'walk': return '&#x1F6B6;';
            case 'bus': return '&#x1F68C;';
            case 'subway': return '&#x1F687;';
            case 'subway_bus': return '&#x1F687;';
            case 'bus_transfer': return '&#x1F504;';
            default: return '&#x1F68C;';
        }
    }

    function _modeLabel(mode) {
        switch (mode) {
            case 'walk': return I18n.t('directions_walk');
            case 'bus': return I18n.t('directions_bus');
            case 'subway': return I18n.t('directions_subway');
            default: return mode;
        }
    }

    function _routeTypeLabel(type) {
        switch (type) {
            case 'walk': return I18n.t('directions_walk');
            case 'bus': return I18n.t('directions_bus');
            case 'subway_bus': return I18n.t('directions_subway_bus');
            case 'bus_transfer': return I18n.t('directions_bus_transfer');
            default: return type;
        }
    }

    function _formatFare(fare) {
        if (!fare || fare === 0) return I18n.t('directions_free');
        return fare.toLocaleString() + I18n.t('directions_currency');
    }

    function _escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    return { initDetail, showRouteOnMap, clearRoute };
})();
