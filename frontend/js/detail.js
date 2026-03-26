/**
 * detail.js — 관광지 상세 페이지
 */
(async () => {
    await I18n.init();

    const params = new URLSearchParams(window.location.search);
    const spotId = params.get('id');
    if (!spotId) {
        document.title = '오류 — Hello, Busan!';
        return;
    }

    try {
        const res = await fetch(`/api/v1/spots/${spotId}?lang=${I18n.getLang()}`);
        const json = await res.json();
        if (!json.success || !json.data) throw new Error('데이터 없음');

        const spot = json.data;
        document.title = `${spot.name} — Hello, Busan!`;

        // Gallery
        const gallery = document.getElementById('detail-gallery');
        if (gallery && spot.images && spot.images.length > 0) {
            gallery.innerHTML = `<img src="${spot.images[0]}" alt="${spot.name}">`;
        }

        // Comfort Dashboard
        if (spot.comfort) {
            const c = spot.comfort;
            _setText('comfort-score', c.score);
            _setText('comfort-grade', c.grade);
            _setScoreColor('comfort-score', c.score);

            if (c.components) {
                _setText('weather-score', c.components.weather?.score ?? '--');
                _setText('crowd-score', c.components.crowd?.score ?? '--');
                _setText('transport-score', c.components.transport?.score ?? '--');
            }
        }

        // Basic Info
        _setText('info-address', spot.address || '정보 없음');
        _setText('info-hours', spot.operating_hours || '정보 없음');
        _setText('info-fee', spot.admission_fee || '정보 없음');
        _setText('info-phone', spot.phone || '정보 없음');

        // Description
        if (spot.description) {
            document.getElementById('detail-desc-section').style.display = '';
            _setText('detail-description', spot.description);
        }

        // Map
        if (spot.lat && spot.lng) {
            const map = L.map('detail-map').setView([spot.lat, spot.lng], 15);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OSM',
                maxZoom: 18,
            }).addTo(map);
            L.marker([spot.lat, spot.lng]).addTo(map).bindPopup(spot.name);
        }

        // Nearby
        if (spot.nearby_spots && spot.nearby_spots.length > 0) {
            document.getElementById('nearby-section').style.display = '';
            const list = document.getElementById('nearby-list');
            spot.nearby_spots.forEach(ns => {
                const card = document.createElement('a');
                card.className = 'nearby-card';
                card.href = `/detail.html?id=${ns.id}`;
                card.innerHTML = `
                    <div class="nearby-card__name">${ns.name}</div>
                    <div class="nearby-card__dist">${ns.distance_km}km</div>
                `;
                list.appendChild(card);
            });
        }

    } catch (e) {
        console.error('상세 페이지 로드 실패:', e);
    }

    function _setText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    function _setScoreColor(id, score) {
        const el = document.getElementById(id);
        if (!el) return;
        if (score >= 80) el.style.color = 'var(--color-comfort)';
        else if (score >= 60) el.style.color = 'var(--color-normal)';
        else el.style.color = 'var(--color-crowded)';
    }
})();
