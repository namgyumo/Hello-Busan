/**
 * detail.js — 관광지 상세 페이지
 */
(async () => {
    // 행동 로그 수집 초기화 (detail_view + detail_leave 자동 추적)
    if (typeof Analytics !== 'undefined') Analytics.init();

    // i18n 초기화 (init이 lang-select 리스너도 등록)
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

        // Title Bar
        _setText('detail-name', spot.name);
        _setText('detail-address-sub', spot.address || '');
        const catEl = document.getElementById('detail-category');
        if (catEl && spot.category) {
            catEl.textContent = _categoryLabel(spot.category);
        }

        // Gallery
        const gallery = document.getElementById('detail-gallery');
        if (gallery && spot.images && spot.images.length > 0) {
            _initGallery(gallery, spot.images, spot.name);
        }

        // Comfort Dashboard
        if (spot.comfort) {
            const c = spot.comfort;
            _setText('comfort-score', c.score);
            _setText('comfort-grade', c.grade);
            _setScoreRing(c.score);

            if (c.components) {
                _setText('weather-score', c.components.weather?.score ?? '--');
                _setText('crowd-score', c.components.crowd?.score ?? '--');
                _setText('transport-score', c.components.transport?.score ?? '--');
                _addProgressBar('weather-score', c.components.weather?.score);
                _addProgressBar('crowd-score', c.components.crowd?.score);
                _addProgressBar('transport-score', c.components.transport?.score);
            }
        }

        // Basic Info
        _setText('info-address', spot.address || I18n.t('info_none'));
        _setText('info-hours', spot.operating_hours || I18n.t('info_none'));
        _setText('info-fee', spot.admission_fee || I18n.t('info_none'));
        _setText('info-phone', spot.phone || I18n.t('info_none'));

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

        // Share: set spot data, update OG meta, render share buttons
        if (typeof Share !== 'undefined') {
            Share.setSpot(spot);
            Share.updateOgMeta();
            Share.render('share-section', _showToast);
        }

        // Favorite Button
        _initFavoriteBtn(spotId);

        // Nearby
        if (spot.nearby_spots && spot.nearby_spots.length > 0) {
            document.getElementById('nearby-section').style.display = '';
            const list = document.getElementById('nearby-list');
            spot.nearby_spots.forEach(ns => {
                const card = document.createElement('a');
                card.className = 'nearby-card';
                card.href = `/detail.html?id=${ns.id}`;
                const comfortHtml = ns.comfort_score != null
                    ? `<div class="nearby-card__comfort ${_scoreClass(ns.comfort_score)}">${ns.comfort_score}${I18n.t('unit_score')}</div>`
                    : '';
                card.innerHTML = `
                    <div class="nearby-card__name">${ns.name}</div>
                    <div class="nearby-card__dist">${ns.distance_km}km</div>
                    ${comfortHtml}
                `;
                list.appendChild(card);
            });
        }

    } catch (e) {
        console.error('상세 페이지 로드 실패:', e);
        _setText('detail-name', '페이지를 불러올 수 없습니다');
    }

    // Language change — reload page to re-fetch with new lang
    window.addEventListener('langchange', () => {
        window.location.reload();
    });

    function _setText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    function _setScoreRing(score) {
        const ring = document.getElementById('comfort-ring');
        const numEl = document.getElementById('comfort-score');
        if (!ring || !numEl) return;

        let borderColor, bgColor, textColor;
        if (score >= 80) {
            borderColor = 'var(--color-comfort)';
            bgColor = '#D1FAE5';
            textColor = '#065F46';
        } else if (score >= 60) {
            borderColor = 'var(--color-normal)';
            bgColor = '#FEF3C7';
            textColor = '#92400E';
        } else {
            borderColor = 'var(--color-crowded)';
            bgColor = '#FEE2E2';
            textColor = '#991B1B';
        }
        ring.style.borderColor = borderColor;
        ring.style.background = bgColor;
        numEl.style.color = textColor;
    }

    function _addProgressBar(scoreElId, score) {
        const el = document.getElementById(scoreElId);
        if (!el || score == null) return;
        const parent = el.closest('.comfort-component');
        if (!parent || parent.querySelector('.comfort-component__bar')) return;
        const barClass = score >= 70 ? 'comfort-component__bar-fill--good'
            : score >= 40 ? 'comfort-component__bar-fill--normal'
            : 'comfort-component__bar-fill--crowded';
        const bar = document.createElement('div');
        bar.className = 'comfort-component__bar';
        bar.innerHTML = `<div class="comfort-component__bar-fill ${barClass}" style="width:0%"></div>`;
        parent.appendChild(bar);
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                bar.querySelector('.comfort-component__bar-fill').style.width = `${score}%`;
            });
        });
    }

    function _scoreClass(score) {
        if (score == null) return '';
        if (score >= 80) return 'score--good';
        if (score >= 60) return 'score--normal';
        if (score >= 40) return 'score--crowded';
        return 'score--very-crowded';
    }

    function _categoryLabel(cat) {
        const map = {
            nature: '자연/경관', culture: '문화/역사', food: '맛집/카페',
            activity: '액티비티', shopping: '쇼핑', nightview: '야경',
        };
        return map[cat] || cat || '';
    }

    function _initFavoriteBtn(id) {
        const btn = document.getElementById('btn-favorite');
        if (!btn || typeof Favorites === 'undefined') return;

        function updateIcon() {
            const isFav = Favorites.isFavorite(id);
            const icon = btn.querySelector('.favorite-btn__icon');
            if (isFav) {
                btn.classList.add('favorite-btn--active');
                icon.innerHTML = '&#x2764;';
                btn.setAttribute('aria-label', I18n.t('favorite_remove'));
            } else {
                btn.classList.remove('favorite-btn--active');
                icon.innerHTML = '&#x2661;';
                btn.setAttribute('aria-label', I18n.t('favorite_add'));
            }
        }

        updateIcon();

        btn.addEventListener('click', () => {
            const added = Favorites.toggle(id);
            updateIcon();
            _showToast(I18n.t(added ? 'favorite_added' : 'favorite_removed'));
            if (typeof Analytics !== 'undefined') Analytics.trackFavorite(id, added ? 'add' : 'remove');
        });
    }

    function _showToast(msg) {
        const el = document.getElementById('toast');
        if (!el) return;
        el.textContent = msg;
        el.classList.add('show');
        setTimeout(() => el.classList.remove('show'), 3000);
    }

    function _initGallery(container, images, name) {
        if (images.length === 1) {
            container.innerHTML = `<img src="${images[0]}" alt="${name}" loading="lazy">`;
            return;
        }

        let currentIdx = 0;

        // Build gallery HTML
        const trackHtml = images.map((src, i) =>
            `<img src="${src}" alt="${name} ${i + 1}/${images.length}" loading="${i === 0 ? 'eager' : 'lazy'}">`
        ).join('');

        const dotsHtml = images.map((_, i) =>
            `<button class="gallery-dot${i === 0 ? ' gallery-dot--active' : ''}" data-idx="${i}" aria-label="${i + 1}/${images.length}"></button>`
        ).join('');

        container.innerHTML = `
            <div class="gallery-track">${trackHtml}</div>
            <button class="gallery-nav gallery-nav--prev" aria-label="이전 이미지">&#x276E;</button>
            <button class="gallery-nav gallery-nav--next" aria-label="다음 이미지">&#x276F;</button>
            <div class="gallery-dots">${dotsHtml}</div>
        `;

        const track = container.querySelector('.gallery-track');
        const dots = container.querySelectorAll('.gallery-dot');
        const prevBtn = container.querySelector('.gallery-nav--prev');
        const nextBtn = container.querySelector('.gallery-nav--next');

        function goTo(idx) {
            if (idx < 0) idx = images.length - 1;
            if (idx >= images.length) idx = 0;
            currentIdx = idx;
            track.style.transform = `translateX(-${idx * 100}%)`;
            dots.forEach((d, i) => d.classList.toggle('gallery-dot--active', i === idx));
        }

        prevBtn.addEventListener('click', () => goTo(currentIdx - 1));
        nextBtn.addEventListener('click', () => goTo(currentIdx + 1));
        dots.forEach(dot => dot.addEventListener('click', () => goTo(Number(dot.dataset.idx))));

        // Swipe support
        let startX = 0;
        container.addEventListener('touchstart', (e) => { startX = e.touches[0].clientX; }, { passive: true });
        container.addEventListener('touchend', (e) => {
            const diff = startX - e.changedTouches[0].clientX;
            if (Math.abs(diff) > 40) goTo(currentIdx + (diff > 0 ? 1 : -1));
        }, { passive: true });

        // Keyboard support
        container.setAttribute('tabindex', '0');
        container.setAttribute('role', 'region');
        container.setAttribute('aria-label', '이미지 갤러리');
        container.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowLeft') goTo(currentIdx - 1);
            if (e.key === 'ArrowRight') goTo(currentIdx + 1);
        });
    }
})();
