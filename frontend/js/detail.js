/**
 * detail.js — 관광지 상세 페이지
 */
(async () => {
    // 행동 로그 수집 초기화 (detail_view + detail_leave 자동 추적)
    if (typeof Analytics !== 'undefined') Analytics.init();

    // i18n 초기화 (init이 lang-select 리스너도 등록)
    await I18n.init();

    // Back button
    const backBtn = document.getElementById('btn-back');
    if (backBtn) {
        backBtn.addEventListener('click', () => history.back());
    }

    const params = new URLSearchParams(window.location.search);
    const spotId = params.get('id');
    if (!spotId) {
        document.title = `${I18n.t('error_page_title')} — Hello, Busan!`;
        return;
    }

    try {
        const res = await fetch(`/api/v1/spots/${encodeURIComponent(spotId)}?lang=${I18n.getLang()}`);
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
        _setHtml('info-hours', spot.operating_hours || I18n.t('info_none'));
        _setHtml('info-fee', spot.admission_fee || I18n.t('info_none'));
        _setText('info-phone', spot.phone || I18n.t('info_none'));

        // Description (HTML 태그 안전 렌더링)
        if (spot.description) {
            const descSection = document.getElementById('detail-desc-section');
            if (descSection) descSection.style.display = '';
            _setHtml('detail-description', spot.description);
        }

        // Map
        if (spot.lat != null && spot.lng != null) {
            const map = L.map('detail-map').setView([spot.lat, spot.lng], 15);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OSM',
                maxZoom: 18,
            }).addTo(map);
            L.marker([spot.lat, spot.lng]).addTo(map).bindPopup(spot.name);
            // Store map reference for directions module
            document.getElementById('detail-map')._leaflet_map = map;
        }

        // Directions: show button and set panel data when coordinates exist
        const dirPanel = document.getElementById('directions-panel');
        if (dirPanel && spot.lat != null && spot.lng != null) {
            dirPanel.dataset.lat = spot.lat;
            dirPanel.dataset.lng = spot.lng;
            dirPanel.dataset.spotId = spotId;
            const dirWrap = document.getElementById('directions-btn-wrap');
            if (dirWrap) dirWrap.style.display = '';
        }
        if (typeof DirectionsModule !== 'undefined') {
            DirectionsModule.initDetail();
        }

        // Share: set spot data, update OG meta, render share buttons
        if (typeof Share !== 'undefined') {
            Share.setSpot(spot);
            Share.updateOgMeta();
            Share.render('share-section', _showToast);
        }

        // Favorite Button
        _initFavoriteBtn(spotId);

        // Air Quality (야외 관광지인 경우)
        var outdoorCategories = ['nature', 'activity', 'nightview'];
        if (outdoorCategories.indexOf(spot.category) >= 0) {
            _loadDetailAirQuality();
        }

        // Menu (맛집 카테고리인 경우)
        if (spot.category === 'food') {
            _loadMenu(spotId);
        }

        // Nearby
        if (spot.nearby_spots && spot.nearby_spots.length > 0) {
            const nearbySection = document.getElementById('nearby-section');
            if (nearbySection) nearbySection.style.display = '';
            const list = document.getElementById('nearby-list');
            if (!list) return;
            spot.nearby_spots.forEach(ns => {
                const card = document.createElement('a');
                card.className = 'nearby-card';
                card.href = `/detail.html?id=${encodeURIComponent(ns.id)}`;
                const comfortHtml = ns.comfort_score != null
                    ? `<div class="nearby-card__comfort ${_scoreClass(ns.comfort_score)}">${ns.comfort_score}${I18n.t('unit_score')}</div>`
                    : '';
                card.innerHTML = `
                    <div class="nearby-card__name">${_escapeHtml(ns.name)}</div>
                    <div class="nearby-card__dist">${ns.distance_km}km</div>
                    ${comfortHtml}
                `;
                list.appendChild(card);
            });
        }

        // Similar Spots (콘텐츠 기반 유사 추천)
        _loadSimilarSpots(spotId);

    } catch (e) {
        console.error('상세 페이지 로드 실패:', e);
        _setText('detail-name', I18n.t('error_load_failed'));
    }

    // Language change — reload page to re-fetch with new lang
    window.addEventListener('langchange', () => {
        window.location.reload();
    });

    function _setText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    /**
     * HTML 태그가 포함된 텍스트를 안전하게 렌더링.
     * 안전한 태그(br, p, strong, em 등)만 허용하고 나머지는 제거.
     * TourAPI에서 수집한 description, operating_hours 등에 사용.
     */
    function _setHtml(id, html) {
        const el = document.getElementById(id);
        if (!el) return;
        el.innerHTML = _sanitizeHtml(html);
    }

    function _sanitizeHtml(raw) {
        if (!raw) return '';

        // HTML 엔티티 디코딩 (이중 인코딩 대응: &lt;br&gt; → <br>)
        const txt = raw
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&amp;/g, '&')
            .replace(/&quot;/g, '"')
            .replace(/&#39;/g, "'");

        // script/style 태그 내용 전체 제거 (태그 사이 내용 포함)
        const noScript = txt
            .replace(/<script[\s\S]*?<\/script>/gi, '')
            .replace(/<style[\s\S]*?<\/style>/gi, '');

        // 모든 이벤트 핸들러 속성 제거 (따옴표 있는/없는 값 모두 대응)
        const noEvents = noScript.replace(/\s+on\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*)/gi, '');

        // 허용 태그 목록
        const allowedTags = new Set([
            'br', 'p', 'strong', 'em', 'b', 'i', 'u',
            'ul', 'ol', 'li', 'span', 'div', 'a',
        ]);

        // 모든 HTML 태그를 검사하여 허용 목록에 없으면 제거
        const sanitized = noEvents.replace(/<\/?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*\/?>/gi, (match, tagName) => {
            if (allowedTags.has(tagName.toLowerCase())) {
                // a 태그의 href에서 위험한 프로토콜 제거 (javascript:, data:, vbscript:)
                if (tagName.toLowerCase() === 'a') {
                    return match.replace(/\s*href\s*=\s*["']?\s*(?:javascript|data|vbscript)\s*:[^"'>]*/gi, '');
                }
                return match;
            }
            return '';
        });

        return sanitized;
    }

    function _setScoreRing(score) {
        const ring = document.getElementById('comfort-ring');
        if (!ring) return;

        ring.classList.remove('comfort-score-ring--good', 'comfort-score-ring--normal', 'comfort-score-ring--crowded');
        if (score >= 80) {
            ring.classList.add('comfort-score-ring--good');
        } else if (score >= 60) {
            ring.classList.add('comfort-score-ring--normal');
        } else {
            ring.classList.add('comfort-score-ring--crowded');
        }
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
        const keyMap = {
            nature: 'category_nature', culture: 'category_culture', food: 'category_food',
            activity: 'category_activity', shopping: 'category_shopping', nightview: 'category_nightview',
        };
        return keyMap[cat] ? I18n.t(keyMap[cat]) : (cat || '');
    }

    function _escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
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

    /** 대기질 데이터 로드 (야외 관광지용) */
    var AQ_GRADE_CONFIG = {
        1: { key: 'aq_good',     css: 'good',     icon: '\u{1F7E2}' },
        2: { key: 'aq_moderate', css: 'moderate', icon: '\u{1F7E1}' },
        3: { key: 'aq_bad',      css: 'bad',      icon: '\u{1F7E0}' },
        4: { key: 'aq_very_bad', css: 'very_bad', icon: '\u{1F534}' },
    };

    async function _loadDetailAirQuality() {
        var section = document.getElementById('detail-air-quality');
        if (!section) return;

        try {
            var res = await fetch('/api/v1/air-quality');
            var json = await res.json();
            if (!json.success || !json.data || !json.data.summary) return;

            var summary = json.data.summary;
            var grade = summary.overall_grade;
            var config = AQ_GRADE_CONFIG[grade] || AQ_GRADE_CONFIG[2];

            var iconEl = document.getElementById('detail-aq-icon');
            if (iconEl) iconEl.textContent = config.icon;

            var gradeBar = document.getElementById('detail-aq-grade-bar');
            if (gradeBar) {
                gradeBar.className = 'air-quality__grade-bar air-quality__grade-bar--' + config.css;
                var gradeLabel = document.getElementById('detail-aq-grade-label');
                if (gradeLabel) gradeLabel.textContent = I18n.t(config.key);
            }

            var pm25El = document.getElementById('detail-aq-pm25');
            if (pm25El) {
                pm25El.textContent = summary.avg_pm25 != null
                    ? _escapeHtml(String(summary.avg_pm25)) + ' ' + I18n.t('aq_unit_ugm3')
                    : '--';
            }

            var pm10El = document.getElementById('detail-aq-pm10');
            if (pm10El) {
                pm10El.textContent = summary.avg_pm10 != null
                    ? _escapeHtml(String(summary.avg_pm10)) + ' ' + I18n.t('aq_unit_ugm3')
                    : '--';
            }

            var caiEl = document.getElementById('detail-aq-cai');
            if (caiEl) {
                caiEl.textContent = summary.avg_khai != null
                    ? String(summary.avg_khai)
                    : '--';
            }

            var stationEl = document.getElementById('detail-aq-station');
            if (stationEl) {
                stationEl.textContent = _escapeHtml(summary.city || '') +
                    ' (' + (summary.station_count || 0) + ')';
            }

            var timeEl = document.getElementById('detail-aq-time');
            if (timeEl && summary.timestamp) {
                var dt = new Date(summary.timestamp);
                var hh = String(dt.getHours()).padStart(2, '0');
                var mm = String(dt.getMinutes()).padStart(2, '0');
                timeEl.textContent = I18n.t('aq_updated') + ' ' + hh + ':' + mm;
            }

            section.style.display = '';
        } catch (e) {
            console.warn('대기질 로드 실패:', e);
        }
    }

    /** 메뉴 데이터 로드 및 렌더링 */
    let _allMenus = [];

    async function _loadMenu(id) {
        try {
            const res = await fetch(`/api/v1/spots/${encodeURIComponent(id)}/menu?lang=${I18n.getLang()}`);
            const json = await res.json();
            if (!json.success || !json.data || !json.data.is_restaurant) return;

            const data = json.data;
            _allMenus = data.menus || [];

            if (_allMenus.length === 0 && !data.summary) return;

            const section = document.getElementById('menu-section');
            if (section) section.style.display = '';

            // 요약 렌더링
            if (data.summary) {
                _renderMenuSummary(data.summary);
            }

            // 메뉴 리스트 렌더링
            _renderMenuList(_allMenus);

            // 필터 이벤트
            const filters = document.querySelectorAll('.menu-filter');
            filters.forEach(btn => {
                btn.addEventListener('click', () => {
                    filters.forEach(b => b.classList.remove('menu-filter--active'));
                    btn.classList.add('menu-filter--active');
                    const range = btn.dataset.range;
                    const filtered = range === 'all'
                        ? _allMenus
                        : _allMenus.filter(m => m.price_range === range);
                    _renderMenuList(filtered);
                });
            });
        } catch (e) {
            console.warn('메뉴 로드 실패:', e);
        }
    }

    function _renderMenuSummary(summary) {
        const el = document.getElementById('menu-summary');
        if (!el) return;

        const priceLabel = {
            low: I18n.t('menu_price_low'),
            mid: I18n.t('menu_price_mid'),
            high: I18n.t('menu_price_high'),
        };
        const rangeText = priceLabel[summary.price_range] || '';

        el.innerHTML = `
            <div class="menu-summary__item">
                <span class="menu-summary__label">${_escapeHtml(I18n.t('menu_avg_price'))}</span>
                <span class="menu-summary__value">${_formatPrice(summary.avg_price)}</span>
            </div>
            <div class="menu-summary__item">
                <span class="menu-summary__label">${_escapeHtml(I18n.t('menu_price_range_label'))}</span>
                <span class="menu-summary__value menu-price-tag menu-price-tag--${_escapeHtml(summary.price_range)}">${_escapeHtml(rangeText)}</span>
            </div>
            <div class="menu-summary__item">
                <span class="menu-summary__label">${_escapeHtml(I18n.t('menu_count'))}</span>
                <span class="menu-summary__value">${summary.menu_count}${_escapeHtml(I18n.t('menu_count_unit'))}</span>
            </div>
        `;
    }

    function _renderMenuList(menus) {
        const list = document.getElementById('menu-list');
        if (!list) return;

        if (menus.length === 0) {
            list.innerHTML = `<div class="menu-empty">${_escapeHtml(I18n.t('menu_empty'))}</div>`;
            return;
        }

        list.innerHTML = menus.map(m => {
            const signatureBadge = m.is_signature
                ? `<span class="menu-card__badge">${_escapeHtml(I18n.t('menu_signature'))}</span>`
                : '';
            const priceText = m.price ? _formatPrice(m.price) : I18n.t('menu_price_unknown');
            const rangeClass = m.price_range ? `menu-card__price--${_escapeHtml(m.price_range)}` : '';
            return `
                <div class="menu-card">
                    <div class="menu-card__info">
                        <div class="menu-card__name">${_escapeHtml(m.name)}${signatureBadge}</div>
                    </div>
                    <div class="menu-card__price ${rangeClass}">${_escapeHtml(priceText)}</div>
                </div>
            `;
        }).join('');
    }

    function _formatPrice(price) {
        if (!price) return '';
        return price.toLocaleString() + I18n.t('menu_currency');
    }

    async function _loadSimilarSpots(id) {
        try {
            const res = await fetch(`/api/v1/spots/${encodeURIComponent(id)}/similar?lang=${I18n.getLang()}`);
            const json = await res.json();
            if (!json.success || !json.data || json.data.length === 0) return;

            const section = document.getElementById('similar-section');
            if (section) section.style.display = '';

            const list = document.getElementById('similar-list');
            if (!list) return;

            json.data.forEach(s => {
                const card = document.createElement('a');
                card.className = 'similar-card';
                card.href = `/detail.html?id=${encodeURIComponent(s.id)}`;

                const thumbHtml = s.thumbnail_url
                    ? `<img class="similar-card__thumb" src="${_escapeHtml(s.thumbnail_url)}" alt="${_escapeHtml(s.name)}" loading="lazy">`
                    : `<div class="similar-card__thumb similar-card__thumb--empty">&#x1F3DE;</div>`;

                const catHtml = s.category_name
                    ? `<span class="similar-card__cat">${_escapeHtml(s.category_name)}</span>`
                    : '';

                card.innerHTML = `
                    ${thumbHtml}
                    <div class="similar-card__info">
                        <div class="similar-card__name">${_escapeHtml(s.name)}</div>
                        ${catHtml}
                    </div>
                `;
                list.appendChild(card);
            });
        } catch (e) {
            console.warn('유사 관광지 로드 실패:', e);
        }
    }

    function _initGallery(container, images, name) {
        const safeName = _escapeHtml(name);
        if (images.length === 1) {
            container.innerHTML = `<img src="${_escapeHtml(images[0])}" alt="${safeName}" loading="lazy">`;
            return;
        }

        let currentIdx = 0;

        // Build gallery HTML
        const trackHtml = images.map((src, i) =>
            `<img src="${_escapeHtml(src)}" alt="${safeName} ${i + 1}/${images.length}" loading="${i === 0 ? 'eager' : 'lazy'}">`
        ).join('');

        const dotsHtml = images.map((_, i) =>
            `<button class="gallery-dot${i === 0 ? ' gallery-dot--active' : ''}" data-idx="${i}" aria-label="${i + 1}/${images.length}"></button>`
        ).join('');

        container.innerHTML = `
            <div class="gallery-track">${trackHtml}</div>
            <button class="gallery-nav gallery-nav--prev" aria-label="${I18n.t('gallery_prev')}">&#x276E;</button>
            <button class="gallery-nav gallery-nav--next" aria-label="${I18n.t('gallery_next')}">&#x276F;</button>
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

        // Swipe support (tracks both axes to avoid hijacking vertical scroll)
        let startX = 0;
        let startY = 0;
        container.addEventListener('touchstart', (e) => {
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
        }, { passive: true });
        container.addEventListener('touchend', (e) => {
            const diffX = startX - e.changedTouches[0].clientX;
            const diffY = startY - e.changedTouches[0].clientY;
            if (Math.abs(diffX) > 40 && Math.abs(diffX) > Math.abs(diffY) * 1.5) {
                goTo(currentIdx + (diffX > 0 ? 1 : -1));
            }
        }, { passive: true });

        // Keyboard support
        container.setAttribute('tabindex', '0');
        container.setAttribute('role', 'region');
        container.setAttribute('aria-label', I18n.t('gallery_label'));
        container.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowLeft') goTo(currentIdx - 1);
            if (e.key === 'ArrowRight') goTo(currentIdx + 1);
        });
    }
})();
